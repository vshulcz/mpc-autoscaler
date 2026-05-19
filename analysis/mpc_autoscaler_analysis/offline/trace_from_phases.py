#!/usr/bin/env python3
"""Build an offline-MPC trace CSV from a phases profile CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

DURATION_RE = re.compile(r"^(?P<num>\d+)(?P<unit>[smh])$")


def parse_duration_seconds(raw: str) -> int:
    m = DURATION_RE.match(raw.strip().lower())
    if not m:
        raise ValueError(f"unsupported duration format: {raw!r}")
    num = int(m.group("num"))
    unit = m.group("unit")
    if unit == "s":
        return num
    if unit == "m":
        return num * 60
    if unit == "h":
        return num * 3600
    raise ValueError(f"unsupported duration unit: {unit!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phases-csv", required=True, help="Input phases.csv path")
    parser.add_argument("--out", required=True, help="Output trace CSV path")
    parser.add_argument(
        "--dt-seconds",
        type=int,
        default=15,
        help="Trace sampling interval in seconds (default: 15)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    phases_path = Path(args.phases_csv)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.dt_seconds <= 0:
        raise ValueError("--dt-seconds must be > 0")

    rows_out: list[dict[str, int]] = []
    step = 0
    timestamp_s = 0

    with phases_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            phase_idx = int(row["phase_idx"])
            duration_s = parse_duration_seconds(row["duration"])
            rate_rps = int(row["rate_rps"])

            points = max(1, round(duration_s / args.dt_seconds))
            for _ in range(points):
                rows_out.append(
                    {
                        "step": step,
                        "timestamp_s": timestamp_s,
                        "rps": rate_rps,
                        "phase_idx": phase_idx,
                    }
                )
                step += 1
                timestamp_s += args.dt_seconds

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["step", "timestamp_s", "rps", "phase_idx"],
        )
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"saved {out_path} ({len(rows_out)} points, dt={args.dt_seconds}s)")


if __name__ == "__main__":
    main()
