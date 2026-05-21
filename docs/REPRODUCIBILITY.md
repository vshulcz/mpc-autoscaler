# Reproducibility

This repository separates quick checks, offline simulation, saved-artifact analysis, and live Kubernetes experiments. Use the lightest tier that answers your question.

## Tier 1: Local Quality Gates

No Kubernetes cluster is required.

```bash
make check
```

This runs Go formatting checks, `go vet`, Go tests, Helm lint/template rendering, dependency-light Python tests, Python bytecode compilation, shell syntax checks, and dashboard JSON validation.

## Tier 2: Offline MPC Simulation

Install the analysis package from repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e analysis
```

Generate and simulate a trace:

```bash
mpc-generate-synthetic-trace \
  --scenario spike \
  --out analysis/out/spike.csv

mpc-validate-trace \
  --trace-csv analysis/out/spike.csv

mpc-offline-sim \
  --trace-csv analysis/out/spike.csv \
  --out-dir analysis/out/offline/spike
```

Generated files under `analysis/out/` are ignored by Git.

Offline trace CSVs must include `step`, `timestamp_s`, and `rps`. Units are
sample index, seconds, and requests/second. Optional `phase_idx` labels can be
used by grid-search tooling. `mpc-validate-trace` reports missing columns and
malformed row values such as nonnumeric `rps`, negative `timestamp_s`, or
noninteger `step` values.

## Tier 3: Saved Evidence Summaries

No cluster is required when saved experiment artifacts are available under `experiments/thesis-evidence/`.

```bash
PYTHONPATH=analysis python3 -m mpc_autoscaler_analysis.cli.summarize_costs \
  --hpa-root experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  --hybrid-root experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  --out-csv /tmp/mpc-cost-summary.csv \
  --out-aggregate-csv /tmp/mpc-cost-aggregate.csv
```

See `experiments/MANIFEST.md` for canonical evidence roots and export commands.

## Tier 4: Live Kubernetes Experiments

Live runs require a Kubernetes cluster, `kubectl`, Helm, Prometheus access, and a deployed `toy-load` service.

Deploy workload:

```bash
helm upgrade --install toy-load toy-load/deploy/helm/toy-load \
  --namespace default \
  --create-namespace
```

Run one HPA baseline:

```bash
bash loadgen/scripts/run_hpa_experiment_incluster.sh step
```

Run one MPC experiment:

```bash
bash loadgen/scripts/run_mpc_experiment_incluster.sh step
```

Set `MPC_APPLY=0` to collect MPC recommendations without scaling the Deployment.

## Tier 5: Release Reproduction

Release preflight:

```bash
make check
make coverage
helm template toy-load toy-load/deploy/helm/toy-load \
  --namespace default \
  --set prometheusOperator.enabled=true \
  --set dashboard.enabled=true >/dev/null
kubectl kustomize deploy/monitoring >/dev/null
```

Full release process lives in `docs/RELEASE.md`.

## Artifact Policy

- Commit source code, tests, small traces, dashboards, manifests, and evidence indices.
- Keep raw experiment outputs under ignored `experiments/_runs/` or external archives.
- Keep generated analysis outputs under ignored `analysis/out/`.
- Use `experiments/package-thesis-evidence.sh` to export curated evidence archives with checksums.
