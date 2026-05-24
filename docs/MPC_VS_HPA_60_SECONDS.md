# MPC vs HPA In 60 Seconds

If you only give this repository one minute, start here.

## The Question

Kubernetes HPA reacts after measured CPU or custom metrics move. A short-horizon Model Predictive Control loop can instead forecast near-term demand and choose a replica target before the spike fully drains through the service.

The research question is narrow: under controlled traffic profiles, when does predictive scaling reduce latency spikes enough to justify its added complexity?

## What Is Built

This repository is a small autoscaling lab, not a production autoscaler distribution.

It contains:

- `toy-load`: a controllable Go HTTP workload with Prometheus metrics.
- Helm and Kubernetes manifests for repeatable deployment.
- HPA baseline runners for step, spike, and seasonality scenarios.
- Python MPC tooling for offline simulation and online control-loop experiments.
- Evidence docs that keep result claims tied to paths, caveats, and rebuild commands.

## Current Snapshot

The public numbers currently cover one tracked 200 rps spike pair. Treat this as a representative snapshot, not an aggregate benchmark claim.

| Controller | Burst throughput | Burst p95 | Burst p99 | Max latency | Success | Max replicas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HPA60 baseline | 197.91 rps | 85.175 ms | 128.983 ms | 276.229 ms | 100.00% | 27 |
| Hybrid-SA MPC | 199.90 rps | 52.483 ms | 71.048 ms | 97.157 ms | 100.00% | 28 |

For this tracked pair, Hybrid-SA MPC lowers burst p95 latency by about 38%, p99 latency by about 45%, and max latency by about 65% versus the HPA60 baseline while both runs report 100% success.

Read the trust boundary before generalizing:

- Results: [`docs/RESULTS.md`](RESULTS.md)
- Benchmark matrix: [`docs/BENCHMARK_MATRIX.md`](BENCHMARK_MATRIX.md)
- Methodology: [`docs/METHODOLOGY.md`](METHODOLOGY.md)
- Limitations: [`docs/LIMITATIONS.md`](LIMITATIONS.md)

## Quick Local Path

The fastest non-cluster path is to validate and simulate one bundled spike trace:

```bash
python3 -m pip install -e analysis
mpc-validate-trace --trace-csv analysis/mpc_autoscaler_analysis/data/traces/baseline_spike_profile_dt15.csv
mpc-offline-sim \
  --trace-csv analysis/mpc_autoscaler_analysis/data/traces/baseline_spike_profile_dt15.csv \
  --out-dir analysis/out/offline/spike
```

This does not reproduce the live Kubernetes result by itself. It is the lightweight path for checking trace schema, simulator behavior, and controller assumptions before trying live runs.

## Feedback I Want

The most useful feedback is specific and reproducible:

- Which HPA target, stabilization window, or metric choice would make the baseline fairer?
- Which workload trace would better represent real production burst behavior?
- Which failure case should be tested first: missing metrics, solver fallback, cold starts, noisy demand, or rate limits?
- Which chart or table would make the current evidence easier to audit?
- Which comparator belongs next: KEDA, predictive HPA, queue-aware reactive scaling, or a simpler no-QP policy?

Use the [Q&A thread](https://github.com/vshulcz/mpc-autoscaler/discussions/77) for setup and methodology questions. Use the [reproduction feedback issue template](https://github.com/vshulcz/mpc-autoscaler/issues/new?template=reproduction_feedback.yml) when you ran one documented path and can paste commands, output paths, or a concrete suggested next experiment.

## One-Sentence Share Text

I am building a reproducible Kubernetes autoscaling lab to compare reactive HPA baselines with a small MPC controller on controlled workloads; the current public result is one spike snapshot with explicit caveats, and I am looking for feedback on baselines, traces, and failure cases.
