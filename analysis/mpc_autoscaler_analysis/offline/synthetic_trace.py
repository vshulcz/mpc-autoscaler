#!/usr/bin/env python3
"""Generate synthetic load traces for quick offline MPC checks."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def build_step_trace(dt_seconds: int) -> list[dict[str, int]]:
    rates = [20] * 20 + [80] * 20 + [40] * 20
    return to_rows(rates, dt_seconds)


def build_spike_trace(dt_seconds: int) -> list[dict[str, int]]:
    rates = [20] * 12 + [200] * 2 + [20] * 12
    return to_rows(rates, dt_seconds)


def build_seasonality_trace(dt_seconds: int, points: int) -> list[dict[str, int]]:
    rates = []
    for i in range(points):
        rate = int(round(70 + 50 * math.sin(2 * math.pi * i / 20)))
        rates.append(min(120, max(20, rate)))
    return to_rows(rates, dt_seconds)


def to_rows(rates: list[int], dt_seconds: int) -> list[dict[str, int]]:
    steps = list(range(len(rates)))
    ts = [step * dt_seconds for step in steps]
    return [
        {"step": step, "timestamp_s": timestamp, "rps": rps}
        for step, timestamp, rps in zip(steps, ts, rates)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("step", "spike", "seasonality"),
        required=True,
        help="Synthetic scenario profile",
    )
    parser.add_argument(
        "--dt-seconds",
        type=int,
        default=15,
        help="Sampling period used for timestamp_s column",
    )
    parser.add_argument(
        "--seasonality-points",
        type=int,
        default=80,
        help="Number of points for seasonality scenario",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output CSV path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.scenario == "step":
        rows = build_step_trace(args.dt_seconds)
    elif args.scenario == "spike":
        rows = build_spike_trace(args.dt_seconds)
    else:
        rows = build_seasonality_trace(args.dt_seconds, args.seasonality_points)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["step", "timestamp_s", "rps"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved trace to {out_path} ({len(rows)} points)")


if __name__ == "__main__":
    main()
