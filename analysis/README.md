# MPC Autoscaler Analysis

Python package for the thesis experiments: offline MPC simulations, online
controller runs, saved-run summaries, and resource proxy estimates.

## Layout

- `mpc_autoscaler_analysis/` contains all executable analysis code.
- `mpc_autoscaler_analysis.artifacts` parses Vegeta reports, MPC control logs,
  and saved experiment directories.
- `mpc_autoscaler_analysis.mpc` contains shared MPC/QP helper functions.
- `mpc_autoscaler_analysis.offline` contains trace builders, offline simulator,
  and grid-search tools.
- `mpc_autoscaler_analysis.online` contains the Kubernetes MPC controller.
- `mpc_autoscaler_analysis.cli` contains artifact-summary CLIs.
- `mpc_autoscaler_analysis/data/traces/` contains small input traces used by
  offline simulations.
- `out/` is reserved for generated analysis outputs and is ignored by Git.

Current thesis tables are rebuilt from saved run artifacts through package CLIs;
generated outputs stay outside version control.

## Setup

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e analysis
```

Dependency-light checks can run without installing the full scientific stack:

```bash
PYTHONPATH=analysis python3 -m unittest discover -s analysis/tests
python3 -m compileall -q analysis
```

## CLI Commands

Installed entry points:

```bash
mpc-summarize-run --run-dir <run-dir> --out-phase-csv <phase.csv> --out-control-csv <control.csv>
mpc-summarize-costs --hpa-root <hpa-root> --hybrid-root <hybrid-root> --out-csv <rows.csv> --out-aggregate-csv <aggregate.csv>
mpc-control-loop --log-csv <control-log.csv> --apply [controller options]
mpc-build-trace --phases-csv <phases.csv> --out <trace.csv>
mpc-generate-synthetic-trace --scenario step --out <trace.csv>
mpc-validate-trace --trace-csv <trace.csv>
mpc-offline-sim --trace-csv <trace.csv> --out-dir <out-dir>
mpc-grid-search
mpc-realistic-grid --scenario core
```

Without installation, use module form:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_run --help
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.offline.validate_trace --help
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.offline.simulation --help
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.online.control_loop --help
```

## Thesis Reproduction

Saved experiment artifacts are not committed to this package. When the evidence
archive is available, unpack it under the repository-level `experiments/`
directory. Final thesis comparisons expect this curated layout:

```text
experiments/thesis-evidence/main/hpa60-cpu-hpa-max70/target_60/<scenario>/<run-id>
experiments/thesis-evidence/main/hybrid-sa-max70-tuned/<scenario>/<run-id>
```

To rebuild HPA-vs-Hybrid resource proxy summaries from saved artifacts:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_costs \
  --hpa-root experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  --hybrid-root experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  --out-csv /tmp/mpc-cost-summary.csv \
  --out-aggregate-csv /tmp/mpc-cost-aggregate.csv
```

This does not run new Kubernetes experiments. It reads saved `run-meta.yaml`,
`phase-summary.csv`, `replica-watch.csv`, and `mpc-control-log.csv` files.

## Offline Simulation

Trace inputs are packaged in `mpc_autoscaler_analysis/data/traces/`:

- `baseline_step_profile_dt15.csv`
- `baseline_spike_profile_dt15.csv`
- `baseline_seasonality_profile_dt15.csv`

Offline trace CSVs use this schema:

| Column | Required | Unit | Validation |
| --- | --- | --- | --- |
| `step` | yes | sample index | Integer greater than or equal to `0`. |
| `timestamp_s` | yes | seconds | Number greater than or equal to `0`. |
| `rps` | yes | requests/second | Number greater than or equal to `0`. |
| `phase_idx` | no | phase label | Integer greater than or equal to `0` when present. |

Validate a trace before running simulations:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.offline.validate_trace \
  --trace-csv analysis/mpc_autoscaler_analysis/data/traces/baseline_step_profile_dt15.csv
```

Invalid examples include:

```csv
step,rps
0,20
```

This is invalid because `timestamp_s` is missing. Malformed values are also
reported with row numbers, for example `rps=fast` or `timestamp_s=-30`.

Generated grid-search outputs are written under `analysis/out/offline/`:

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.offline.grid_search
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.offline.realistic_sim --scenario core
```

These commands require the scientific stack from `analysis/pyproject.toml`.

## Live Controller Safety

`mpc_autoscaler_analysis.online.control_loop` talks to Kubernetes. It runs in
dry-run mode by default and only calls `kubectl scale` when `--apply` is passed.
Do not use `--apply` while rebuilding thesis tables or figures.

## Data Policy

- Keep source code, tests, package metadata, and small input traces in Git.
- Keep raw experiment archives under `experiments/`; they are ignored by Git.
- Keep generated analysis outputs under `analysis/out/`; it is ignored by Git.
- Do not commit `__pycache__`, `.venv`, local load-generator results, or temporary
  CSVs created during checks.

## Test Scope

The committed unit tests cover the dependency-light package surface: report
parsing, control summaries, resource aggregation, QP helper functions, artifact
summary CLIs, and trace-building CLIs. Offline grid-search quality and live
Kubernetes behavior still require the scientific dependencies and, for the live
loop, an explicit test cluster or `--dry-run` harness.
