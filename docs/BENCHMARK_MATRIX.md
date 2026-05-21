# Benchmark Matrix

This page separates public numeric claims from indexed evidence coverage. It is a matrix for readers and contributors, not a scoreboard.

## Published Numeric Claims

Only the cells below have public numbers in this repository today.

| Scenario | Controller | Burst throughput | Burst p95 latency | Burst p99 latency | Max latency | Success | Max replicas | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `spike` | HPA60 baseline | 197.91 rps | 85.175 ms | 128.983 ms | 276.229 ms | 100.00% | 27 | `experiments/thesis-evidence/main/hpa60-cpu-hpa-max70/target_60/spike/20260514T095402Z-hpa-t60-spike-04-0d577/` |
| `spike` | Hybrid-SA MPC | 199.90 rps | 52.483 ms | 71.048 ms | 97.157 ms | 100.00% | 28 | `experiments/archive/supporting/hybrid-common-max70/spike/20260514T220058Z-es_safety-spike-07-fcede/` |

Reading rule: this is one tracked spike pair. It supports a concrete research narrative and a reproducibility check. It does not prove that MPC generally beats HPA.

## Evidence Coverage

`Indexed` means the evidence root is listed in `experiments/EVIDENCE_MAP.csv` and the full raw archive can be rebuilt or exported outside Git. `Published` means this repository contains numeric values tied to exact run directories.

| Controller family | Evidence alias | `step` | `spike` | `seasonality` | Current public status |
| --- | --- | --- | --- | --- | --- |
| CPU HPA60 baseline | `thesis/main/hpa60_cpu_hpa_max70` | Indexed | Published numeric pair | Indexed | Primary reactive baseline. |
| Hybrid-SA MPC | `thesis/main/hybrid_sa_max70_tuned` | Indexed | Indexed | Indexed | Primary tuned predictive controller; current public spike numbers use supporting refresh run. |
| Proxy-HPA plus safety | `thesis/comparator/proxy_hpa_safety_max70` | Indexed | Indexed | Indexed | Comparator root indexed; public aggregate table still needed. |
| No-QP reactive policy | `thesis/comparator/no_qp_reactive_max70` | Indexed | Indexed | Indexed | Comparator root indexed; public aggregate table still needed. |
| Vanilla HPA80 | `thesis/comparator/vanilla_hpa80_max70` | Indexed | Indexed | Indexed | Comparator root indexed; public aggregate table still needed. |

## Matrix Rebuild Path

When the evidence archive is present under `experiments/thesis-evidence/`, rebuild primary HPA-vs-Hybrid resource summaries with:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_costs \
  --hpa-root experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  --hybrid-root experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  --out-csv /tmp/mpc-cost-summary.csv \
  --out-aggregate-csv /tmp/mpc-cost-aggregate.csv
```

The broader comparator matrix should be published only after each cell has:

- exact evidence root or committed summary path;
- scenario, controller, and tuning parameters;
- p95, p99, max latency, success ratio, and replica behavior;
- statement of whether values are single-run, representative, or aggregate;
- caveat update in `docs/LIMITATIONS.md` if the result changes interpretation.

## Useful Next PR

Best next contribution: add a generated `benchmark-matrix.csv` from existing evidence archives and keep this Markdown page as the human-readable view.
