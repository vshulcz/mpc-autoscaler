# Experiment Archive Index

This file classifies local raw artifacts that are kept for audit but are not the
primary thesis evidence package. Raw paths are not renamed or moved.

## Top-Level Roots

| Path | Archive class | Notes |
| --- | --- | --- |
| `experiments/archive/historical/baseline/` | historical-baseline | Older HPA baseline runs. |
| `experiments/archive/calibration/` | calibration | Small calibration notes/artifacts. |
| `experiments/archive/historical/hpa-custom-metrics/` | historical-baseline | Experiments with custom HPA metrics. |
| `experiments/archive/historical/mpc-early/` | historical-mpc | Early MPC artifacts. |
| `experiments/archive/historical/mpc-ablation/` | historical-mpc | Early ablation batch. |
| `experiments/archive/historical/mpc-ablation-v3/` | historical-mpc | Later ablation batch. |
| `experiments/archive/historical/mpc-component-v3-remote/` | historical-mpc | Remote component diagnostics. |
| `experiments/archive/historical/mpc-component-v3-remote-full/` | historical-mpc | Full remote component diagnostics. |
| `experiments/archive/historical/mpc-isolation-v2-clean/` | historical-mpc | Isolation diagnostics before max70 refresh. |
| `experiments/archive/tuning/mpc-normalized-full-v1/` | tuning | Normalized objective tuning. |
| `experiments/archive/tuning/mpc-normalized-isolation-v1/` | tuning | Normalized objective isolation. |
| `experiments/archive/tuning/mpc-normalized-night-v1/` | tuning | Long candidate-selection pipeline. |
| `experiments/archive/tuning/mpc-normalized-retune-v1/` | tuning | Retuning run. |
| `experiments/archive/tuning/mpc-normalized-safety-smoke-v1/` | tuning | Safety smoke test. |
| `experiments/archive/tuning/mpc-normalized-spike-tune-v1/` | tuning | Spike-specific tuning. |
| `experiments/archive/historical/mpc-online/` | historical-mpc | Earlier online MPC runs. |
| `experiments/archive/tuning/mpc-resource-tune-v2-rest/` | tuning/archive | Remaining resource-tuning roots after primary/supporting roots were extracted. |
| `experiments/archive/historical/mpc-sensitivity/` | historical-mpc | Sensitivity study. |
| `experiments/archive/historical/mpc-sensitivity-v3/` | historical-mpc | Later sensitivity study. |
| `experiments/archive/scratch/progress/` | scratch | Batch logs and local progress records. |
| `experiments/archive/legacy-transfer/publication-transfer/` | legacy-export | Partial old export, not current thesis package. |
| `experiments/archive/legacy-transfer/transfer-v3/` | legacy-export | Transfer artifacts. |
| `experiments/archive/legacy-transfer/transfer2/` | legacy-export | Transfer artifacts. |
| `experiments/archive/helpers/gen-hpa-timeseries.py` | local-helper | Hard-coded helper, not publication entry point. |
| `experiments/archive/helpers/vary-copies.py` | local-helper | Hard-coded helper, not publication entry point. |
| `experiments/archive/scratch/v3-extra-series-20260417T161019Z.log` | scratch | Local batch log. |
| `experiments/archive/scratch/v3-extra-series-20260417T161019Z-run-registry.csv` | scratch | Local batch registry. |

## Resource-Tuning Extracted Roots

| Path suffix | Archive class | Notes |
| --- | --- | --- |
| `experiments/thesis-evidence/main/hpa60-cpu-hpa-max70` | primary-evidence | Canonical alias `thesis/main/hpa60_cpu_hpa_max70`. |
| `experiments/thesis-evidence/main/hybrid-sa-max70-tuned` | primary-evidence | Canonical alias `thesis/main/hybrid_sa_max70_tuned`. |
| `experiments/thesis-evidence/comparators/proxy-hpa-safety-max70` | primary-evidence | Canonical alias `thesis/comparator/proxy_hpa_safety_max70`. |
| `experiments/thesis-evidence/comparators/no-qp-reactive-max70` | primary-evidence | Canonical alias `thesis/comparator/no_qp_reactive_max70`. |
| `experiments/thesis-evidence/comparators/vanilla-hpa80-max70` | primary-evidence | Canonical alias `thesis/comparator/vanilla_hpa80_max70`. |
| `experiments/archive/supporting/hpa-target-grid-argofix` | supporting | Earlier target sweep. |
| `experiments/archive/superseded/hybrid-argofix-3scenarios` | superseded | Earlier Hybrid-SA root. |
| `experiments/archive/superseded/hybrid-sa-max70-onepass` | superseded | Earlier max70 Hybrid-SA run. |
| `experiments/archive/supporting/hybrid-common-max70` | supporting | Common Hybrid refresh run. |
| `experiments/archive/tuning/mpc-resource-tune-v2-rest` | archive | Remaining resource-tuning roots retained locally for audit trail. |

If a future table uses one of the archived roots, add a row to
`EVIDENCE_MAP.csv` instead of relying on the raw directory name.
