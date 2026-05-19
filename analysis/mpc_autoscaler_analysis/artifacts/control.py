"""Summaries for online MPC control logs."""

from __future__ import annotations

EMPTY_CONTROL_SUMMARY = {
    "samples": "0",
    "avg_replicas": "",
    "max_replicas": "",
    "replica_variation_sum_abs_delta": "",
    "max_observed_rps": "",
    "avg_observed_rps": "",
    "avg_cpu_cores": "",
    "max_observed_inflight": "",
    "avg_demand_proxy_rps": "",
    "emergency_scale_events": "",
    "solver_status_unique": "",
}


def summarize_control_log(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return dict(EMPTY_CONTROL_SUMMARY)

    reps = [float(r["applied_replicas"]) for r in rows]
    rps = [float(r["observed_rps"]) for r in rows]
    cpu = [float(r["observed_cpu_cores"]) for r in rows]
    inflight = [float(r.get("observed_inflight", "0") or 0.0) for r in rows]
    demand_proxy = [float(r.get("demand_proxy_rps", "0") or 0.0) for r in rows]
    emergency = [int(float(r.get("emergency_scale_up", "0") or 0.0)) for r in rows]
    variation = sum(abs(b - a) for a, b in zip(reps[:-1], reps[1:])) if len(reps) > 1 else 0.0
    statuses = sorted(set(r["solver_status"] for r in rows))
    return {
        "samples": str(len(rows)),
        "avg_replicas": f"{sum(reps) / len(reps):.3f}",
        "max_replicas": f"{max(reps):.0f}",
        "replica_variation_sum_abs_delta": f"{variation:.3f}",
        "max_observed_rps": f"{max(rps):.3f}",
        "avg_observed_rps": f"{sum(rps) / len(rps):.3f}",
        "avg_cpu_cores": f"{sum(cpu) / len(cpu):.3f}",
        "max_observed_inflight": f"{max(inflight):.3f}",
        "avg_demand_proxy_rps": f"{sum(demand_proxy) / len(demand_proxy):.3f}",
        "emergency_scale_events": f"{sum(emergency)}",
        "solver_status_unique": ";".join(statuses),
    }
