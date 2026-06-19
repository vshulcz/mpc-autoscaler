# Results

Single source of truth for current experiment evidence. Only claims backed by committed summaries or documented evidence aliases appear here.

## Current observation

Under a representative 200 rps spike, the predictive controller showed lower latency than the reactive HPA baseline while preserving 100% success. This is a snapshot, not an aggregate benchmark.

| Scenario | Controller | Burst throughput | Burst p95 | Burst p99 | Max latency | Success | Max replicas | Evidence | Index |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `spike` | HPA60 baseline | 197.91 rps | 85.175 ms | 128.983 ms | 276.229 ms | 100.00% | 27 | `experiments/thesis-evidence/main/hpa60-cpu-hpa-max70/target_60/spike/20260514T095402Z-hpa-t60-spike-04-0d577/` | [`EVIDENCE_MAP.csv`](../experiments/EVIDENCE_MAP.csv) |
| `spike` | Hybrid-SA MPC  | 199.90 rps | 52.483 ms |  71.048 ms |  97.157 ms | 100.00% | 28 | `experiments/archive/supporting/hybrid-common-max70/spike/20260514T220058Z-es_safety-spike-07-fcede/`         | [`EVIDENCE_MAP.csv`](../experiments/EVIDENCE_MAP.csv) |

For this pair Hybrid-SA MPC lowers burst p95 by ~38%, p99 by ~45%, and max latency by ~65%. See [`METHODOLOGY.md`](METHODOLOGY.md) and [`LIMITATIONS.md`](LIMITATIONS.md) before generalising.

## Why it matters

Reactive HPA waits for measured pressure. The MPC path forecasts short-horizon demand and picks a replica target before the spike fully drains through the system. The question is not whether MPC can scale more, but whether it can scale earlier with fewer tail-latency spikes and reproducible evidence.

## Evidence coverage

`Indexed` = evidence root listed in [`experiments/EVIDENCE_MAP.csv`](../experiments/EVIDENCE_MAP.csv), full raw archive can be rebuilt or exported outside Git. `Published` = repository contains numeric values tied to exact run directories.

| Controller family   | Evidence alias                              | `step`  | `spike`                  | `seasonality` | Public status |
| ---                 | ---                                         | ---     | ---                      | ---           | --- |
| CPU HPA60 baseline  | `thesis/main/hpa60_cpu_hpa_max70`           | Indexed | **Published numeric pair** | Indexed     | Primary reactive baseline. |
| Hybrid-SA MPC       | `thesis/main/hybrid_sa_max70_tuned`         | Indexed | Indexed                  | Indexed       | Primary tuned predictive controller; current public spike numbers use supporting refresh run. |
| Proxy-HPA + safety  | `thesis/comparator/proxy_hpa_safety_max70`  | Indexed | Indexed                  | Indexed       | Comparator root indexed; public aggregate table still missing. |
| No-QP reactive      | `thesis/comparator/no_qp_reactive_max70`    | Indexed | Indexed                  | Indexed       | Comparator root indexed; public aggregate table still missing. |
| Vanilla HPA80       | `thesis/comparator/vanilla_hpa80_max70`     | Indexed | Indexed                  | Indexed       | Comparator root indexed; public aggregate table still missing. |

Canonical aliases:

- `thesis/main/hpa60_cpu_hpa_max70` — primary CPU-HPA60 baseline.
- `thesis/main/hybrid_sa_max70_tuned` — primary tuned Hybrid-SA evidence root used for the corrected thesis discussion.
- `archive/supporting/hybrid_common_max70` — supporting Hybrid refresh run used by the visual spike snapshot.

## What is still open

| Gap | Why it matters | Useful contribution |
| --- | --- | --- |
| More aggregate tables | One trace is a single-run result, not a paper-grade result. | Rebuild multi-run summaries from [`experiments/MANIFEST.md`](../experiments/MANIFEST.md). |
| More comparator charts | Readers need HPA, proxy-HPA, no-QP, and Hybrid-SA side by side. | Add figures from existing `phase-summary.csv` / `control-summary.csv` files. |
| Faster local demo | New users need value in minutes. | Improve offline and Docker quickstarts. |
| Dashboard storytelling | Grafana previews need metric meaning and import steps. | Link panels to PromQL and run artifacts. |

Before publishing a new comparator cell, each row needs: exact evidence root or committed summary; scenario, controller, and tuning parameters; p95, p99, max latency, success ratio, replica behaviour; statement of single-run / representative / aggregate; caveat update in [`LIMITATIONS.md`](LIMITATIONS.md) if interpretation changes.

## Rebuild commands

Summarise one saved MPC run:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_run \
  --run-dir experiments/archive/supporting/hybrid-common-max70/spike/20260514T220058Z-es_safety-spike-07-fcede \
  --out-phase-csv /tmp/phase-summary.csv \
  --out-control-csv /tmp/control-summary.csv
```

Rebuild resource-proxy summaries (when the full local evidence archive is present):

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_costs \
  --hpa-root experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  --hybrid-root experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  --out-csv /tmp/mpc-cost-summary.csv \
  --out-aggregate-csv /tmp/mpc-cost-aggregate.csv
```

## Reading rules

- Treat the table as a current snapshot, not a generalised claim.
- Prefer committed summaries over screenshots.
- Link new claims to exact run directories or rebuild commands.
- Keep bulky generated artifacts out of Git unless they are curated evidence.
