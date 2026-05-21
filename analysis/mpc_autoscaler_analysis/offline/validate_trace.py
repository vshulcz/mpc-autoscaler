#!/usr/bin/env python3
"""Validate offline simulation trace CSV inputs."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REQUIRED_COLUMNS = ("step", "timestamp_s", "rps")
OPTIONAL_COLUMNS = ("phase_idx",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-csv", required=True, help="Input trace CSV path")
    return parser.parse_args()


def validate_trace_csv(path: Path) -> tuple[list[str], int]:
    """Return validation errors and the number of data rows read."""
    errors: list[str] = []
    row_count = 0

    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if not fieldnames:
                return ["header row is required"], 0

            missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
            if missing:
                errors.append(f"missing required columns: {', '.join(missing)}")

            for line_no, row in enumerate(reader, start=2):
                row_count += 1
                validate_row(row, line_no, fieldnames, errors)
    except FileNotFoundError:
        return [f"file not found: {path}"], 0

    if row_count == 0:
        errors.append("trace CSV must contain at least one data row")
    return errors, row_count


def validate_row(
    row: dict[str, str],
    line_no: int,
    fieldnames: list[str],
    errors: list[str],
) -> None:
    if "step" in fieldnames:
        raw = (row.get("step") or "").strip()
        try:
            value = int(raw)
        except ValueError:
            errors.append(f"row {line_no}: step must be an integer")
        else:
            if value < 0:
                errors.append(f"row {line_no}: step must be >= 0")

    if "timestamp_s" in fieldnames:
        raw = (row.get("timestamp_s") or "").strip()
        try:
            value = float(raw)
        except ValueError:
            errors.append(f"row {line_no}: timestamp_s must be a number of seconds")
        else:
            if value < 0:
                errors.append(f"row {line_no}: timestamp_s must be >= 0 seconds")

    if "rps" in fieldnames:
        raw = (row.get("rps") or "").strip()
        try:
            value = float(raw)
        except ValueError:
            errors.append(f"row {line_no}: rps must be a number")
        else:
            if value < 0:
                errors.append(f"row {line_no}: rps must be >= 0 requests/second")

    if "phase_idx" in fieldnames:
        raw = row.get("phase_idx", "").strip()
        if raw:
            try:
                value = int(raw)
            except ValueError:
                errors.append(f"row {line_no}: phase_idx must be an integer")
            else:
                if value < 0:
                    errors.append(f"row {line_no}: phase_idx must be >= 0")


def main() -> int:
    args = parse_args()
    path = Path(args.trace_csv)
    errors, row_count = validate_trace_csv(path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        f"valid trace CSV: {path} ({row_count} rows; "
        f"required columns: {', '.join(REQUIRED_COLUMNS)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
