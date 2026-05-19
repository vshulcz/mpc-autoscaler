"""Cost and resource summaries for saved experiment artifacts."""

from __future__ import annotations

import csv
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

CPU_REQUEST_VCPU = 0.1
MEM_REQUEST_GIB = 64.0 / 1024.0

DEFAULT_PRICES = {
    "aws_fargate_us_east_1": (0.000011244 * 3600.0, 0.000001235 * 3600.0, "USD"),
    "gke_autopilot_us_central1": (0.0445, 0.0049225, "USD"),
}


@dataclass(frozen=True)
class CostSummaryOptions:
    hpa_roots: tuple[Path, ...] = ()
    hybrid_roots: tuple[Path, ...] = ()
    yandex_vcpu_hour_rub: float = 0.0
    yandex_memory_gib_hour_rub: float = 0.0


def parse_meta(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip().strip('"')
    return data


def parse_time(raw: str) -> dt.datetime | None:
    if not raw:
        return None
    return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))


def duration_seconds(meta: dict[str, str]) -> float:
    start = parse_time(meta.get("started_at_utc", ""))
    finish = parse_time(meta.get("finished_at_utc", ""))
    if not start or not finish:
        return 0.0
    return max(0.0, (finish - start).total_seconds())


def parse_duration(raw: str) -> float:
    raw = raw.strip()
    m = re.fullmatch(r"([0-9.]+)(s|m|h)", raw)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = m.group(2)
    if unit == "h":
        return value * 3600.0
    if unit == "m":
        return value * 60.0
    return value


def planned_duration_seconds(run_dir: Path) -> float:
    path = run_dir / "phases.csv"
    if not path.exists():
        return 0.0
    with path.open("r", encoding="utf-8", newline="") as f:
        return sum(parse_duration(r.get("duration", "")) for r in csv.DictReader(f))


def to_ms(raw: str) -> float:
    raw = raw.strip()
    m = re.fullmatch(r"([0-9.]+)(ms|s|m|us|µs)", raw)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = m.group(2)
    if unit == "s":
        return value * 1000.0
    if unit == "m":
        return value * 60_000.0
    if unit in {"us", "µs"}:
        return value / 1000.0
    return value


def phase_focus(run_dir: Path, scenario: str) -> tuple[float, float, float]:
    path = run_dir / "phase-summary.csv"
    if not path.exists():
        return 0.0, 0.0, 0.0
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0.0, 0.0, 0.0
    if scenario in {"step", "spike"} and len(rows) >= 2:
        focus = rows[1]
        success = float(focus.get("success_ratio_pct", "0") or 0.0)
    else:
        focus = max(rows, key=lambda r: to_ms(r.get("p95", "0ms")))
        success = min(float(r.get("success_ratio_pct", "0") or 0.0) for r in rows)
    return to_ms(focus.get("p95", "0ms")), to_ms(focus.get("p99", "0ms")), success


def replica_stats(samples: list[tuple[float, float]], duration_s: float) -> tuple[float, float, float]:
    if not samples:
        return 0.0, 0.0, 0.0
    samples = sorted((max(0.0, t), r) for t, r in samples if duration_s <= 0 or t <= duration_s)
    if not samples:
        return 0.0, 0.0, 0.0

    reps = [r for _, r in samples]
    variation = sum(abs(b - a) for a, b in zip(reps[:-1], reps[1:]))
    if duration_s <= 0:
        return sum(reps) / len(reps), max(reps), variation

    replica_seconds = 0.0
    prev_t = 0.0
    prev_r = reps[0]
    for elapsed, replicas in samples:
        elapsed = min(max(elapsed, prev_t), duration_s)
        replica_seconds += prev_r * (elapsed - prev_t)
        prev_t = elapsed
        prev_r = replicas
    replica_seconds += prev_r * max(0.0, duration_s - prev_t)
    return replica_seconds / duration_s, max(reps), variation


def hpa_replicas(run_dir: Path, duration_s: float) -> tuple[float, float, float]:
    path = run_dir / "replica-watch.csv"
    if not path.exists():
        return 0.0, 0.0, 0.0
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    samples = []
    for r in rows:
        try:
            elapsed = float(r.get("elapsed_s", "0") or 0.0)
        except ValueError:
            elapsed = 0.0
        raw = r.get("spec_replicas") or r.get("ready_replicas") or "0"
        try:
            samples.append((elapsed, float(raw or 0.0)))
        except ValueError:
            continue
    return replica_stats(samples, duration_s)


def hybrid_replicas(run_dir: Path, duration_s: float) -> tuple[float, float, float]:
    log_path = run_dir / "mpc-control-log.csv"
    if log_path.exists():
        with log_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        reps = []
        for r in rows:
            try:
                elapsed = float(r.get("elapsed_s", "0") or 0.0)
            except ValueError:
                elapsed = 0.0
            reps.append((elapsed, float(r.get("applied_replicas", "0") or 0.0)))
        stats = replica_stats(reps, duration_s)
        if stats[0] > 0:
            return stats

    path = run_dir / "control-summary.csv"
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if rows:
            r = rows[0]
            return (
                float(r.get("avg_replicas", "0") or 0.0),
                float(r.get("max_replicas", "0") or 0.0),
                float(r.get("replica_variation_sum_abs_delta", "0") or 0.0),
            )
    return 0.0, 0.0, 0.0


def prices(options: CostSummaryOptions) -> dict[str, tuple[float, float, str]]:
    result = dict(DEFAULT_PRICES)
    if options.yandex_vcpu_hour_rub > 0 and options.yandex_memory_gib_hour_rub > 0:
        result["yandex_compute_custom_rub"] = (
            options.yandex_vcpu_hour_rub,
            options.yandex_memory_gib_hour_rub,
            "RUB",
        )
    return result


def scenario_from_dir(run_dir: Path) -> str:
    return run_dir.parent.name


def hpa_target_from_dir(run_dir: Path, meta: dict[str, str]) -> str:
    if "hpa_target_average_utilization" in meta:
        return meta["hpa_target_average_utilization"]
    for parent in run_dir.parents:
        if parent.name.startswith("target_"):
            return parent.name.removeprefix("target_")
    return ""


def collect_hpa_roots(roots: tuple[Path, ...]) -> list[tuple[str, Path]]:
    runs: list[tuple[str, Path]] = []
    for root in roots:
        for run_dir in sorted(root.glob("target_*/*/*")):
            if (run_dir / "run-meta.yaml").exists():
                runs.append(("hpa", run_dir))
    return runs


def collect_hybrid_roots(roots: tuple[Path, ...]) -> list[tuple[str, Path]]:
    runs: list[tuple[str, Path]] = []
    for root in roots:
        for run_dir in sorted(root.glob("*/*")):
            if (run_dir / "run-meta.yaml").exists():
                runs.append(("hybrid", run_dir))
    return runs


def summarize_costs(options: CostSummaryOptions) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    price_table = prices(options)
    runs = collect_hpa_roots(options.hpa_roots) + collect_hybrid_roots(options.hybrid_roots)
    rows: list[dict[str, str]] = []
    aggregates: dict[tuple[str, str, str], dict[str, float]] = {}

    for controller, run_dir in runs:
        meta = parse_meta(run_dir / "run-meta.yaml")
        scenario = meta.get("scenario") or scenario_from_dir(run_dir)
        target = hpa_target_from_dir(run_dir, meta) if controller == "hpa" else "final"
        duration_s = planned_duration_seconds(run_dir) or duration_seconds(meta)
        p95_ms, p99_ms, success_pct = phase_focus(run_dir, scenario)
        if controller == "hpa":
            avg_rep, max_rep, variation = hpa_replicas(run_dir, duration_s)
        else:
            avg_rep, max_rep, variation = hybrid_replicas(run_dir, duration_s)
        if avg_rep <= 0:
            continue
        hours = duration_s / 3600.0
        vcpu_hours = avg_rep * CPU_REQUEST_VCPU * hours
        mem_gib_hours = avg_rep * MEM_REQUEST_GIB * hours
        for provider, (cpu_rate, mem_rate, currency) in price_table.items():
            cost = vcpu_hours * cpu_rate + mem_gib_hours * mem_rate
            cost_per_hour = avg_rep * (CPU_REQUEST_VCPU * cpu_rate + MEM_REQUEST_GIB * mem_rate)
            row = {
                "provider": provider,
                "currency": currency,
                "controller": controller,
                "target": target,
                "scenario": scenario,
                "run_dir": str(run_dir),
                "duration_s": f"{duration_s:.0f}",
                "avg_replicas": f"{avg_rep:.3f}",
                "max_replicas": f"{max_rep:.0f}",
                "replica_variation": f"{variation:.3f}",
                "vcpu_hours": f"{vcpu_hours:.6f}",
                "mem_gib_hours": f"{mem_gib_hours:.6f}",
                "cost": f"{cost:.8f}",
                "cost_per_hour": f"{cost_per_hour:.8f}",
                "focus_p95_ms": f"{p95_ms:.3f}",
                "focus_p99_ms": f"{p99_ms:.3f}",
                "success_pct": f"{success_pct:.3f}",
            }
            rows.append(row)
            key = (provider, controller, target)
            agg = aggregates.setdefault(
                key,
                {
                    "duration_s": 0.0,
                    "replica_seconds": 0.0,
                    "variation": 0.0,
                    "cost": 0.0,
                    "worst_p95_ms": 0.0,
                    "worst_p99_ms": 0.0,
                    "min_success_pct": 100.0,
                },
            )
            agg["duration_s"] += duration_s
            agg["replica_seconds"] += avg_rep * duration_s
            agg["variation"] += variation
            agg["cost"] += cost
            agg["worst_p95_ms"] = max(agg["worst_p95_ms"], p95_ms)
            agg["worst_p99_ms"] = max(agg["worst_p99_ms"], p99_ms)
            agg["min_success_pct"] = min(agg["min_success_pct"], success_pct)

    agg_rows: list[dict[str, str]] = []
    for (provider, controller, target), agg in sorted(aggregates.items()):
        duration_s = agg["duration_s"]
        avg_replicas = agg["replica_seconds"] / duration_s if duration_s else 0.0
        currency = price_table[provider][2]
        agg_rows.append(
            {
                "provider": provider,
                "currency": currency,
                "controller": controller,
                "target": target,
                "scenarios": "all",
                "duration_s": f"{duration_s:.0f}",
                "avg_replicas_weighted": f"{avg_replicas:.3f}",
                "replica_variation_sum": f"{agg['variation']:.3f}",
                "cost": f"{agg['cost']:.8f}",
                "cost_per_hour": f"{(agg['cost'] / (duration_s / 3600.0)) if duration_s else 0.0:.8f}",
                "worst_p95_ms": f"{agg['worst_p95_ms']:.3f}",
                "worst_p99_ms": f"{agg['worst_p99_ms']:.3f}",
                "min_success_pct": f"{agg['min_success_pct']:.3f}",
            }
        )
    return rows, agg_rows
