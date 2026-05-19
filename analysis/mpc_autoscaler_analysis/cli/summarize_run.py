"""Summarize online MPC run artifacts from a run directory."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from mpc_autoscaler_analysis.artifacts import parse_phase_metrics, summarize_control_log

PHASE_FIELDNAMES = [
    "phase",
    "throughput_rps",
    "p95",
    "p99",
    "max",
    "success_ratio_pct",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True, help="Run directory path.")
    p.add_argument("--out-phase-csv", required=True, help="Output phase summary CSV.")
    p.add_argument(
        "--out-control-csv",
        default="",
        help="Output control summary CSV (if mpc-control-log.csv exists).",
    )
    return p.parse_args()


def write_phase_summary(run_dir: Path, out_phase: Path) -> None:
    report_path = run_dir / "incluster-report.txt"
    if not report_path.exists():
        raise SystemExit(f"Missing report: {report_path}")

    phase_rows = parse_phase_metrics(report_path.read_text(encoding="utf-8"))
    out_phase.parent.mkdir(parents=True, exist_ok=True)
    with out_phase.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PHASE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(phase_rows)
    print(f"Wrote phase summary: {out_phase}")


def write_control_summary(run_dir: Path, out_control: Path) -> None:
    log_path = run_dir / "mpc-control-log.csv"
    out_control.parent.mkdir(parents=True, exist_ok=True)
    control_rows: list[dict[str, str]] = []
    if log_path.exists():
        with log_path.open("r", encoding="utf-8", newline="") as f:
            control_rows = list(csv.DictReader(f))

    summary = summarize_control_log(control_rows)
    with out_control.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)
    print(f"Wrote control summary: {out_control}")


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    write_phase_summary(run_dir, Path(args.out_phase_csv).resolve())
    if args.out_control_csv:
        write_control_summary(run_dir, Path(args.out_control_csv).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
