from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_summarize_run_cli_writes_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "incluster-report.txt").write_text(
                """
Requests      [total, rate, throughput]  100, 10.00, 9.50
Latencies     [min, mean, 50, 90, 95, 99, max]  1ms, 2ms, 3ms, 4ms, 5ms, 6ms, 7ms
Success       [ratio]                    98.00%
""",
                encoding="utf-8",
            )
            self._write_csv(
                run_dir / "mpc-control-log.csv",
                [
                    "applied_replicas",
                    "observed_rps",
                    "observed_cpu_cores",
                    "observed_inflight",
                    "demand_proxy_rps",
                    "emergency_scale_up",
                    "solver_status",
                ],
                [
                    {
                        "applied_replicas": "2",
                        "observed_rps": "9.5",
                        "observed_cpu_cores": "0.2",
                        "observed_inflight": "1",
                        "demand_proxy_rps": "10",
                        "emergency_scale_up": "0",
                        "solver_status": "optimal",
                    }
                ],
            )

            phase_out = root / "phase.csv"
            control_out = root / "control.csv"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mpc_autoscaler_analysis.cli.summarize_run",
                    "--run-dir",
                    str(run_dir),
                    "--out-phase-csv",
                    str(phase_out),
                    "--out-control-csv",
                    str(control_out),
                ],
                cwd=ANALYSIS_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Wrote phase summary", result.stdout)
            self.assertEqual(self._read_csv(phase_out)[0]["p95"], "5ms")
            self.assertEqual(self._read_csv(control_out)[0]["avg_replicas"], "2.000")

    def test_cli_help_works_for_installed_entrypoints(self) -> None:
        for module in (
            "mpc_autoscaler_analysis.cli.summarize_run",
            "mpc_autoscaler_analysis.cli.summarize_costs",
            "mpc_autoscaler_analysis.online.control_loop",
            "mpc_autoscaler_analysis.offline.trace_from_phases",
            "mpc_autoscaler_analysis.offline.synthetic_trace",
            "mpc_autoscaler_analysis.offline.validate_trace",
        ):
            result = subprocess.run(
                [sys.executable, "-m", module, "--help"],
                cwd=ANALYSIS_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("usage:", result.stdout)

    def test_trace_clis_write_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            phases = root / "phases.csv"
            self._write_csv(
                phases,
                ["phase_idx", "duration", "rate_rps"],
                [
                    {"phase_idx": "1", "duration": "30s", "rate_rps": "20"},
                    {"phase_idx": "2", "duration": "15s", "rate_rps": "80"},
                ],
            )
            trace_out = root / "trace.csv"
            synthetic_out = root / "synthetic.csv"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mpc_autoscaler_analysis.offline.trace_from_phases",
                    "--phases-csv",
                    str(phases),
                    "--out",
                    str(trace_out),
                    "--dt-seconds",
                    "15",
                ],
                cwd=ANALYSIS_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mpc_autoscaler_analysis.offline.synthetic_trace",
                    "--scenario",
                    "spike",
                    "--out",
                    str(synthetic_out),
                ],
                cwd=ANALYSIS_ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertEqual([r["rps"] for r in self._read_csv(trace_out)], ["20", "20", "80"])
            self.assertEqual(len(self._read_csv(synthetic_out)), 26)

    def test_validate_trace_reports_missing_and_malformed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.csv"
            self._write_csv(missing, ["step", "rps"], [{"step": "0", "rps": "20"}])

            missing_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mpc_autoscaler_analysis.offline.validate_trace",
                    "--trace-csv",
                    str(missing),
                ],
                cwd=ANALYSIS_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(missing_result.returncode, 0)
            self.assertIn("missing required columns: timestamp_s", missing_result.stderr)

            malformed = root / "malformed.csv"
            self._write_csv(
                malformed,
                ["step", "timestamp_s", "rps"],
                [
                    {"step": "0", "timestamp_s": "0", "rps": "20"},
                    {"step": "1", "timestamp_s": "15", "rps": "fast"},
                    {"step": "2", "timestamp_s": "-30", "rps": "40"},
                ],
            )

            malformed_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mpc_autoscaler_analysis.offline.validate_trace",
                    "--trace-csv",
                    str(malformed),
                ],
                cwd=ANALYSIS_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(malformed_result.returncode, 0)
            self.assertIn("row 3: rps must be a number", malformed_result.stderr)
            self.assertIn("row 4: timestamp_s must be >= 0 seconds", malformed_result.stderr)

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))


if __name__ == "__main__":
    unittest.main()
