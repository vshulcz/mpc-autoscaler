#!/usr/bin/env python3
"""Run the online MPC controller against a Kubernetes deployment."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
import re

from mpc_autoscaler_analysis.mpc import greedy_replica_action, solve_backlog_mpc, update_backlog


SOLVED_STATUSES = {"optimal", "optimal_inaccurate"}

# PromQL duration: positive integer followed by a unit. Conservative subset.
_PROM_DURATION_RE = re.compile(r"^[0-9]+(ms|s|m|h|d|w|y)$")


def escape_promql_label(value: str) -> str:
    """Escape a string for safe use inside a PromQL label matcher value.

    PromQL strings are double-quoted; backslash, quote and newline must be
    escaped to prevent injection through CLI-provided namespace/deployment names.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def validate_promql_duration(value: str, *, name: str) -> str:
    """Return ``value`` if it is a valid PromQL duration, else raise ValueError."""
    if not _PROM_DURATION_RE.match(value):
        raise ValueError(
            f"{name!s} must match PromQL duration (e.g. '30s', '1m', '2h'); got {value!r}"
        )
    return value


@dataclass
class MPCConfig:
    """Controller configuration for one run."""

    horizon: int
    alpha: float           # backlog penalty weight
    beta: float            # smoothness penalty weight
    gamma: float           # capacity cost weight
    rho_star: float        # target utilization level
    capacity_per_replica: float  # mu: per-replica throughput (RPS)
    normalization_reference_replicas: float
    min_replicas: int
    max_replicas: int
    max_step: int          # Delta_max
    dt_seconds: int        # Delta_t: control step length
    normalized_objective: bool
    constraint_tolerance: float

    def __post_init__(self) -> None:
        if self.horizon <= 0:
            raise ValueError(f"horizon must be > 0, got {self.horizon}")
        if self.alpha < 0 or self.beta < 0 or self.gamma < 0:
            raise ValueError(
                f"alpha, beta, gamma must be >= 0; got {self.alpha}, {self.beta}, {self.gamma}"
            )
        if not (0.0 < self.rho_star <= 1.0):
            raise ValueError(f"rho_star must be in (0, 1], got {self.rho_star}")
        if self.capacity_per_replica <= 0:
            raise ValueError(
                f"capacity_per_replica must be > 0, got {self.capacity_per_replica}"
            )
        if self.normalization_reference_replicas <= 0:
            raise ValueError(
                "normalization_reference_replicas must be > 0, "
                f"got {self.normalization_reference_replicas}"
            )
        if self.min_replicas < 1:
            raise ValueError(f"min_replicas must be >= 1, got {self.min_replicas}")
        if self.max_replicas < self.min_replicas:
            raise ValueError(
                f"max_replicas ({self.max_replicas}) must be >= min_replicas ({self.min_replicas})"
            )
        if self.max_step < 1:
            raise ValueError(f"max_step must be >= 1, got {self.max_step}")
        if self.dt_seconds <= 0:
            raise ValueError(f"dt_seconds must be > 0, got {self.dt_seconds}")
        if self.constraint_tolerance < 0:
            raise ValueError(
                f"constraint_tolerance must be >= 0, got {self.constraint_tolerance}"
            )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--namespace", default="default")
    p.add_argument("--deployment", default="toy-load-toy-load")
    p.add_argument("--prom-namespace", default="toy-monitoring")
    p.add_argument("--prom-service", default="toy-prometheus")
    p.add_argument("--step-seconds", type=int, default=15)
    p.add_argument("--duration-seconds", type=int, default=900)
    p.add_argument(
        "--control-mode",
        choices=("qp", "no_qp_reactive", "proxy_hpa_safety"),
        default="qp",
        help="Replica recommendation mode before safety overrides.",
    )
    p.add_argument("--forecast", choices=("es", "hold"), default="es")
    p.add_argument("--es-alpha", type=float, default=0.45)
    p.add_argument("--history-window", type=int, default=60)
    p.add_argument(
        "--prom-query-retries",
        type=int,
        default=3,
        help="Retries per Prometheus query before marking it failed.",
    )
    p.add_argument(
        "--prom-query-backoff-seconds",
        type=float,
        default=0.3,
        help="Backoff base (seconds) between Prometheus query retries.",
    )
    p.add_argument(
        "--demand-mode",
        choices=("served", "served_plus_inflight", "max_served_inflight"),
        default="served_plus_inflight",
    )
    p.add_argument("--inflight-gain", type=float, default=4.0)
    p.add_argument("--demand-cap-rps", type=float, default=400.0)
    p.add_argument("--emergency-inflight-threshold", type=float, default=40.0)
    p.add_argument("--emergency-step", type=int, default=4)
    p.add_argument(
        "--emergency-mode",
        choices=("step", "max"),
        default="step",
        help="Emergency scale-up mode: +step or immediate max replicas.",
    )
    p.add_argument(
        "--metric-rate-window",
        default="1m",
        help="Prometheus rate window for rate() queries, e.g. 15s, 30s, 1m.",
    )
    p.add_argument(
        "--surge-delta-threshold",
        type=float,
        default=1e9,
        help="If observed_rps jump over previous step exceeds this threshold, force scale-up by surge-step. Large default disables.",
    )
    p.add_argument(
        "--surge-step",
        type=int,
        default=2,
        help="Scale-up step applied when surge-delta-threshold is triggered.",
    )
    p.add_argument(
        "--capacity-trigger-fraction",
        type=float,
        default=2.0,
        help="If observed_rps exceeds fraction*served_capacity, force scale-up by capacity-trigger-step. >1 disables by default.",
    )
    p.add_argument(
        "--capacity-trigger-step",
        type=int,
        default=2,
        help="Scale-up step applied when capacity-trigger-fraction is triggered.",
    )
    p.add_argument(
        "--downscale-cooldown-seconds",
        type=float,
        default=0.0,
        help="Block downscale for this many seconds after a scale-up. <=0 disables.",
    )
    p.add_argument(
        "--downscale-inflight-threshold",
        type=float,
        default=-1.0,
        help="Block downscale while observed inflight exceeds this value. <0 disables.",
    )
    p.add_argument(
        "--max-downscale-step",
        type=int,
        default=0,
        help="Limit applied downscale step. <=0 keeps QP-recommended downscale.",
    )
    p.add_argument("--proxy-ema-alpha", type=float, default=0.45)
    p.add_argument("--proxy-downscale-stabilization-seconds", type=float, default=300.0)
    p.add_argument("--horizon", type=int, default=8)
    p.add_argument("--alpha", type=float, default=15.0)
    p.add_argument("--beta", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=0.08)
    p.add_argument("--rho-star", type=float, default=0.70)
    p.add_argument("--capacity-per-replica", type=float, default=25.0)
    p.add_argument("--normalization-reference-replicas", type=float, default=12.0)
    p.add_argument("--min-replicas", type=int, default=2)
    p.add_argument("--max-replicas", type=int, default=12)
    p.add_argument("--max-step", type=int, default=2)
    p.add_argument(
        "--normalized-objective",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use objective terms scaled by backlog, step and replica ranges. "
            "Default matches offline simulation; pass --no-normalized-objective "
            "to reproduce legacy un-normalized behaviour."
        ),
    )
    p.add_argument(
        "--constraint-tolerance",
        type=float,
        default=1e-2,
        help="Absolute tolerance for post-solve constraint checks.",
    )
    p.add_argument("--log-csv", required=True, help="Decision log CSV output path.")
    apply_group = p.add_mutually_exclusive_group()
    apply_group.add_argument(
        "--apply",
        action="store_true",
        help="Call kubectl scale. Without this flag the controller only logs recommendations.",
    )
    apply_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Default mode: do not call kubectl scale, only log recommended replicas.",
    )
    p.add_argument(
        "--kube-server",
        default=os.environ.get("KUBECTL_SERVER", ""),
        help="kubectl --server URL (e.g. http://127.0.0.1:8001 via kubectl proxy). "
             "Falls back to KUBECTL_SERVER env var.",
    )
    p.add_argument(
        "--kube-context",
        default=os.environ.get("KUBECTL_CONTEXT", ""),
        help="kubectl context name. Falls back to KUBECTL_CONTEXT env var.",
    )
    return p.parse_args()


def run_cmd(cmd: list[str]) -> str:
    """Run a command and return stripped stdout."""
    timeout = float(os.environ.get("MPC_KUBECTL_TIMEOUT_SECONDS", "30"))
    return subprocess.check_output(
        cmd,
        text=True,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    ).strip()


# Injected once at startup from --kube-server / KUBECTL_SERVER env.
_KUBE_SERVER: str = ""
_KUBE_CONTEXT: str = ""


def _kube(extra_flags: list[str]) -> list[str]:
    """Return ['kubectl', '--server=...'] when proxy is configured, else ['kubectl']."""
    base = ["kubectl"]
    if _KUBE_CONTEXT:
        base.append(f"--context={_KUBE_CONTEXT}")
    if _KUBE_SERVER:
        base.append(f"--server={_KUBE_SERVER}")
    return base + extra_flags


def utc_now() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prom_query(
    prom_ns: str,
    prom_service: str,
    query: str,
    retries: int = 1,
    backoff_seconds: float = 0.0,
) -> float:
    """Query Prometheus through the Kubernetes API proxy and return a scalar value."""
    params = urllib.parse.urlencode({"query": query})
    path = (
        f"/api/v1/namespaces/{prom_ns}/services/http:{prom_service}:9090/"
        f"proxy/api/v1/query?{params}"
    )
    attempts = max(1, int(retries))
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            raw = run_cmd(_kube(["--request-timeout=30s", "-n", prom_ns, "get", "--raw", path]))
            payload = json.loads(raw)
            if payload.get("status") != "success":
                raise RuntimeError(f"Prometheus query failed: {payload}")
            result = payload.get("data", {}).get("result", [])
            if not result:
                return 0.0
            val = result[0]["value"][1]
            if val in ("NaN", "Inf", "-Inf"):
                return 0.0
            return float(val)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if i < attempts - 1 and backoff_seconds > 0:
                time.sleep(backoff_seconds * (2**i))
    raise RuntimeError(f"Prometheus query failed after {attempts} attempts: {last_exc}")


def get_deployment_replicas(
    namespace: str, deployment: str, retries: int = 5, backoff: float = 2.0
) -> tuple[int, int]:
    """Return ready and desired replica counts."""
    last_exc: Exception | None = None
    for i in range(max(1, retries)):
        try:
            out = run_cmd(
                _kube(
                    [
                        "--request-timeout=30s",
                        "-n",
                        namespace,
                        "get",
                        "deploy",
                        deployment,
                        "-o",
                        "jsonpath={.status.readyReplicas},{.spec.replicas}",
                    ]
                )
            )
            ready_raw, _, desired_raw = out.partition(",")
            ready = int(ready_raw) if ready_raw.strip() else 0
            desired = int(desired_raw) if desired_raw.strip() else ready
            return max(0, ready), max(0, desired)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if i < retries - 1:
                time.sleep(backoff * (2**i))
    raise RuntimeError(f"get_deployment_replicas failed after {retries} attempts: {last_exc}")


def get_current_replicas(namespace: str, deployment: str, retries: int = 5, backoff: float = 2.0) -> int:
    """Return ready replicas for callers that only need capacity state."""
    ready, _ = get_deployment_replicas(namespace, deployment, retries, backoff)
    return ready


def scale_replicas(namespace: str, deployment: str, replicas: int) -> None:
    """Scale the deployment to the requested replica count."""
    run_cmd(
        _kube(
            [
                "--request-timeout=30s",
                "-n",
                namespace,
                "scale",
                "deploy",
                deployment,
                f"--replicas={replicas}",
            ]
        )
    )


def forecast_series(
    history: list[float], horizon: int, mode: str, es_alpha: float
) -> list[float]:
    """Build a short-horizon demand forecast from recent history."""
    if not history:
        return [0.0] * horizon
    if mode == "hold":
        return [float(history[-1])] * horizon

    level = history[0]
    for x in history[1:]:
        level = es_alpha * x + (1.0 - es_alpha) * level
    guarded = max(level, history[-1], 0.0)
    return [float(guarded)] * horizon


def solve_mpc_action(
    forecast: list[float],
    b0: float,
    r_current: int,
    cfg: MPCConfig,
) -> tuple[int, str]:
    """Solve one MPC step and return the next replica recommendation."""
    return solve_backlog_mpc(
        forecast=forecast,
        b0=b0,
        r_current=r_current,
        alpha=cfg.alpha,
        beta=cfg.beta,
        gamma=cfg.gamma,
        capacity_per_replica=cfg.capacity_per_replica,
        rho_star=cfg.rho_star,
        min_replicas=cfg.min_replicas,
        max_replicas=cfg.max_replicas,
        max_step=cfg.max_step,
        dt_seconds=cfg.dt_seconds,
        fallback=lambda forecast_first, current: greedy_replica_action(
            forecast_first,
            current,
            min_replicas=cfg.min_replicas,
            max_replicas=cfg.max_replicas,
            max_step=cfg.max_step,
            capacity_per_replica=cfg.capacity_per_replica,
            rho_star=cfg.rho_star,
            status="fallback",
        ),
        accepted_statuses=SOLVED_STATUSES,
        constraint_tolerance=cfg.constraint_tolerance,
        normalized_objective=cfg.normalized_objective,
        normalization_reference_replicas=cfg.normalization_reference_replicas,
    )


def solve_reactive_action(demand_proxy: float, r_current: int, cfg: MPCConfig) -> int:
    target_capacity = max(cfg.capacity_per_replica * cfg.rho_star, 1e-9)
    desired = math.ceil(max(demand_proxy, 0.0) / target_capacity)
    desired = max(cfg.min_replicas, min(cfg.max_replicas, desired))
    if desired > r_current:
        return min(cfg.max_replicas, r_current + cfg.max_step, desired)
    if desired < r_current:
        return max(cfg.min_replicas, r_current - cfg.max_step, desired)
    return r_current


def solve_proxy_hpa_action(
    demand_proxy: float,
    r_current: int,
    cfg: MPCConfig,
    desired_history: list[tuple[float, int]],
    elapsed: float,
    stabilization_seconds: float,
) -> int:
    target_capacity = max(cfg.capacity_per_replica * cfg.rho_star, 1e-9)
    desired = math.ceil(max(demand_proxy, 0.0) / target_capacity)
    desired = max(cfg.min_replicas, min(cfg.max_replicas, desired))
    desired_history.append((elapsed, desired))
    if stabilization_seconds > 0:
        cutoff = elapsed - stabilization_seconds
        desired_history[:] = [(ts, value) for ts, value in desired_history if ts >= cutoff]
    if desired < r_current and desired_history:
        desired = max(value for _, value in desired_history)
    if desired > r_current:
        return min(cfg.max_replicas, r_current + cfg.max_step, desired)
    if desired < r_current:
        return max(cfg.min_replicas, r_current - cfg.max_step, desired)
    return r_current


def main() -> int:
    global _KUBE_CONTEXT, _KUBE_SERVER
    args = parse_args()
    _KUBE_CONTEXT = args.kube_context.strip()
    _KUBE_SERVER = args.kube_server.strip()
    if _KUBE_CONTEXT:
        print(f"[mpc] kubectl context: {_KUBE_CONTEXT}", flush=True)
    if _KUBE_SERVER:
        print(f"[mpc] kubectl proxy: {_KUBE_SERVER}", flush=True)
    if not args.apply:
        print("[mpc] dry-run mode: pass --apply to scale the deployment", flush=True)

    log_path = Path(args.log_csv).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = MPCConfig(
        horizon=args.horizon,
        alpha=args.alpha,
        beta=args.beta,
        gamma=args.gamma,
        rho_star=args.rho_star,
        capacity_per_replica=args.capacity_per_replica,
        normalization_reference_replicas=args.normalization_reference_replicas,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
        max_step=args.max_step,
        dt_seconds=args.step_seconds,
        normalized_objective=args.normalized_objective,
        constraint_tolerance=args.constraint_tolerance,
    )

    ns_label = escape_promql_label(args.namespace)
    job_label = escape_promql_label(args.deployment)
    rate_window = validate_promql_duration(args.metric_rate_window, name="--metric-rate-window")

    rps_query = (
        f'sum(rate(toy_http_requests_total{{namespace="{ns_label}",'
        f'job="{job_label}",path="/work"}}[{rate_window}]))'
    )
    cpu_query = (
        f'sum(rate(process_cpu_seconds_total{{namespace="{ns_label}",'
        f'job="{job_label}"}}[{rate_window}]))'
    )
    inflight_query = (
        f'sum(toy_in_flight_requests{{namespace="{ns_label}",'
        f'job="{job_label}"}})'
    )

    started = time.time()
    ready_replicas, desired_replicas = get_deployment_replicas(
        args.namespace, args.deployment
    )

    b0_state = 0.0

    rps_hist: list[float] = []

    fields = [
        "ts_utc",
        "control_mode",
        "elapsed_s",
        "observed_rps",
        "observed_cpu_cores",
        "observed_inflight",
        "rps_query_failed",
        "cpu_query_failed",
        "inflight_query_failed",
        "demand_proxy_rps",
        "backlog_state",
        "prev_replicas",
        "ready_replicas",
        "desired_replicas",
        "qp_recommended_replicas",
        "recommended_replicas",
        "applied_replicas",
        "emergency_scale_up",
        "surge_scale_up",
        "capacity_scale_up",
        "downscale_blocked",
        "downscale_limited",
        "safety_raised",
        "solver_status",
    ]

    last_good_rps = 0.0
    last_good_cpu = 0.0
    last_good_inflight = 0.0
    prev_observed_rps: float | None = None
    last_scale_up_elapsed = -math.inf
    proxy_ema: float | None = None
    proxy_desired_history: list[tuple[float, int]] = []

    with log_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        next_tick = started
        while True:
            now = time.time()
            elapsed = now - started
            if elapsed > args.duration_seconds:
                break

            rps_failed = 0
            cpu_failed = 0
            inflight_failed = 0

            try:
                observed_rps = prom_query(
                    args.prom_namespace,
                    args.prom_service,
                    rps_query,
                    retries=args.prom_query_retries,
                    backoff_seconds=args.prom_query_backoff_seconds,
                )
                last_good_rps = observed_rps
            except Exception as exc:  # noqa: BLE001
                observed_rps = last_good_rps
                rps_failed = 1
                print(f"[warn] rps query failed: {exc}", file=sys.stderr)

            try:
                observed_cpu = prom_query(
                    args.prom_namespace,
                    args.prom_service,
                    cpu_query,
                    retries=args.prom_query_retries,
                    backoff_seconds=args.prom_query_backoff_seconds,
                )
                last_good_cpu = observed_cpu
            except Exception as exc:  # noqa: BLE001
                observed_cpu = last_good_cpu
                cpu_failed = 1
                print(f"[warn] cpu query failed: {exc}", file=sys.stderr)

            try:
                observed_inflight = prom_query(
                    args.prom_namespace,
                    args.prom_service,
                    inflight_query,
                    retries=args.prom_query_retries,
                    backoff_seconds=args.prom_query_backoff_seconds,
                )
                last_good_inflight = observed_inflight
            except Exception as exc:  # noqa: BLE001
                observed_inflight = last_good_inflight
                inflight_failed = 1
                print(f"[warn] inflight query failed: {exc}", file=sys.stderr)

            try:
                ready_replicas, desired_replicas = get_deployment_replicas(
                    args.namespace, args.deployment
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] replica query failed: {exc}", file=sys.stderr)

            if args.demand_mode == "served":
                demand_proxy = observed_rps
            elif args.demand_mode == "max_served_inflight":
                demand_proxy = max(observed_rps, observed_inflight * args.inflight_gain)
            else:
                demand_proxy = observed_rps + observed_inflight * args.inflight_gain

            if math.isfinite(args.demand_cap_rps) and args.demand_cap_rps > 0:
                demand_proxy = min(demand_proxy, args.demand_cap_rps)
            demand_proxy = max(demand_proxy, 0.0)

            # Update the backlog state from the latest demand estimate.
            b0_state = update_backlog(
                b0=b0_state,
                lambda_obs=demand_proxy,
                r_prev=ready_replicas,
                mu=cfg.capacity_per_replica,
                rho_star=cfg.rho_star,
                dt=float(cfg.dt_seconds),
            )

            rps_hist.append(demand_proxy)
            rps_hist = rps_hist[-args.history_window :]

            forecast = forecast_series(
                history=rps_hist,
                horizon=cfg.horizon,
                mode=args.forecast,
                es_alpha=args.es_alpha,
            )

            if args.control_mode == "qp":
                rec, status = solve_mpc_action(
                    forecast=forecast,
                    b0=b0_state,
                    r_current=desired_replicas,
                    cfg=cfg,
                )
            elif args.control_mode == "no_qp_reactive":
                rec = solve_reactive_action(
                    demand_proxy=demand_proxy,
                    r_current=desired_replicas,
                    cfg=cfg,
                )
                status = "no_qp_reactive"
            else:
                alpha = min(1.0, max(0.0, args.proxy_ema_alpha))
                if proxy_ema is None:
                    proxy_ema = demand_proxy
                else:
                    proxy_ema = alpha * demand_proxy + (1.0 - alpha) * proxy_ema
                rec = solve_proxy_hpa_action(
                    demand_proxy=proxy_ema,
                    r_current=desired_replicas,
                    cfg=cfg,
                    desired_history=proxy_desired_history,
                    elapsed=elapsed,
                    stabilization_seconds=args.proxy_downscale_stabilization_seconds,
                )
                status = "proxy_hpa_safety"
            qp_rec = rec

            emergency = 0
            if observed_inflight >= args.emergency_inflight_threshold:
                emergency = 1
                if args.emergency_mode == "max":
                    rec = cfg.max_replicas
                else:
                    rec = min(
                        cfg.max_replicas,
                        max(rec, desired_replicas + args.emergency_step),
                    )

            surge_scale = 0
            if (
                prev_observed_rps is not None
                and args.surge_delta_threshold > 0
                and math.isfinite(args.surge_delta_threshold)
                and observed_rps - prev_observed_rps >= args.surge_delta_threshold
            ):
                surge_scale = 1
                rec = min(cfg.max_replicas, max(rec, desired_replicas + args.surge_step))

            capacity_scale = 0
            served_capacity = max(
                ready_replicas * cfg.capacity_per_replica * cfg.rho_star, 1e-9
            )
            if 0 < args.capacity_trigger_fraction <= 1.0 and (
                observed_rps >= served_capacity * args.capacity_trigger_fraction
            ):
                capacity_scale = 1
                rec = min(
                    cfg.max_replicas,
                    max(rec, desired_replicas + args.capacity_trigger_step),
                )

            downscale_blocked = 0
            downscale_limited = 0
            if rec < desired_replicas:
                if (
                    args.downscale_inflight_threshold >= 0
                    and observed_inflight > args.downscale_inflight_threshold
                ):
                    rec = desired_replicas
                    downscale_blocked = 1
                if (
                    rec < desired_replicas
                    and args.downscale_cooldown_seconds > 0
                    and elapsed - last_scale_up_elapsed < args.downscale_cooldown_seconds
                ):
                    rec = desired_replicas
                    downscale_blocked = 1
                if (
                    rec < desired_replicas
                    and args.max_downscale_step > 0
                    and desired_replicas - rec > args.max_downscale_step
                ):
                    rec = desired_replicas - args.max_downscale_step
                    downscale_limited = 1

            if desired_replicas > ready_replicas and rec < desired_replicas:
                rec = desired_replicas
                downscale_blocked = 1
                downscale_limited = 0

            safety_raised = int(rec > qp_rec)

            applied = rec
            if not args.apply:
                applied = desired_replicas
            else:
                try:
                    scale_replicas(args.namespace, args.deployment, rec)
                    applied = rec
                except Exception as exc:  # noqa: BLE001
                    status = f"scale_error:{type(exc).__name__}"
                    applied = desired_replicas
                    print(f"[warn] scale failed: {exc}", file=sys.stderr)

            writer.writerow(
                {
                    "ts_utc": utc_now(),
                    "control_mode": args.control_mode,
                    "elapsed_s": f"{elapsed:.1f}",
                    "observed_rps": f"{observed_rps:.6f}",
                    "observed_cpu_cores": f"{observed_cpu:.6f}",
                    "observed_inflight": f"{observed_inflight:.6f}",
                    "rps_query_failed": rps_failed,
                    "cpu_query_failed": cpu_failed,
                    "inflight_query_failed": inflight_failed,
                    "demand_proxy_rps": f"{demand_proxy:.6f}",
                    "backlog_state": f"{b0_state:.6f}",
                    "prev_replicas": desired_replicas,
                    "ready_replicas": ready_replicas,
                    "desired_replicas": desired_replicas,
                    "qp_recommended_replicas": qp_rec,
                    "recommended_replicas": rec,
                    "applied_replicas": applied,
                    "emergency_scale_up": emergency,
                    "surge_scale_up": surge_scale,
                    "capacity_scale_up": capacity_scale,
                    "downscale_blocked": downscale_blocked,
                    "downscale_limited": downscale_limited,
                    "safety_raised": safety_raised,
                    "solver_status": status,
                }
            )
            f.flush()

            if applied > desired_replicas:
                last_scale_up_elapsed = elapsed
            desired_replicas = applied
            prev_observed_rps = observed_rps
            next_tick += args.step_seconds
            sleep_for = next_tick - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                overrun = -sleep_for
                next_tick += math.ceil(overrun / args.step_seconds) * args.step_seconds

    print(f"Saved control log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
