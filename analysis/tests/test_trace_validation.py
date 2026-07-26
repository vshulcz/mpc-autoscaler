from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from mpc_autoscaler_analysis.offline.validate_trace import validate_trace_csv


class ValidateTraceCsvTests(unittest.TestCase):
    def test_valid_trace_returns_no_errors_and_row_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            self._write_csv(
                path,
                ["step", "timestamp_s", "rps"],
                [{"step": "0", "timestamp_s": "0", "rps": "20"}],
            )

            errors, row_count = validate_trace_csv(path)

            self.assertEqual(errors, [])
            self.assertEqual(row_count, 1)

    def test_missing_file_reports_error_without_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-trace.csv"

            errors, row_count = validate_trace_csv(path)

            self.assertEqual(errors, [f"file not found: {path}"])
            self.assertEqual(row_count, 0)

    def test_empty_file_reports_missing_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            path.write_text("", encoding="utf-8")

            errors, row_count = validate_trace_csv(path)

            self.assertEqual(errors, ["header row is required"])
            self.assertEqual(row_count, 0)

    def test_phase_index_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            self._write_csv(
                path,
                ["step", "timestamp_s", "rps", "phase_idx"],
                [
                    {"step": "0", "timestamp_s": "0", "rps": "20", "phase_idx": ""},
                    {"step": "1", "timestamp_s": "15", "rps": "25", "phase_idx": "2"},
                ],
            )

            errors, row_count = validate_trace_csv(path)

            self.assertEqual(errors, [])
            self.assertEqual(row_count, 2)

    def _write_csv(
        self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]
    ) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
