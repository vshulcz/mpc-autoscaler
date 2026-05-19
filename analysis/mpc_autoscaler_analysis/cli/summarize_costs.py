"""Summarize latency/resource/cost for HPA grid and Hybrid runs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from mpc_autoscaler_analysis.artifacts import CostSummaryOptions, summarize_costs

COST_FIELDNAMES = [
    "provider",
    "currency",
    "controller",
    "target",
    "scenario",
    "run_dir",
    "duration_s",
    "avg_replicas",
    "max_replicas",
    "replica_variation",
    "vcpu_hours",
    "mem_gib_hours",
    "cost",
    "cost_per_hour",
    "focus_p95_ms",
    "focus_p99_ms",
    "success_pct",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hpa-root", action="append", default=[], help="HPA root containing target_<n> dirs.")
    p.add_argument("--hybrid-root", action="append", default=[], help="Hybrid root containing scenario dirs.")
    p.add_argument("--out-csv", required=True)
    p.add_argument("--out-aggregate-csv", required=True)
    p.add_argument("--yandex-vcpu-hour-rub", type=float, default=0.0)
    p.add_argument("--yandex-memory-gib-hour-rub", type=float, default=0.0)
    return p.parse_args()


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    rows, agg_rows = summarize_costs(
        CostSummaryOptions(
            hpa_roots=tuple(Path(p) for p in args.hpa_root),
            hybrid_roots=tuple(Path(p) for p in args.hybrid_root),
            yandex_vcpu_hour_rub=args.yandex_vcpu_hour_rub,
            yandex_memory_gib_hour_rub=args.yandex_memory_gib_hour_rub,
        )
    )

    out_csv = Path(args.out_csv)
    out_agg = Path(args.out_aggregate_csv)
    write_rows(out_csv, rows, COST_FIELDNAMES)
    out_agg.parent.mkdir(parents=True, exist_ok=True)
    with out_agg.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(agg_rows[0].keys()) if agg_rows else [])
        if agg_rows:
            writer.writeheader()
            writer.writerows(agg_rows)

    print(f"Wrote cost rows: {out_csv}")
    print(f"Wrote aggregate rows: {out_agg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
