#!/usr/bin/env python3
"""Simulate the online MPC controller with a more realistic offline model."""

from __future__ import annotations

import argparse
import csv
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

warnings.filterwarnings("ignore", message=".*Solution may be inaccurate.*")

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    SM_OK = True
except ImportError:
    ExponentialSmoothing = None
    SM_OK = False

from mpc_autoscaler_analysis.mpc import greedy_replica_action, solve_backlog_mpc, update_backlog
from mpc_autoscaler_analysis.paths import default_trace_dir, resolve_output_path


SOLVED_STATUSES = {"optimal", "optimal_inaccurate"}


# Configuration

@dataclass
class PhysicsParams:
    """Physical system parameters calibrated from real runs."""
    mu: float = 25.0            # effective throughput per replica (RPS), CPU-limited
    service_time_s: float = 0.023  # observed low-load latency (s)
    rho_star: float = 0.70      # surrogate SLO utilization target
    inflight_gain: float = 4.0  # demand proxy: demand = rps + gain * inflight
    inflight_cap_per_replica: float = 2.0
    demand_cap_rps: float = 400.0


@dataclass
class MPCParams:
    """MPC QP and forecast parameters."""
    alpha: float = 15.0         # backlog penalty weight
    beta: float = 1.0           # smoothness penalty weight
    gamma: float = 0.08         # replica cost weight
    horizon: int = 8            # prediction horizon (steps)
    es_alpha: float = 0.45      # ES smoothing factor
    min_replicas: int = 2
    max_replicas: int = 12
    max_step: int = 2           # max replica change per step
    normalized_objective: bool = True
    normalization_reference_replicas: float = 12.0


@dataclass
class SafetyParams:
    """Safety layer thresholds."""
    emergency_inflight_threshold: float = 40.0  # inflight triggers emergency
    emergency_step: int = 4                      # replicas to add on emergency
    surge_delta_rps: float = 1e9                # disabled by default
    surge_step: int = 2


@dataclass
class SimParams:
    """Simulation timing and infrastructure parameters."""
    control_step_s: int = 15      # Delta_t: control step (seconds)
    scrape_interval_s: int = 30   # Prometheus scrape cadence
    ready_delay_steps: int = 2    # pod startup delay in control steps
    initial_replicas: int = 2


@dataclass
class HPAParams:
    """HPA baseline configuration."""
    min_replicas: int = 2
    max_replicas: int = 12
    cpu_target: float = 0.60       # target CPU utilization
    scale_up_stab_steps: int = 0   # scale up immediately
    scale_down_stab_steps: int = 20  # 5 min / 15s = 20 steps stabilization
    scale_up_pct: float = 2.0      # max scale factor per step (200%)


# Queueing model

def md1_inflight(rps: float, n_replicas: int, mu: float) -> float:
    """M/D/1 queue: expected number of requests in system."""
    capacity = max(n_replicas * mu, 1e-9)
    rho = min(rps / capacity, 0.999)
    return rho + rho ** 2 / (2 * (1 - rho))


def observed_inflight(rps: float, n_replicas: int, ph: PhysicsParams) -> float:
    raw = md1_inflight(rps, n_replicas, ph.mu)
    cap = max(float(n_replicas) * ph.inflight_cap_per_replica, 0.0)
    return min(raw, cap)


def demand_proxy(rps: float, inflight: float, ph: PhysicsParams) -> float:
    proxy = max(rps + ph.inflight_gain * inflight, 0.0)
    if math.isfinite(ph.demand_cap_rps) and ph.demand_cap_rps > 0:
        proxy = min(proxy, ph.demand_cap_rps)
    return proxy


def md1_latency_ms(rps: float, n_replicas: int, mu: float, service_time_s: float) -> float:
    """M/D/1 mean response time in ms."""
    capacity = max(n_replicas * mu, 1e-9)
    rho = min(rps / capacity, 0.9999)
    mean_t = service_time_s * (2 - rho) / (2 * (1 - rho))
    return mean_t * 1000


def p95_latency_ms(rps: float, n_replicas: int, mu: float, service_time_s: float) -> float:
    """Approximate p95 latency from the M/D/1 mean response time."""
    capacity = max(n_replicas * mu, 1e-9)
    rho = min(rps / capacity, 0.9999)
    mean_t = service_time_s * (2 - rho) / (2 * (1 - rho))
    tail_mult = 1.1 + 1.9 * rho ** 2
    return mean_t * tail_mult * 1000


# Forecast

def es_forecast(history: list[float], horizon: int, alpha: float) -> np.ndarray:
    """Simple exponential smoothing forecast: flat extrapolation of current level."""
    if len(history) < 2:
        last = history[-1] if history else 0.0
        return np.full(horizon, max(0.0, last))
    if SM_OK and ExponentialSmoothing is not None and len(history) >= 4:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = ExponentialSmoothing(
                    history, trend=None, seasonal=None
                ).fit(smoothing_level=alpha, optimized=False)
            level = float(fit.fittedvalues.iloc[-1])
        except Exception:
            level = history[-1]
    else:
        level = history[-1]
        for v in reversed(history[:-1]):
            level = alpha * level + (1 - alpha) * v
    return np.full(horizon, max(level, history[-1], 0.0))


def solve_mpc(
    forecast: np.ndarray,
    b0: float,
    r_current: int,
    p: MPCParams,
    ph: PhysicsParams,
    dt_seconds: float,
) -> tuple[int, str]:
    return solve_backlog_mpc(
        forecast=forecast,
        b0=b0,
        r_current=r_current,
        alpha=p.alpha,
        beta=p.beta,
        gamma=p.gamma,
        capacity_per_replica=ph.mu,
        rho_star=ph.rho_star,
        min_replicas=p.min_replicas,
        max_replicas=p.max_replicas,
        max_step=p.max_step,
        dt_seconds=dt_seconds,
        fallback=lambda forecast_first, current: greedy_replica_action(
            forecast_first,
            current,
            min_replicas=p.min_replicas,
            max_replicas=p.max_replicas,
            max_step=p.max_step,
            capacity_per_replica=ph.mu,
            rho_star=ph.rho_star,
            status="greedy",
        ),
        accepted_statuses=SOLVED_STATUSES,
        normalized_objective=p.normalized_objective,
        normalization_reference_replicas=p.normalization_reference_replicas,
    )


# HPA baseline

def hpa_step(
    rps: float,
    current: int,
    ready: int,
    mu: float,
    p: HPAParams,
    scale_down_counter: int,
) -> tuple[int, int]:
    """Advance the simplified HPA controller by one step."""
    if ready <= 0:
        return p.min_replicas, scale_down_counter
    util = rps / (ready * mu)
    desired = math.ceil(ready * util / p.cpu_target)
    desired = max(p.min_replicas, min(p.max_replicas, desired))

    if desired > current:
        max_allowed = math.ceil(current * p.scale_up_pct)
        new = min(desired, max_allowed)
        new = max(p.min_replicas, min(p.max_replicas, new))
        return new, 0

    if desired < current:
        scale_down_counter += 1
        if scale_down_counter >= p.scale_down_stab_steps:
            return desired, 0
        return current, scale_down_counter

    return current, 0


# Simulation

@dataclass
class TickResult:
    step: int
    rps: float
    phase: int
    mpc_replicas_desired: int
    mpc_replicas_ready: int
    mpc_inflight: float
    mpc_demand_proxy: float
    mpc_b0: float
    mpc_rec: int
    mpc_emergency: int
    mpc_p95_ms: float
    mpc_util: float
    mpc_slo_violated: bool
    mpc_status: str
    hpa_replicas_desired: int
    hpa_replicas_ready: int
    hpa_inflight: float
    hpa_p95_ms: float
    hpa_util: float
    hpa_slo_violated: bool


def run_simulation(
    rps_trace: np.ndarray,
    phase_trace: np.ndarray,
    physics: PhysicsParams,
    mpc: MPCParams,
    safety: SafetyParams,
    sim: SimParams,
    hpa: HPAParams,
) -> list[TickResult]:
    """Simulate the MPC controller and the HPA baseline on the same trace."""
    n_steps = len(rps_trace)
    results: list[TickResult] = []

    mpc_initial = max(sim.initial_replicas, mpc.min_replicas)
    hpa_initial = max(sim.initial_replicas, hpa.min_replicas)

    mpc_desired = mpc_initial
    mpc_ready = mpc_initial
    mpc_ready_queue: list[int] = [mpc_initial] * max(0, sim.ready_delay_steps)
    mpc_b0 = 0.0
    mpc_rps_hist: list[float] = []
    mpc_prev_rps: Optional[float] = None
    mpc_last_obs_rps: float = 0.0
    mpc_last_obs_inflight: float = 0.0

    hpa_desired = hpa_initial
    hpa_ready = hpa_initial
    hpa_ready_queue: list[int] = [hpa_initial] * max(0, sim.ready_delay_steps)
    hpa_sd_counter = 0
    hpa_last_obs_rps: float = 0.0

    dt = float(sim.control_step_s)
    # Scrape cadence is driven by wall-clock seconds, not by step index.
    # Using integer step % ratio truncates non-multiple intervals
    # (e.g. scrape=30s, control=20s would scrape every step instead of every 1.5).
    scrape_interval = max(float(sim.scrape_interval_s), dt)
    next_scrape_time = 0.0

    for step in range(n_steps):
        true_rps = float(rps_trace[step])
        phase = int(phase_trace[step])

        # Advance delayed ready-replica state.
        mpc_ready = mpc_ready_queue.pop(0) if mpc_ready_queue else mpc_desired
        hpa_ready = hpa_ready_queue.pop(0) if hpa_ready_queue else hpa_desired

        # Refresh observed metrics on scrape ticks and hold them between scrapes.
        now_seconds = step * dt
        if now_seconds + 1e-9 >= next_scrape_time:
            next_scrape_time = now_seconds + scrape_interval
            scrape_tick = True
        else:
            scrape_tick = False
        if scrape_tick:
            obs_rps_mpc = true_rps
            obs_rps_hpa = true_rps
            obs_inflight_mpc = observed_inflight(true_rps, max(1, mpc_ready), physics)
            mpc_last_obs_rps = obs_rps_mpc
            mpc_last_obs_inflight = obs_inflight_mpc
            hpa_last_obs_rps = obs_rps_hpa
        else:
            obs_rps_mpc = mpc_last_obs_rps
            obs_rps_hpa = hpa_last_obs_rps
            obs_inflight_mpc = mpc_last_obs_inflight

        mpc_demand_proxy = demand_proxy(obs_rps_mpc, obs_inflight_mpc, physics)

        mpc_b0 = update_backlog(
            mpc_b0,
            mpc_demand_proxy,
            mpc_ready,
            physics.mu,
            physics.rho_star,
            dt,
        )

        mpc_rps_hist.append(mpc_demand_proxy)
        if len(mpc_rps_hist) > 60:
            mpc_rps_hist.pop(0)
        forecast = es_forecast(mpc_rps_hist, mpc.horizon, mpc.es_alpha)

        rec, status = solve_mpc(forecast, mpc_b0, mpc_desired, mpc, physics, dt)

        emergency = 0
        if obs_inflight_mpc >= safety.emergency_inflight_threshold:
            emergency = 1
            rec = min(mpc.max_replicas, max(rec, mpc_desired + safety.emergency_step))

        if (mpc_prev_rps is not None
                and safety.surge_delta_rps > 0
                and math.isfinite(safety.surge_delta_rps)
                and obs_rps_mpc - mpc_prev_rps >= safety.surge_delta_rps):
            rec = min(mpc.max_replicas, max(rec, mpc_desired + safety.surge_step))

        mpc_prev_rps = obs_rps_mpc

        if mpc_desired > mpc_ready and rec < mpc_desired:
            rec = mpc_desired

        new_mpc_desired = rec
        if sim.ready_delay_steps <= 0:
            mpc_ready = new_mpc_desired
        else:
            mpc_ready_queue.append(new_mpc_desired)
        mpc_desired = new_mpc_desired

        old_hpa_desired = hpa_desired
        hpa_desired, hpa_sd_counter = hpa_step(
            obs_rps_hpa, hpa_desired, max(1, hpa_ready), physics.mu, hpa, hpa_sd_counter
        )
        if old_hpa_desired > hpa_ready and hpa_desired < old_hpa_desired:
            hpa_desired = old_hpa_desired
        if sim.ready_delay_steps <= 0:
            hpa_ready = hpa_desired
        else:
            hpa_ready_queue.append(hpa_desired)

        mpc_ready_eff = max(1, mpc_ready)
        hpa_ready_eff = max(1, hpa_ready)

        mpc_inf = md1_inflight(true_rps, mpc_ready_eff, physics.mu)
        hpa_inf = md1_inflight(true_rps, hpa_ready_eff, physics.mu)
        mpc_p95 = p95_latency_ms(true_rps, mpc_ready_eff, physics.mu, physics.service_time_s)
        hpa_p95 = p95_latency_ms(true_rps, hpa_ready_eff, physics.mu, physics.service_time_s)
        mpc_util = true_rps / (mpc_ready_eff * physics.mu)
        hpa_util = true_rps / (hpa_ready_eff * physics.mu)

        results.append(TickResult(
            step=step, rps=true_rps, phase=phase,
            mpc_replicas_desired=mpc_desired,
            mpc_replicas_ready=mpc_ready_eff,
            mpc_inflight=mpc_inf,
            mpc_demand_proxy=mpc_demand_proxy,
            mpc_b0=mpc_b0,
            mpc_rec=rec,
            mpc_emergency=emergency,
            mpc_p95_ms=mpc_p95,
            mpc_util=mpc_util,
            mpc_slo_violated=mpc_util > physics.rho_star,
            mpc_status=status,
            hpa_replicas_desired=hpa_desired,
            hpa_replicas_ready=hpa_ready_eff,
            hpa_inflight=hpa_inf,
            hpa_p95_ms=hpa_p95,
            hpa_util=hpa_util,
            hpa_slo_violated=hpa_util > physics.rho_star,
        ))

    return results

# Summary metrics

def build_metrics(results: list[TickResult], focus_phases: set[int]) -> dict:
    """Compute aggregate metrics for all phases and for a focus subset."""
    def metrics_for(rows: list[TickResult], prefix: str) -> dict:
        if not rows:
            return {}
        mpc_reps = [r.mpc_replicas_ready for r in rows]
        hpa_reps = [r.hpa_replicas_ready for r in rows]
        mpc_V = sum(abs(mpc_reps[i] - mpc_reps[i-1]) for i in range(1, len(mpc_reps)))
        hpa_V = sum(abs(hpa_reps[i] - hpa_reps[i-1]) for i in range(1, len(hpa_reps)))
        mpc_slo = sum(1 for r in rows if r.mpc_slo_violated) / len(rows)
        hpa_slo = sum(1 for r in rows if r.hpa_slo_violated) / len(rows)
        mpc_avg = sum(mpc_reps) / len(mpc_reps)
        hpa_avg = sum(hpa_reps) / len(hpa_reps)
        mpc_p95 = float(np.quantile([r.mpc_p95_ms for r in rows], 0.95))
        hpa_p95 = float(np.quantile([r.hpa_p95_ms for r in rows], 0.95))
        mpc_emerg = sum(r.mpc_emergency for r in rows)
        return {
            f"{prefix}_mpc_V": mpc_V, f"{prefix}_hpa_V": hpa_V,
            f"{prefix}_delta_V": mpc_V - hpa_V,
            f"{prefix}_mpc_slo": mpc_slo, f"{prefix}_hpa_slo": hpa_slo,
            f"{prefix}_delta_slo": mpc_slo - hpa_slo,
            f"{prefix}_mpc_avg_rep": mpc_avg, f"{prefix}_hpa_avg_rep": hpa_avg,
            f"{prefix}_delta_avg_rep": mpc_avg - hpa_avg,
            f"{prefix}_mpc_p95": mpc_p95, f"{prefix}_hpa_p95": hpa_p95,
            f"{prefix}_delta_p95": mpc_p95 - hpa_p95,
            f"{prefix}_mpc_emergency_count": mpc_emerg,
        }

    all_metrics = metrics_for(results, "all")
    focus = [r for r in results if r.phase in focus_phases]
    focus_metrics = metrics_for(focus, "focus")
    return {**all_metrics, **focus_metrics}


# Grid search

def run_grid_search(
    traces: dict[str, tuple[np.ndarray, np.ndarray]],
    focus_phases: dict[str, set[int]],
    physics: PhysicsParams,
    sim: SimParams,
    hpa: HPAParams,
    safety: SafetyParams,
    alpha_vals: list[float],
    beta_vals: list[float],
    gamma_vals: list[float],
    horizon_vals: list[int],
    emerg_thresh_vals: list[float],
    normalized_objective: bool,
    normalization_reference_replicas: float,
    scenario_min_replicas: dict[str, int],
    mpc_max_replicas: int,
) -> list[dict]:
    """Evaluate the realistic simulator over a parameter grid."""
    import itertools
    grid = list(itertools.product(
        alpha_vals, beta_vals, gamma_vals, horizon_vals, emerg_thresh_vals
    ))
    total = len(grid) * len(traces)
    print(f"Grid: {len(grid)} param combos × {len(traces)} scenarios = {total} runs", flush=True)

    all_results: list[dict] = []
    for idx, (alpha, beta, gamma, horizon, emerg_thresh) in enumerate(grid):
        sl = SafetyParams(
            emergency_inflight_threshold=emerg_thresh,
            emergency_step=safety.emergency_step,
            surge_delta_rps=safety.surge_delta_rps,
            surge_step=safety.surge_step,
        )

        row: dict = {
            "alpha": alpha, "beta": beta, "gamma": gamma,
            "horizon": horizon, "emerg_thresh": emerg_thresh,
        }
        for scenario, (rps_arr, phase_arr) in traces.items():
            scenario_mpc = MPCParams(
                alpha=alpha,
                beta=beta,
                gamma=gamma,
                horizon=horizon,
                es_alpha=0.45,
                min_replicas=scenario_min_replicas.get(scenario, 2),
                max_replicas=mpc_max_replicas,
                max_step=2,
                normalized_objective=normalized_objective,
                normalization_reference_replicas=normalization_reference_replicas,
            )
            try:
                res = run_simulation(rps_arr, phase_arr, physics, scenario_mpc, sl, sim, hpa)
                m = build_metrics(res, focus_phases.get(scenario, {2}))
                for k, v in m.items():
                    row[f"{scenario}_{k}"] = v
            except Exception as exc:
                row[f"{scenario}_error"] = str(exc)

        all_results.append(row)
        if (idx + 1) % 20 == 0:
            print(f"  {idx+1}/{len(grid)} done...", flush=True)

    return all_results


# CLI

def load_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load demand values and phase labels from CSV."""
    rps_list, phase_list = [], []
    with path.open() as f:
        for row in csv.DictReader(f):
            rps_list.append(float(row["rps"]))
            phase_list.append(int(row.get("phase_idx", 0)))
    return np.array(rps_list), np.array(phase_list)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scenario", choices=("spike", "step", "seasonality", "core", "all"),
                   default="core",
                   help="core=spike+step only; all=spike+step+seasonality")
    p.add_argument("--mu", type=float, default=25.0)
    p.add_argument("--rho-star", type=float, default=0.70)
    p.add_argument("--inflight-gain", type=float, default=4.0)
    p.add_argument("--inflight-cap-per-replica", type=float, default=2.0)
    p.add_argument("--demand-cap-rps", type=float, default=400.0)
    p.add_argument("--service-time-ms", type=float, default=23.0)
    p.add_argument("--control-step", type=int, default=15)
    p.add_argument("--scrape-interval", type=int, default=30)
    p.add_argument("--ready-delay-steps", type=int, default=2)
    p.add_argument("--initial-replicas", type=int, default=2)
    p.add_argument("--step-min-replicas", type=int, default=2)
    p.add_argument("--spike-min-replicas", type=int, default=6)
    p.add_argument("--seasonality-min-replicas", type=int, default=2)
    p.add_argument("--mpc-max-replicas", type=int, default=12)
    p.add_argument("--hpa-max-replicas", type=int, default=12)
    p.add_argument(
        "--normalized-objective",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use normalized QP objective terms.",
    )
    p.add_argument("--normalization-reference-replicas", type=float, default=12.0)
    p.add_argument("--trace-dir", default=str(default_trace_dir()))
    p.add_argument("--out-csv", default="analysis/out/offline/realistic_grid_results.csv")
    # Grid ranges
    p.add_argument("--alpha-vals", default="5,10,20,40,80")
    p.add_argument("--beta-vals", default="0.3,0.5,1.0,2.0")   # β<0.3 excluded: too little smoothness penalty
    p.add_argument("--gamma-vals", default="0.02,0.05,0.10")   # γ>0.10 excluded: too greedy on replicas
    p.add_argument("--horizon-vals", default="6,8,10")
    p.add_argument("--emerg-thresh-vals", default="20,30,40,60")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    physics = PhysicsParams(
        mu=args.mu,
        service_time_s=args.service_time_ms / 1000,
        rho_star=args.rho_star,
        inflight_gain=args.inflight_gain,
        inflight_cap_per_replica=args.inflight_cap_per_replica,
        demand_cap_rps=args.demand_cap_rps,
    )
    sim = SimParams(
        control_step_s=args.control_step,
        scrape_interval_s=args.scrape_interval,
        ready_delay_steps=args.ready_delay_steps,
        initial_replicas=args.initial_replicas,
    )
    hpa = HPAParams(
        min_replicas=2,
        max_replicas=args.hpa_max_replicas,
        cpu_target=0.60,
        scale_up_stab_steps=0,
        scale_down_stab_steps=20,
    )
    safety = SafetyParams(
        emergency_inflight_threshold=40.0,
        emergency_step=4,
        surge_delta_rps=1e9,
        surge_step=2,
    )

    data_dir = Path(args.trace_dir)
    scenario_files = {
        "spike":       data_dir / "baseline_spike_profile_dt15.csv",
        "step":        data_dir / "baseline_step_profile_dt15.csv",
    }
    if (data_dir / "baseline_seasonality_profile_dt15.csv").exists():
        scenario_files["seasonality"] = data_dir / "baseline_seasonality_profile_dt15.csv"

    if args.scenario == "core":
        scenario_files = {k: v for k, v in scenario_files.items() if k in ("spike", "step")}
    elif args.scenario != "all":
        scenario_files = {k: v for k, v in scenario_files.items() if k == args.scenario}

    traces = {name: load_trace(path) for name, path in scenario_files.items()}
    focus_phases = {"spike": {2}, "step": {2}, "seasonality": {2, 3, 4}}
    scenario_min_replicas = {
        "step": args.step_min_replicas,
        "spike": args.spike_min_replicas,
        "seasonality": args.seasonality_min_replicas,
    }

    alpha_vals   = [float(x) for x in args.alpha_vals.split(",")]
    beta_vals    = [float(x) for x in args.beta_vals.split(",")]
    gamma_vals   = [float(x) for x in args.gamma_vals.split(",")]
    horizon_vals = [int(x)   for x in args.horizon_vals.split(",")]
    emerg_thresh = [float(x) for x in args.emerg_thresh_vals.split(",")]

    results = run_grid_search(
        traces=traces,
        focus_phases=focus_phases,
        physics=physics,
        sim=sim,
        hpa=hpa,
        safety=safety,
        alpha_vals=alpha_vals,
        beta_vals=beta_vals,
        gamma_vals=gamma_vals,
        horizon_vals=horizon_vals,
        emerg_thresh_vals=emerg_thresh,
        normalized_objective=args.normalized_objective,
        normalization_reference_replicas=args.normalization_reference_replicas,
        scenario_min_replicas=scenario_min_replicas,
        mpc_max_replicas=args.mpc_max_replicas,
    )

    # Filter out clearly impractical settings before ranking.
    def passes(r: dict) -> bool:
        spk_dslo = r.get("spike_focus_delta_slo", r.get("spike_all_delta_slo", 1e9))
        spk_dav  = r.get("spike_focus_delta_avg_rep", r.get("spike_all_delta_avg_rep", 1e9))
        spk_hav  = r.get("spike_focus_hpa_avg_rep", r.get("spike_all_hpa_avg_rep", 1.0))
        if spk_dslo > 0.01:
            return False
        if spk_dav > 0.15 * spk_hav:
            return False
        stp_dslo = r.get("step_focus_delta_slo", r.get("step_all_delta_slo", 1e9))
        stp_dav  = r.get("step_focus_delta_avg_rep", r.get("step_all_delta_avg_rep", 1e9))
        stp_hav  = r.get("step_focus_hpa_avg_rep", r.get("step_all_hpa_avg_rep", 1.0))
        if stp_dslo > 0.02:
            return False
        if stp_dav > 0.15 * stp_hav:
            return False
        return True

    good = [r for r in results if passes(r)]
    print(f"\nConfigs passing feasibility filter: {len(good)} / {len(results)}")

    def core_sort_key(r: dict) -> float:
        stp_dv   = r.get("step_focus_delta_V",       r.get("step_all_delta_V",       0))
        stp_dslo = r.get("step_focus_delta_slo",     r.get("step_all_delta_slo",     0))
        stp_dav  = r.get("step_focus_delta_avg_rep", r.get("step_all_delta_avg_rep", 0))
        return 6.0 * stp_dslo + 1.0 * stp_dv + 2.0 * stp_dav

    good.sort(key=core_sort_key)
    best_pool = good if good else sorted(results, key=core_sort_key)

    def j_score(r: dict) -> float:
        seas_dslo = r.get("seasonality_focus_delta_slo", 0.0)
        seas_dv = r.get("seasonality_focus_delta_V", 0.0)
        stp_dslo = r.get("step_focus_delta_slo", r.get("step_all_delta_slo", 0.0))
        stp_dv = r.get("step_focus_delta_V", r.get("step_all_delta_V", 0.0))
        stp_dav = r.get(
            "step_focus_delta_avg_rep", r.get("step_all_delta_avg_rep", 0.0)
        )
        return 10.0 * seas_dslo + 6.0 * stp_dslo + 1.0 * seas_dv + 1.0 * stp_dv + 2.0 * stp_dav

    TOP_K = 30
    seasonality_path = data_dir / "baseline_seasonality_profile_dt15.csv"
    if args.scenario == "core" and seasonality_path.exists():
        print(f"\nSecond-pass: validating top {TOP_K} configs against seasonality...", flush=True)
        seas_trace = load_trace(seasonality_path)
        seas_focus = {2, 3, 4}
        top_candidates = best_pool[:TOP_K]
        for r in top_candidates:
            mpc_p = MPCParams(
                alpha=r["alpha"], beta=r["beta"], gamma=r["gamma"],
                horizon=int(r["horizon"]), es_alpha=0.45,
                min_replicas=scenario_min_replicas.get("seasonality", 2),
                max_replicas=args.mpc_max_replicas, max_step=2,
                normalized_objective=args.normalized_objective,
                normalization_reference_replicas=args.normalization_reference_replicas,
            )
            saf_p = SafetyParams(emergency_inflight_threshold=r["emerg_thresh"])
            try:
                ticks = run_simulation(seas_trace[0], seas_trace[1], physics, mpc_p, saf_p, sim, hpa)
                m = build_metrics(ticks, seas_focus)
                for k, v in m.items():
                    r[f"seasonality_{k}"] = v
            except Exception as exc:
                r["seasonality_error"] = str(exc)

        top_candidates.sort(key=j_score)
        best_pool = top_candidates
        traces_display = list(traces.keys()) + ["seasonality"]
    else:
        traces_display = list(traces.keys())

    print("\n--- Gold pool check (spike Δslo≤0, step ΔV≤+2, seas Δslo<0, Δavg≤15%) ---")
    def is_gold(r: dict) -> bool:
        if r.get("spike_focus_delta_slo", 1) > 0:
            return False
        if r.get("step_focus_delta_V", 99) > 2:
            return False
        if r.get("seasonality_focus_delta_slo", 1) >= 0:
            return False
        stp_hav = r.get("step_focus_hpa_avg_rep", 1.0)
        if r.get("step_focus_delta_avg_rep", 99) > 0.15 * stp_hav:
            return False
        return True
    gold = [r for r in best_pool if is_gold(r)]
    if gold:
        print(f"  GOLD pool size: {len(gold)}")
    else:
        print("  No gold configs. Checking silver (step ΔV≤+2 OR seas Δslo<0)...")
        silver = [r for r in best_pool if
                  r.get("step_focus_delta_V", 99) <= 2 or
                  r.get("seasonality_focus_delta_slo", 1) < 0]
        print(f"  Silver pool size: {len(silver)}")

    print(f"\n=== TOP 15 CONFIGS (J-score: 10·Δslo_seas + 6·Δslo_step + ΔV_seas + ΔV_step + 2·Δr̄) ===")
    hdr = f"{'α':>5} {'β':>4} {'γ':>5} {'H':>2} {'ET':>4}  {'J':>7}"
    for sc in traces_display:
        hdr += f" | {sc[:4]:>4} ΔV  Δslo"
    print(hdr)
    print("-" * len(hdr))
    for r in best_pool[:15]:
        j = j_score(r) if "seasonality_focus_delta_slo" in r else core_sort_key(r)
        line = f"{r['alpha']:>5.0f} {r['beta']:>4.2f} {r['gamma']:>5.3f} {r['horizon']:>2.0f} {r['emerg_thresh']:>4.0f}  {j:>+7.2f}"
        for sc in traces_display:
            if sc == "seasonality":
                dv   = r.get("seasonality_focus_delta_V",  float("nan"))
                dslo = r.get("seasonality_focus_delta_slo", float("nan"))
            else:
                dv   = r.get(f"{sc}_focus_delta_V",  r.get(f"{sc}_all_delta_V",  float("nan")))
                dslo = r.get(f"{sc}_focus_delta_slo", r.get(f"{sc}_all_delta_slo", float("nan")))
            line += f" | {dv:>+6.1f} {dslo:>+6.3f}"
        print(line)

    if best_pool:
        best = best_pool[0]
        print(f"\n=== BEST CONFIG ===")
        print(f"  alpha={best['alpha']:.0f}  beta={best['beta']:.2f}  "
              f"gamma={best['gamma']:.3f}  horizon={best['horizon']:.0f}  "
              f"emergency_threshold={best['emerg_thresh']:.0f}")

    out = resolve_output_path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    if results:
        all_keys: list[str] = []
        seen: set[str] = set()
        for row in results:
            for k in row:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved: {out}")


if __name__ == "__main__":
    main()
