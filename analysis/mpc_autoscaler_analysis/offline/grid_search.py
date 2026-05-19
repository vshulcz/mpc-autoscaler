#!/usr/bin/env python3
"""Run a small grid search for the offline MPC parameters."""

from __future__ import annotations

import argparse
import csv
import itertools
import warnings
from pathlib import Path

import numpy as np

from mpc_autoscaler_analysis.offline.simulation import SimConfig, build_summary, run_simulation
from mpc_autoscaler_analysis.paths import default_trace_dir, resolve_output_path

warnings.filterwarnings("ignore", message=".*Solution may be inaccurate.*")

# Search space used in the thesis experiments.
ALPHA_VALUES = [5.0, 10.0, 20.0, 40.0, 80.0]
BETA_VALUES = [0.1, 0.3, 0.5, 1.0, 2.0]
GAMMA_VALUES = [0.02, 0.05, 0.10, 0.20]
HORIZON_VALUES = [6, 8, 10]

# Shared model parameters.
CAPACITY_PER_REPLICA = 25.0
RHO_STAR = 0.70
ES_ALPHA = 0.45
MAX_STEP = 2
MIN_REPLICAS = 2
MAX_REPLICAS = 12
INITIAL_REPLICAS = 2
HISTORY_WINDOW = 60
DT_SECONDS = 15
HPA_TARGET = 0.60
HPA_SCALE_DOWN_HOLD = 5


def load_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a demand trace and phase labels from CSV."""
    rps_list, phase_list = [], []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            rps_list.append(float(row["rps"]))
            phase_list.append(int(row.get("phase_idx", 0)))
    return np.array(rps_list), np.array(phase_list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", default=str(default_trace_dir()))
    parser.add_argument("--out-csv", default="analysis/out/offline/grid_search_results.csv")
    return parser.parse_args()


def score(summary: dict) -> dict:
    """Extract scalar metrics from build_summary output."""
    delta = summary["delta_mpc_minus_hpa"]
    mpc   = summary["mpc"]
    hpa   = summary["hpa"]
    return {
        "delta_V":   delta["replica_variation_sum_abs_delta"],
        "delta_slo": delta["slo_violation_ratio"],
        "delta_avg_rep": delta["avg_replicas"],
        "mpc_V":     mpc["replica_variation_sum_abs_delta"],
        "hpa_V":     hpa["replica_variation_sum_abs_delta"],
        "mpc_slo":   mpc["slo_violation_ratio"],
        "hpa_slo":   hpa["slo_violation_ratio"],
        "mpc_avg":   mpc["avg_replicas"],
        "hpa_avg":   hpa["avg_replicas"],
    }


def metric(row: dict[str, object], key: str, default: float) -> float:
    value = row.get(key, default)
    if isinstance(value, (int, float, str)):
        return float(value)
    return default


def main() -> None:
    args = parse_args()
    trace_dir = Path(args.trace_dir)
    trace_paths = {
        "spike": trace_dir / "baseline_spike_profile_dt15.csv",
        "step": trace_dir / "baseline_step_profile_dt15.csv",
    }

    print("Loading traces...")
    traces = {name: load_trace(path) for name, path in trace_paths.items()}

    grid = list(itertools.product(ALPHA_VALUES, BETA_VALUES, GAMMA_VALUES, HORIZON_VALUES))
    total = len(grid)
    print(f"Grid size: {total} combinations × {len(trace_paths)} scenarios = {total * len(trace_paths)} runs\n")

    results: list[dict[str, object]] = []

    for idx, (alpha, beta, gamma, horizon) in enumerate(grid):
        row: dict[str, object] = {
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "horizon": horizon,
        }

        for scenario, (rps_arr, _) in traces.items():
            cfg = SimConfig(
                forecast="es",
                horizon=horizon,
                history_window=HISTORY_WINDOW,
                es_alpha=ES_ALPHA,
                capacity_per_replica=CAPACITY_PER_REPLICA,
                rho_star=RHO_STAR,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
                min_replicas=MIN_REPLICAS,
                max_replicas=MAX_REPLICAS,
                max_step=MAX_STEP,
                initial_replicas=INITIAL_REPLICAS,
                hpa_target=HPA_TARGET,
                hpa_scale_down_hold_steps=HPA_SCALE_DOWN_HOLD,
                dt_seconds=DT_SECONDS,
            )
            try:
                df = run_simulation(rps_arr, cfg)
                summary = build_summary(df, cfg)
                s = score(summary)
            except Exception as exc:
                s: dict[str, object] = {
                    k: float("nan")
                    for k in [
                        "delta_V",
                        "delta_slo",
                        "delta_avg_rep",
                        "mpc_V",
                        "hpa_V",
                        "mpc_slo",
                        "hpa_slo",
                        "mpc_avg",
                        "hpa_avg",
                    ]
                }
                s["error"] = str(exc)

            for k, v in s.items():
                row[f"{scenario}_{k}"] = v

        results.append(row)
        if (idx + 1) % 50 == 0:
            print(f"  {idx+1}/{total} done...")

    print(f"\nDone. {len(results)} results.\n")

    # Keep configurations that do not regress churn, SLO violations, or average replicas.
    def passes(r: dict[str, object]) -> bool:
        for sc in ("spike", "step"):
            if metric(r, f"{sc}_delta_V", 1) > 0:
                return False
            if metric(r, f"{sc}_delta_slo", 1) > 1e-6:
                return False
            hpa_avg = metric(r, f"{sc}_hpa_avg", 1)
            if metric(r, f"{sc}_delta_avg_rep", 1) > 0.15 * hpa_avg:
                return False
        return True

    good = [r for r in results if passes(r)]
    print(f"Configs passing all criteria: {len(good)} / {total}")

    good.sort(key=lambda r: metric(r, "spike_delta_V", 0) + metric(r, "step_delta_V", 0))

    header = f"{'α':>6} {'β':>5} {'γ':>5} {'H':>3} | "
    header += f"{'spk ΔV':>8} {'spk Δslo':>9} {'spk mV':>7} {'spk hV':>7} | "
    header += f"{'stp ΔV':>8} {'stp Δslo':>9} {'stp mV':>7} {'stp hV':>7}"
    print(header)
    print("-" * len(header))

    for r in good[:20]:
        line = f"{r['alpha']:>6.0f} {r['beta']:>5.2f} {r['gamma']:>5.3f} {r['horizon']:>3} | "
        line += f"{r['spike_delta_V']:>+8.1f} {r['spike_delta_slo']:>+9.4f} {r['spike_mpc_V']:>7.1f} {r['spike_hpa_V']:>7.1f} | "
        line += f"{r['step_delta_V']:>+8.1f} {r['step_delta_slo']:>+9.4f} {r['step_mpc_V']:>7.1f} {r['step_hpa_V']:>7.1f}"
        print(line)

    if not good:
        print("\nNo config passes all criteria. Top 20 by combined ΔV (all results):")
        results.sort(
            key=lambda r: metric(r, "spike_delta_V", 99) + metric(r, "step_delta_V", 99)
        )
        for r in results[:20]:
            line = f"α={r['alpha']:>5.0f} β={r['beta']:>4.2f} γ={r['gamma']:>5.3f} H={r['horizon']} | "
            line += f"spk ΔV={r.get('spike_delta_V',float('nan')):>+6.1f} Δslo={r.get('spike_delta_slo',float('nan')):>+7.4f} | "
            line += f"stp ΔV={r.get('step_delta_V',float('nan')):>+6.1f} Δslo={r.get('step_delta_slo',float('nan')):>+7.4f}"
            print(line)

    out_csv = resolve_output_path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if results:
        fieldnames = list(results[0].keys())
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nFull results saved to: {out_csv}")


if __name__ == "__main__":
    main()
