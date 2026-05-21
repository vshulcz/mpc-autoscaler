# Methodology

This repository studies whether a small Model Predictive Control loop can make smoother scaling decisions than reactive HPA-style baselines on controlled Kubernetes workloads.

The project is a research playground, not a production autoscaler. The goal is reproducible comparison, clear instrumentation, and honest reporting of tradeoffs.

## Research Question

Can a short-horizon predictive controller reduce latency spikes or replica oscillation compared with a reactive baseline under controlled `step`, `spike`, and `seasonality` traffic profiles?

## System Under Test

| Component | Role |
| --- | --- |
| `toy-load` | Go HTTP workload with configurable CPU, sleep, jitter, payload, and error-rate knobs. |
| Prometheus metrics | Request rate, latency histogram, in-flight requests, work knobs, and error counters. |
| HPA baseline | Reactive scaling policy using Kubernetes HPA behavior and resource signals. |
| MPC controller | Python controller that estimates demand and recommends or applies replica targets. |
| Analysis tools | Offline simulation, trace validation, run summarization, and resource proxy summaries. |

## Traffic Scenarios

| Scenario | Purpose |
| --- | --- |
| `step` | Sustained increase in load. |
| `spike` | Short burst followed by return to baseline. |
| `seasonality` | Smooth demand variation over time. |

These scenarios are synthetic by design. They are useful for controlled controller comparison, not a replacement for production traces.

## Metrics

Primary metrics:

- request success ratio;
- throughput during each traffic phase;
- p95, p99, and max request latency;
- replica target and available replicas;
- controller decision log, solver status, and safety events for MPC runs.

Secondary metrics:

- average and maximum observed demand;
- average CPU proxy;
- resource proxy summaries when full evidence archives are available.

## Evidence Policy

Raw experiment runs can be large, so the repository commits only curated evidence indices, small summary files, figures, and rebuild commands. Raw run roots are documented through `experiments/EVIDENCE_MAP.csv` and `experiments/MANIFEST.md`.

Claims in `docs/RESULTS.md` should link to exact run directories or committed summary files. Screenshots and SVG figures are treated as presentation aids, not primary evidence.

## Current Results Snapshot

The current public results snapshot compares one representative HPA60 spike run against one representative Hybrid-SA MPC spike run. It is not an aggregate benchmark claim.

Use it as:

- a smoke test that the pipeline can produce interpretable evidence;
- a concrete example for contributors adding tables, figures, or rebuild commands;
- a starting point for broader benchmark aggregation.

Do not use it as:

- evidence that MPC is generally better than HPA;
- production guidance for Kubernetes clusters;
- a claim about arbitrary workloads.

The public benchmark coverage table lives in `docs/BENCHMARK_MATRIX.md`. A cell can be marked as published only when it has numeric values, exact evidence paths, and caveats. Evidence-root aliases alone are useful for reproducibility planning, but they are not result claims.

## Reproduction Tiers

| Tier | Requires cluster | Purpose |
| --- | --- | --- |
| Local checks | No | Verify code, docs, charts, dashboards, and Python tooling. |
| Offline simulation | No | Generate or validate traces and simulate controller behavior. |
| Saved evidence summaries | No, if evidence archive is present | Rebuild tables from saved run directories. |
| Live Kubernetes experiments | Yes | Run HPA and MPC controllers against a deployed workload. |

Detailed commands live in `docs/REPRODUCIBILITY.md`.

## Review Standard

Before adding a new result claim:

1. Link the exact run directory or summary file.
2. State whether the result is representative, aggregate, or exploratory.
3. Include enough command context for another person to rebuild the summary.
4. Avoid production claims unless the experiment actually evaluates production-like workloads.
5. Update `docs/LIMITATIONS.md` if the claim exposes a new caveat.
