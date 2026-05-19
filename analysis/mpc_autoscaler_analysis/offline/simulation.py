#!/usr/bin/env python3
"""Compare an HPA-like baseline with the offline MPC controller."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from mpc_autoscaler_analysis.mpc import (
    clamp_int,
    greedy_replica_action,
    solve_backlog_mpc,
    update_backlog,
)

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except Exception:  # pragma: no cover - optional dependency at runtime
    ExponentialSmoothing = None  # type: ignore[assignment]

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - optional dependency at runtime
    plt = None  # type: ignore[assignment]


SOLVED_STATUSES = {"optimal", "optimal_inaccurate"}


@dataclass
class SimConfig:
    """Configuration shared by the offline simulator and summary builder."""

    forecast: str
    horizon: int
    history_window: int
    es_alpha: float

    # System model.
    capacity_per_replica: float  # mu: effective throughput per replica (RPS)
    rho_star: float              # rho*: target utilization level

    # MPC objective weights (unnormalized form).
    alpha: float  # backlog penalty weight
    beta: float   # smoothness penalty weight
    gamma: float  # capacity cost weight

    # Shared replica bounds and step limits.
    min_replicas: int
    max_replicas: int
    max_step: int        # Delta_max: max replica change per step
    initial_replicas: int

    # HPA-like controller parameters.
    hpa_target: float
    hpa_scale_down_hold_steps: int

    # Time step.
    dt_seconds: int  # Delta_t

    normalized_objective: bool = True
    normalization_reference_replicas: float = 12.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-csv", required=True, help="Input trace CSV path")
    parser.add_argument(
        "--rps-column",
        default="rps",
        help="Column name with input demand in RPS",
    )
    parser.add_argument(
        "--time-column",
        default="",
        help="Optional time column from input CSV",
    )
    parser.add_argument("--out-dir", required=True, help="Output directory path")

    parser.add_argument("--forecast", choices=("es", "hw"), default="es")
    parser.add_argument("--horizon", type=int, default=8)
    parser.add_argument("--history-window", type=int, default=60)
    parser.add_argument("--es-alpha", type=float, default=0.35)

    parser.add_argument("--capacity-per-replica", type=float, default=25.0)
    parser.add_argument("--rho-star", type=float, default=0.70)

    parser.add_argument("--alpha", type=float, default=15.0)
    parser.add_argument("--beta", type=float, default=4.0)
    parser.add_argument("--gamma", type=float, default=0.08)

    parser.add_argument("--min-replicas", type=int, default=2)
    parser.add_argument("--max-replicas", type=int, default=12)
    parser.add_argument("--max-step", type=int, default=2)
    parser.add_argument("--initial-replicas", type=int, default=2)

    parser.add_argument("--hpa-target", type=float, default=0.60)
    parser.add_argument("--hpa-scale-down-hold-steps", type=int, default=5)
    parser.add_argument("--dt-seconds", type=int, default=15)
    parser.add_argument(
        "--normalized-objective",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use normalized QP objective terms.",
    )
    parser.add_argument("--normalization-reference-replicas", type=float, default=12.0)
    return parser.parse_args()


def build_forecast(history: np.ndarray, cfg: SimConfig) -> np.ndarray:
    if cfg.forecast == "es":
        return forecast_es(history, cfg.horizon, cfg.es_alpha)
    return forecast_hw(history, cfg.horizon, cfg.es_alpha)


def forecast_es(history: np.ndarray, horizon: int, alpha: float) -> np.ndarray:
    if history.size == 0:
        return np.zeros(horizon, dtype=float)
    level = float(history[0])
    for x in history[1:]:
        level = alpha * float(x) + (1.0 - alpha) * level
    return np.full(horizon, max(level, 0.0), dtype=float)


def forecast_hw(history: np.ndarray, horizon: int, alpha_fallback: float) -> np.ndarray:
    if history.size < 6 or ExponentialSmoothing is None:
        return forecast_es(history, horizon, alpha_fallback)
    try:
        model = ExponentialSmoothing(
            history.astype(float),
            trend="add",
            damped_trend=True,
            seasonal=None,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True)
        pred = np.asarray(fit.forecast(horizon), dtype=float)
        return np.maximum(pred, 0.0)
    except Exception:
        return forecast_es(history, horizon, alpha_fallback)


def hpa_like_action(
    demand_rps: float,
    replicas_prev: int,
    down_hold_counter: int,
    cfg: SimConfig,
) -> Tuple[int, int]:
    denom = max(cfg.capacity_per_replica * cfg.hpa_target, 1e-9)
    desired = int(math.ceil(max(demand_rps, 0.0) / denom))
    desired = clamp_int(desired, cfg.min_replicas, cfg.max_replicas)

    delta = desired - replicas_prev
    if delta > cfg.max_step:
        desired = replicas_prev + cfg.max_step
    elif delta < -cfg.max_step:
        desired = replicas_prev - cfg.max_step

    if desired < replicas_prev:
        if down_hold_counter < cfg.hpa_scale_down_hold_steps:
            return replicas_prev, down_hold_counter + 1
        return desired, 0
    if desired > replicas_prev:
        return desired, 0
    return desired, down_hold_counter


def fallback_mpc_action(
    forecast_first: float, r_current: int, cfg: SimConfig
) -> Tuple[int, str]:
    """Fallback used when the QP solver cannot produce a usable result."""
    return greedy_replica_action(
        forecast_first,
        r_current,
        min_replicas=cfg.min_replicas,
        max_replicas=cfg.max_replicas,
        max_step=cfg.max_step,
        capacity_per_replica=cfg.capacity_per_replica,
        rho_star=cfg.rho_star,
        status="fallback",
    )


def solve_mpc_action(
    forecast: np.ndarray,
    b0: float,
    r_current: int,
    cfg: SimConfig,
) -> Tuple[int, str]:
    """Solve one offline MPC step."""
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
        fallback=lambda forecast_first, current: fallback_mpc_action(
            forecast_first, current, cfg
        ),
        accepted_statuses=SOLVED_STATUSES,
        normalized_objective=cfg.normalized_objective,
        normalization_reference_replicas=cfg.normalization_reference_replicas,
    )


def utilization(demand_rps: float, replicas: int, cfg: SimConfig) -> float:
    cap = max(cfg.capacity_per_replica * max(replicas, 1), 1e-9)
    return max(demand_rps, 0.0) / cap


def overflow_replicas(demand_rps: float, replicas: int, cfg: SimConfig) -> float:
    """Return how many more replicas would be needed to satisfy demand at `rho_star`."""
    req = max(demand_rps, 0.0) / max(cfg.capacity_per_replica * cfg.rho_star, 1e-9)
    return max(0.0, req - replicas)


def run_simulation(trace_rps: np.ndarray, cfg: SimConfig) -> pd.DataFrame:
    """Simulate both policies over a demand trace and return the trajectory."""
    rows = []
    replicas_hpa = cfg.initial_replicas
    replicas_mpc = cfg.initial_replicas
    down_hold_counter = 0
    b0_mpc = 0.0

    dt = float(cfg.dt_seconds)
    mu = cfg.capacity_per_replica
    rho_star = cfg.rho_star

    for t in range(trace_rps.size):
        demand = float(max(trace_rps[t], 0.0))
        active_hpa = replicas_hpa
        active_mpc = replicas_mpc

        b0_mpc = update_backlog(b0_mpc, demand, active_mpc, mu, rho_star, dt)

        hist_start = max(0, t - cfg.history_window + 1)
        history = trace_rps[hist_start : t + 1]
        forecast = build_forecast(history, cfg)
        forecast_t0 = float(forecast[0]) if forecast.size else 0.0

        next_replicas_hpa, down_hold_counter = hpa_like_action(
            demand_rps=demand,
            replicas_prev=active_hpa,
            down_hold_counter=down_hold_counter,
            cfg=cfg,
        )

        next_replicas_mpc, mpc_status = solve_mpc_action(
            forecast=forecast,
            b0=b0_mpc,
            r_current=active_mpc,
            cfg=cfg,
        )

        rows.append(
            {
                "step": t,
                "demand_rps": demand,
                "forecast_rps_t0": forecast_t0,
                "mpc_b0": b0_mpc,
                "hpa_replicas": active_hpa,
                "mpc_replicas": active_mpc,
                "hpa_recommended_replicas": next_replicas_hpa,
                "mpc_recommended_replicas": next_replicas_mpc,
                "hpa_utilization": utilization(demand, active_hpa, cfg),
                "mpc_utilization": utilization(demand, active_mpc, cfg),
                "hpa_overflow_replicas": overflow_replicas(demand, active_hpa, cfg),
                "mpc_overflow_replicas": overflow_replicas(demand, active_mpc, cfg),
                "mpc_status": mpc_status,
            }
        )

        replicas_hpa = next_replicas_hpa
        replicas_mpc = next_replicas_mpc

    return pd.DataFrame(rows)


def build_summary(df: pd.DataFrame, cfg: SimConfig) -> dict:
    """Build aggregate metrics for the HPA-like baseline and the MPC run."""

    def metrics(prefix: str) -> dict:
        reps = df[f"{prefix}_replicas"].to_numpy(dtype=float)
        utils = df[f"{prefix}_utilization"].to_numpy(dtype=float)
        overflow = df[f"{prefix}_overflow_replicas"].to_numpy(dtype=float)

        if reps.size > 1:
            variation = float(np.sum(np.abs(np.diff(reps))))
        else:
            variation = 0.0

        return {
            "avg_replicas": float(np.mean(reps)),
            "max_replicas": int(np.max(reps)),
            "replica_variation_sum_abs_delta": variation,
            "utilization_mean": float(np.mean(utils)),
            "utilization_p95": float(np.quantile(utils, 0.95)),
            "slo_violation_ratio": float(np.mean(utils > cfg.rho_star)),
            "overflow_mean_replicas": float(np.mean(overflow)),
            "overflow_p95_replicas": float(np.quantile(overflow, 0.95)),
        }

    hpa = metrics("hpa")
    mpc = metrics("mpc")

    b0_series = df["mpc_b0"].to_numpy(dtype=float)
    mpc_backlog = {
        "b0_mean": float(np.mean(b0_series)),
        "b0_p95": float(np.quantile(b0_series, 0.95)),
        "b0_max": float(np.max(b0_series)),
    }

    return {
        "config": asdict(cfg),
        "n_points": int(df.shape[0]),
        "hpa": hpa,
        "mpc": mpc,
        "mpc_backlog": mpc_backlog,
        "delta_mpc_minus_hpa": {
            "avg_replicas": mpc["avg_replicas"] - hpa["avg_replicas"],
            "replica_variation_sum_abs_delta": (
                mpc["replica_variation_sum_abs_delta"]
                - hpa["replica_variation_sum_abs_delta"]
            ),
            "slo_violation_ratio": mpc["slo_violation_ratio"]
            - hpa["slo_violation_ratio"],
            "overflow_mean_replicas": mpc["overflow_mean_replicas"]
            - hpa["overflow_mean_replicas"],
        },
    }


def render_plot(df: pd.DataFrame, out_path: Path, cfg: SimConfig) -> None:
    """Render a summary plot if matplotlib is available."""
    if plt is None:
        return

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    x = df["step"].to_numpy()

    axes[0].plot(x, df["demand_rps"], label="Demand RPS", color="tab:blue")
    axes[0].plot(
        x, df["forecast_rps_t0"], label="Forecast(t+1)", color="tab:cyan", alpha=0.7
    )
    axes[0].set_ylabel("RPS")
    axes[0].legend(loc="upper right")
    axes[0].grid(alpha=0.3)

    axes[1].plot(x, df["hpa_replicas"], label="HPA-like", color="tab:orange")
    axes[1].plot(x, df["mpc_replicas"], label="MPC", color="tab:green")
    axes[1].set_ylabel("Replicas")
    axes[1].legend(loc="upper right")
    axes[1].grid(alpha=0.3)

    axes[2].plot(x, df["hpa_utilization"], label="HPA-like util", color="tab:red")
    axes[2].plot(x, df["mpc_utilization"], label="MPC util", color="tab:purple")
    axes[2].axhline(
        cfg.rho_star, linestyle="--", color="black", linewidth=1.0, label="rho_star"
    )
    axes[2].set_ylabel("Utilization")
    axes[2].legend(loc="upper right")
    axes[2].grid(alpha=0.3)

    axes[3].plot(x, df["mpc_b0"], label="MPC backlog b0", color="tab:brown")
    axes[3].set_ylabel("Backlog (RPS·s)")
    axes[3].set_xlabel("Step")
    axes[3].legend(loc="upper right")
    axes[3].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> None:
    args = parse_args()

    in_path = Path(args.trace_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    src = pd.read_csv(in_path)
    if args.rps_column not in src.columns:
        available = ", ".join(src.columns)
        raise ValueError(
            f"Column '{args.rps_column}' is missing in {in_path}. Available columns: {available}"
        )

    trace = src[args.rps_column].astype(float).to_numpy()
    cfg = SimConfig(
        forecast=args.forecast,
        horizon=args.horizon,
        history_window=args.history_window,
        es_alpha=args.es_alpha,
        capacity_per_replica=args.capacity_per_replica,
        rho_star=args.rho_star,
        alpha=args.alpha,
        beta=args.beta,
        gamma=args.gamma,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
        max_step=args.max_step,
        initial_replicas=args.initial_replicas,
        hpa_target=args.hpa_target,
        hpa_scale_down_hold_steps=args.hpa_scale_down_hold_steps,
        dt_seconds=args.dt_seconds,
        normalized_objective=args.normalized_objective,
        normalization_reference_replicas=args.normalization_reference_replicas,
    )

    sim_df = run_simulation(trace, cfg)
    if args.time_column and args.time_column in src.columns:
        sim_df.insert(1, args.time_column, src[args.time_column])
    elif "timestamp_s" in src.columns:
        sim_df.insert(1, "timestamp_s", src["timestamp_s"])
    else:
        sim_df.insert(1, "timestamp_s", sim_df["step"] * cfg.dt_seconds)

    trajectory_path = out_dir / "trajectory.csv"
    summary_path = out_dir / "summary.json"
    plot_path = out_dir / "trajectory.png"

    sim_df.to_csv(trajectory_path, index=False)
    summary = build_summary(sim_df, cfg)
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2))
    render_plot(sim_df, plot_path, cfg)

    print(f"Input trace: {in_path}")
    print(f"Saved trajectory: {trajectory_path}")
    print(f"Saved summary: {summary_path}")
    if plot_path.exists():
        print(f"Saved plot: {plot_path}")
    else:
        print("Plot was skipped (matplotlib not available)")


if __name__ == "__main__":
    main()
