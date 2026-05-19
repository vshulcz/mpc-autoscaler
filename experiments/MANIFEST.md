# Experiment Artifact Manifest

This manifest documents thesis artifacts without committing raw generated data.
Paths are relative to repository root.

## Packaging Policy

Best-practice artifact packages keep raw data immutable, put clean names in a
manifest, separate raw and derived data, include exact rebuild commands, and ship
checksums for external archives. This follows common artifact-evaluation and
research-data packaging practice: README first, machine-readable manifest,
provenance metadata, reproducible derived outputs, and optional DOI archive.

Curated artifact roots use clean names under `thesis-evidence/` and `archive/`.
Runner-generated leaf run directories keep original timestamps and IDs to
preserve provenance. Use aliases from `EVIDENCE_MAP.csv` in documentation.

## Committed Index

| File | Purpose |
| --- | --- |
| `experiments/README.md` | Short directory entry point. |
| `experiments/MANIFEST.md` | Packaging policy, final evidence roots, rebuild and export commands. |
| `experiments/EVIDENCE_MAP.csv` | Canonical aliases mapped to raw local paths. |
| `experiments/ARCHIVE_INDEX.md` | Archive classification for non-primary roots. |
| `experiments/package-thesis-evidence.sh` | Local builder for external raw-evidence archive. |
| `experiments/templates/run-meta.template.yaml` | Metadata schema produced by current runners. |

## Primary Thesis Evidence

| Canonical alias | Raw path | Role |
| --- | --- | --- |
| `thesis/main/hpa60_cpu_hpa_max70` | `experiments/thesis-evidence/main/hpa60-cpu-hpa-max70` | CPU-HPA60 baseline under the max70 comparison setup. |
| `thesis/main/hybrid_sa_max70_tuned` | `experiments/thesis-evidence/main/hybrid-sa-max70-tuned` | Final tuned Hybrid-SA evidence root used for corrected latency/resource discussion. |
| `thesis/comparator/proxy_hpa_safety_max70` | `experiments/thesis-evidence/comparators/proxy-hpa-safety-max70` | Reactive proxy-HPA+safety comparator. |
| `thesis/comparator/no_qp_reactive_max70` | `experiments/thesis-evidence/comparators/no-qp-reactive-max70` | No-QP reactive comparator. |
| `thesis/comparator/vanilla_hpa80_max70` | `experiments/thesis-evidence/comparators/vanilla-hpa80-max70` | Vanilla HPA80 comparator. |

## Supporting And Superseded Evidence

| Raw path | Status | Notes |
| --- | --- | --- |
| `experiments/archive/supporting/hpa-target-grid-argofix` | supporting | Earlier HPA target sweep; useful audit trail for target selection. |
| `experiments/archive/superseded/hybrid-argofix-3scenarios` | superseded | Earlier Hybrid-SA root before max70 tuned rerun. |
| `experiments/archive/superseded/hybrid-sa-max70-onepass` | superseded | Earlier max70 Hybrid-SA run, superseded by `thesis/main/hybrid_sa_max70_tuned`. |
| `experiments/archive/supporting/hybrid-common-max70` | supporting | Refresh run for common Hybrid settings, not the primary tuned Hybrid-SA root. |
| `experiments/archive/superseded/no-qp-reactive-pre-max70` | superseded | Earlier no-QP comparator before max70 refresh. |
| `experiments/archive/superseded/vanilla-hpa80-pre-max70` | superseded | Earlier HPA80 comparator before max70 refresh. |

## Run Directory Schema

Common files:

- `run-meta.yaml`: scenario, mode, timestamps, workload knobs, Git snapshot, artifact names.
- `phases.csv`: generated load profile phases.
- `target.txt`: target URL used by Vegeta.
- `incluster-report.txt`: per-phase Vegeta report captured from in-cluster pod logs.
- `hpa-live.yaml`: HPA snapshot when present.
- `deployment-live.yaml`: Deployment snapshot.

HPA run additions:

- `replica-watch.csv`: sampled Deployment and HPA replica counts when replica watch is enabled.

MPC run additions:

- `mpc-control-log.csv`: online MPC controller decision log.
- `mpc-loop.log`: controller stdout/stderr.
- `phase-summary.csv`: parsed load phase metrics when generated.
- `control-summary.csv`: parsed control metrics when generated.

Root-level derived summaries:

- `cost-detail.csv`: per-scenario resource proxy rows.
- `cost-aggregate.csv`: aggregate resource proxy rows.
- `*_cost_rows.csv` / `*_cost_aggregate.csv`: comparator-specific resource proxy summaries.

## Rebuild Commands

Summarize one saved MPC run:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_run \
  --run-dir experiments/thesis-evidence/main/hybrid-sa-max70-tuned/spike/20260514T171519Z-es_safety-spike-r1 \
  --out-phase-csv /tmp/phase-summary.csv \
  --out-control-csv /tmp/control-summary.csv
```

Rebuild HPA60-vs-Hybrid resource proxy summaries:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_costs \
  --hpa-root experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  --hybrid-root experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  --out-csv /tmp/mpc-cost-summary.csv \
  --out-aggregate-csv /tmp/mpc-cost-aggregate.csv
```

## Archive Export

Export the primary thesis evidence plus index files:

```bash
bash experiments/package-thesis-evidence.sh /tmp/mpc-autoscaler-thesis-evidence.tar.gz
```

Equivalent explicit command:

```bash
tar --exclude='__pycache__' --exclude='.DS_Store' -czf /tmp/mpc-autoscaler-thesis-evidence.tar.gz \
  experiments/README.md \
  experiments/MANIFEST.md \
  experiments/EVIDENCE_MAP.csv \
  experiments/ARCHIVE_INDEX.md \
  experiments/package-thesis-evidence.sh \
  experiments/templates/run-meta.template.yaml \
  experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  experiments/thesis-evidence/comparators/proxy-hpa-safety-max70 \
  experiments/thesis-evidence/comparators/no-qp-reactive-max70 \
  experiments/thesis-evidence/comparators/vanilla-hpa80-max70
```

Create checksum after export if not using the script:

```bash
shasum -a 256 /tmp/mpc-autoscaler-thesis-evidence.tar.gz
```

For a full local audit archive, archive all of `experiments/` with the same
exclusions. Do not edit raw saved run files while preparing either archive.
