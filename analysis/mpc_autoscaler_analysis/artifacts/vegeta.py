"""Parsers for saved vegeta text reports."""

from __future__ import annotations

import re

REQUESTS_RE = re.compile(
    r"Requests\s+\[total, rate, throughput\]\s+([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)"
)
LAT_RE = re.compile(
    r"Latencies\s+\[min, mean, 50, 90, 95, 99, max\]\s+"
    r"([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^\n]+)"
)
SUCCESS_RE = re.compile(r"Success\s+\[ratio\]\s+([0-9.]+)%")


def parse_phase_metrics(report_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    parts = report_text.split("Requests      [total, rate, throughput]")
    for idx, part in enumerate(parts[1:], start=1):
        text = "Requests      [total, rate, throughput]" + part
        req_m = REQUESTS_RE.search(text)
        lat_m = LAT_RE.search(text)
        suc_m = SUCCESS_RE.search(text)
        if not req_m or not lat_m or not suc_m:
            continue
        rows.append(
            {
                "phase": str(idx),
                "throughput_rps": req_m.group(3),
                "p95": lat_m.group(5).strip(),
                "p99": lat_m.group(6).strip(),
                "max": lat_m.group(7).strip(),
                "success_ratio_pct": suc_m.group(1),
            }
        )
    return rows
