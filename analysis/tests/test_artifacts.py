from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from mpc_autoscaler_analysis.artifacts.control import summarize_control_log
from mpc_autoscaler_analysis.artifacts.costs import (
    CostSummaryOptions,
    parse_duration,
    replica_stats,
    summarize_costs,
    to_ms,
)
from mpc_autoscaler_analysis.artifacts.vegeta import parse_phase_metrics


class VegetaParserTests(unittest.TestCase):
    def test_parse_phase_metrics(self) -> None:
        report = """
Requests      [total, rate, throughput]  1000, 50.00, 49.95
Latencies     [min, mean, 50, 90, 95, 99, max]  1ms, 2ms, 3ms, 4ms, 5ms, 6ms, 7ms
Success       [ratio]                    99.90%
Requests      [total, rate, throughput]  2000, 100.00, 98.50
Latencies     [min, mean, 50, 90, 95, 99, max]  2ms, 3ms, 4ms, 5ms, 6ms, 7ms, 8ms
Success       [ratio]                    97.25%
"""

        rows = parse_phase_metrics(report)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["phase"], "1")
        self.assertEqual(rows[0]["throughput_rps"], "49.95")
        self.assertEqual(rows[1]["p95"], "6ms")
        self.assertEqual(rows[1]["success_ratio_pct"], "97.25")


class ControlSummaryTests(unittest.TestCase):
    def test_summarize_control_log(self) -> None:
        rows = [
            {
                "applied_replicas": "2",
                "observed_rps": "10",
                "observed_cpu_cores": "0.5",
                "observed_inflight": "1",
                "demand_proxy_rps": "11",
                "emergency_scale_up": "0",
                "solver_status": "optimal",
            },
            {
                "applied_replicas": "5",
                "observed_rps": "20",
                "observed_cpu_cores": "0.7",
                "observed_inflight": "4",
                "demand_proxy_rps": "21",
                "emergency_scale_up": "1",
                "solver_status": "fallback",
            },
            {
                "applied_replicas": "4",
                "observed_rps": "15",
                "observed_cpu_cores": "0.6",
                "observed_inflight": "2",
                "demand_proxy_rps": "16",
                "emergency_scale_up": "0",
                "solver_status": "optimal",
            },
        ]

        summary = summarize_control_log(rows)

        self.assertEqual(summary["samples"], "3")
        self.assertEqual(summary["avg_replicas"], "3.667")
        self.assertEqual(summary["max_replicas"], "5")
        self.assertEqual(summary["replica_variation_sum_abs_delta"], "4.000")
        self.assertEqual(summary["emergency_scale_events"], "1")
        self.assertEqual(summary["solver_status_unique"], "fallback;optimal")


class CostSummaryTests(unittest.TestCase):
    def test_duration_latency_and_replica_stats(self) -> None:
        self.assertEqual(parse_duration("2m"), 120.0)
        self.assertEqual(parse_duration("1.5h"), 5400.0)
        self.assertEqual(to_ms("2s"), 2000.0)
        self.assertEqual(to_ms("1500us"), 1.5)

        avg, max_rep, variation = replica_stats([(0.0, 2.0), (10.0, 4.0), (20.0, 1.0)], 30.0)

        self.assertAlmostEqual(avg, 70.0 / 30.0)
        self.assertEqual(max_rep, 4.0)
        self.assertEqual(variation, 5.0)

    def test_summarize_costs_from_fixture_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hpa_run = root / "hpa" / "target_60" / "step" / "run1"
            hybrid_run = root / "hybrid" / "spike" / "run1"
            hpa_run.mkdir(parents=True)
            hybrid_run.mkdir(parents=True)
            self._write_run(hpa_run, "step", [(0, 2), (10, 4), (20, 4)], hpa=True)
            self._write_run(hybrid_run, "spike", [(0, 3), (10, 3), (20, 5)], hpa=False)

            rows, agg_rows = summarize_costs(
                CostSummaryOptions(
                    hpa_roots=(root / "hpa",),
                    hybrid_roots=(root / "hybrid",),
                )
            )

        self.assertEqual(len(rows), 4)
        self.assertEqual(len(agg_rows), 4)
        hpa_rows = [r for r in rows if r["controller"] == "hpa"]
        hybrid_rows = [r for r in rows if r["controller"] == "hybrid"]
        self.assertTrue(all(r["target"] == "60" for r in hpa_rows))
        self.assertTrue(all(r["target"] == "final" for r in hybrid_rows))
        self.assertEqual(hpa_rows[0]["focus_p95_ms"], "20.000")
        self.assertEqual(hybrid_rows[0]["focus_p99_ms"], "30.000")

    def _write_run(self, run_dir: Path, scenario: str, replicas: list[tuple[int, int]], *, hpa: bool) -> None:
        (run_dir / "run-meta.yaml").write_text(
            f'scenario: "{scenario}"\nstarted_at_utc: "2026-01-01T00:00:00Z"\nfinished_at_utc: "2026-01-01T00:00:30Z"\n',
            encoding="utf-8",
        )
        self._write_csv(run_dir / "phases.csv", ["duration"], [{"duration": "10s"}, {"duration": "20s"}])
        self._write_csv(
            run_dir / "phase-summary.csv",
            ["phase", "p95", "p99", "success_ratio_pct"],
            [
                {"phase": "1", "p95": "10ms", "p99": "15ms", "success_ratio_pct": "100.00"},
                {"phase": "2", "p95": "20ms", "p99": "30ms", "success_ratio_pct": "99.00"},
            ],
        )
        if hpa:
            self._write_csv(
                run_dir / "replica-watch.csv",
                ["elapsed_s", "spec_replicas", "ready_replicas"],
                [
                    {"elapsed_s": str(t), "spec_replicas": str(r), "ready_replicas": str(r)}
                    for t, r in replicas
                ],
            )
        else:
            self._write_csv(
                run_dir / "mpc-control-log.csv",
                ["elapsed_s", "applied_replicas"],
                [{"elapsed_s": str(t), "applied_replicas": str(r)} for t, r in replicas],
            )

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
