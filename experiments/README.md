# Experiments

`experiments/` stores local thesis run artifacts. Raw runs are intentionally
ignored by Git; committed files here are the artifact index only.

## Index Files

- `MANIFEST.md`: artifact packaging policy, canonical aliases, export commands.
- `EVIDENCE_MAP.csv`: machine-readable map from clean artifact names to raw paths.
- `ARCHIVE_INDEX.md`: inventory of historical roots kept for audit but not used as primary thesis evidence.
- `package-thesis-evidence.sh`: local archive builder for raw thesis evidence.
- `templates/run-meta.template.yaml`: metadata schema for run directories.

## Naming Policy

Top-level artifact roots use clean names:

- `thesis-evidence/main/`: roots used directly in thesis main comparison.
- `thesis-evidence/comparators/`: comparator roots used in thesis discussion.
- `archive/supporting/`: supporting sweeps and refresh runs.
- `archive/superseded/`: replaced evidence kept for audit.
- `archive/historical/`, `archive/tuning/`, `archive/legacy-transfer/`, `archive/scratch/`: non-primary raw artifacts.

Inside each root, runner-generated run directories keep original timestamps and
IDs because those names appear in logs and metadata. Use canonical aliases from
`EVIDENCE_MAP.csv` when referring to artifacts in text, tables, archives, or
handoff notes.

## Evidence Aliases

Committed evidence aliases in [`experiments/EVIDENCE_MAP.csv`](EVIDENCE_MAP.csv) map to
local or archived run roots. Bulky raw run directories may stay outside
Git and are tracked separately via [`experiments/MANIFEST.md`](MANIFEST.md).

## Evidence Alias Glossary

These short aliases come from `EVIDENCE_MAP.csv` and keep thesis notes,
figures, and handoff text stable even when raw run directories are long.

| Alias | Meaning |
| --- | --- |
| `thesis/main/hpa60_cpu_hpa_max70` | Primary CPU-HPA60 baseline under the max70 comparison setup. |
| `thesis/main/hybrid_sa_max70_tuned` | Primary tuned Hybrid-SA evidence root used for corrected thesis results. |
| `thesis/comparator/proxy_hpa_safety_max70` | Reactive proxy-HPA plus safety comparator for step, spike, and seasonality scenarios. |
| `thesis/comparator/no_qp_reactive_max70` | No-QP reactive comparator for step, spike, and seasonality scenarios. |
| `thesis/comparator/vanilla_hpa80_max70` | Vanilla HPA80 comparator for step, spike, and seasonality scenarios. |

## Current Runners

Run these from repository root only when you intend to change a live Kubernetes
test cluster:

```bash
bash loadgen/scripts/run_hpa_experiment_incluster.sh <step|spike|seasonality>
bash loadgen/scripts/run_mpc_experiment_incluster.sh <step|spike|seasonality>
bash loadgen/scripts/run_hpa_target_grid.sh
bash loadgen/scripts/run_mpc_isolation_batch.sh
bash loadgen/scripts/run_normalized_night_pipeline.sh
```

These commands create new run directories under ignored `experiments/_runs/` by default.
Do not run them while rebuilding tables or figures from saved artifacts.

## Rebuilding Saved Summaries

No Kubernetes cluster is required for saved artifact summaries. See
`MANIFEST.md` for exact commands and canonical evidence paths.

## External Archive

Build the evidence archive locally:

```bash
bash experiments/package-thesis-evidence.sh /tmp/mpc-autoscaler-thesis-evidence.tar.gz
```

The script writes both the `.tar.gz` and `.sha256` checksum file.
