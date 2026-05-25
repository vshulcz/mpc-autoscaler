# Public Interface

This document lists the repository surfaces that are stable enough for examples, scripts, and external references. The project remains research software, so stability means documented change process, not production support.

## Stable Enough For Public Examples

| Surface | Contract | Reference |
| --- | --- | --- |
| `toy-load` HTTP API | `GET /`, `/healthz`, `/readyz`, `/work`, and `/metrics`; unsupported methods return `405`. | [`toy-load/README.md#http-api`](../toy-load/README.md#http-api) |
| `toy-load` work parameters | `cpu_ms`, `sleep_ms`, `jitter_ms`, `payload_bytes`, `err_rate`, and `id`. | [`toy-load/README.md#work-parameters`](../toy-load/README.md#work-parameters) |
| Prometheus metrics | Request count, latency histogram, in-flight requests, work knobs, and error counters. | [`toy-load/README.md#metrics`](../toy-load/README.md#metrics) |
| Helm values | Values are schema-checked through `values.schema.json`. | [`toy-load/deploy/helm/toy-load/values.schema.json`](../toy-load/deploy/helm/toy-load/values.schema.json) |
| Trace CSV schema | Required columns: `step`, `timestamp_s`, `rps`; optional `phase_idx`. | [`docs/REPRODUCIBILITY.md#tier-2-offline-mpc-simulation`](REPRODUCIBILITY.md#tier-2-offline-mpc-simulation) |
| Analysis CLIs | Entry points under `analysis/pyproject.toml`, including `mpc-validate-trace`, `mpc-offline-sim`, `mpc-summarize-run`, and `mpc-control-loop`. | [`analysis/README.md#cli-commands`](../analysis/README.md#cli-commands) |
| Evidence aliases | Canonical names map to raw local paths through `experiments/EVIDENCE_MAP.csv`. | [`experiments/EVIDENCE_MAP.csv`](../experiments/EVIDENCE_MAP.csv) |
| Control Loop Safety flags | Stable: `--dry-run` (demo/safe mode), omit `--apply` for recommendations only. Unstable: `--apply` (live-cluster mode, requires namespace, deployment, Prometheus, and RBAC review). | docs/API.md#control-loop-safety-contract |

## Control Loop Safety Contract

`mpc-control-loop` defaults to recommendation mode. It writes decisions to `--log-csv` and does not scale Kubernetes resources unless `--apply` is passed.

Use `--dry-run` or omit `--apply` for demos, reproduction checks, and exploratory tuning. Treat `--apply` as a live-cluster experiment mode that requires explicit namespace, deployment, Prometheus, and RBAC review.

## Not Stable API

- Internal Python module layout outside documented CLIs.
- Raw experiment directory names except aliases in `experiments/EVIDENCE_MAP.csv`.
- SVG and HTML class names in `site/`.
- Exact benchmark numbers until they are listed in `docs/BENCHMARK_MATRIX.md` or `docs/RESULTS.md` with evidence paths.

## Change Policy

Before changing a public surface:

1. Update the relevant README or docs page in the same PR.
2. Keep one release note or migration note for changed CLI flags, endpoint parameters, metric names, or trace columns.
3. Prefer additive changes for `v0.x` unless old behavior is misleading or unsafe.
4. Keep caveats visible when API changes affect result interpretation.
