# Results Snapshot

This page is the public entry point for current experiment evidence. It is intentionally narrow: only claims backed by committed summaries or documented evidence aliases appear here.

## Current Claim

Under a representative 200 rps spike trace, the predictive controller keeps latency lower than the reactive HPA baseline while preserving 100% request success. This is a proof point, not a final benchmark suite.

| Scenario | Controller | Burst throughput | Burst p95 latency | Burst p99 latency | Max latency | Success | Max replicas | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| spike | HPA60 baseline | 197.91 rps | 85.175 ms | 128.983 ms | 276.229 ms | 100.00% | 27 | `experiments/thesis-evidence/main/hpa60-cpu-hpa-max70/target_60/spike/20260514T095402Z-hpa-t60-spike-04-0d577/` |
| spike | Hybrid-SA MPC | 199.90 rps | 52.483 ms | 71.048 ms | 97.157 ms | 100.00% | 28 | `experiments/archive/supporting/hybrid-common-max70/spike/20260514T220058Z-es_safety-spike-07-fcede/` |

For this tracked pair, Hybrid-SA MPC lowers burst p95 latency by about 38%, p99 latency by about 45%, and max latency by about 65% versus the HPA60 baseline. Both runs report 100% success.

## Why This Matters

Reactive HPA waits for measured resource pressure. The MPC path forecasts short-horizon demand and chooses a replica target before the spike fully drains through the system. The interesting question is not whether MPC can scale more, but whether it can scale earlier with fewer latency spikes and reproducible evidence.

## What Is Still Open

| Gap | Why it matters | Useful contribution |
| --- | --- | --- |
| More aggregate tables | One trace is a proof point, not a paper-grade result. | Rebuild multi-run summaries from `experiments/MANIFEST.md`. |
| More comparator charts | Readers need HPA, proxy-HPA, no-QP, and Hybrid-SA side by side. | Add figures from existing `phase-summary.csv` and `control-summary.csv` files. |
| Faster local demo | Users need to see value in minutes. | Improve offline and Docker quickstarts. |
| Dashboard storytelling | Grafana previews need metric meaning and import steps. | Link panels to PromQL and run artifacts. |

## Evidence Map

Canonical evidence aliases live in `experiments/EVIDENCE_MAP.csv`. Packaging and rebuild commands live in `experiments/MANIFEST.md`.

Important aliases:

- `thesis/main/hpa60_cpu_hpa_max70`: primary CPU-HPA60 baseline.
- `thesis/main/hybrid_sa_max70_tuned`: primary tuned Hybrid-SA evidence root used for corrected thesis discussion.
- `archive/supporting/hybrid_common_max70`: supporting Hybrid refresh run used by the visual spike proof card.

## Rebuild Commands

Summarize one saved MPC run:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_run \
  --run-dir experiments/archive/supporting/hybrid-common-max70/spike/20260514T220058Z-es_safety-spike-07-fcede \
  --out-phase-csv /tmp/phase-summary.csv \
  --out-control-csv /tmp/control-summary.csv
```

Rebuild resource proxy summaries when the full local evidence archive is present:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_costs \
  --hpa-root experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  --hybrid-root experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  --out-csv /tmp/mpc-cost-summary.csv \
  --out-aggregate-csv /tmp/mpc-cost-aggregate.csv
```

## Reading Rules

- Treat the table as a current snapshot, not a final generalized claim.
- Prefer committed summaries over screenshots.
- Link new claims to exact run directories or rebuild commands.
- Keep bulky generated artifacts out of Git unless they are curated evidence.
