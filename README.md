# mpc-autoscaler

[![CI](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/ci.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/ci.yaml)
[![Release](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/release.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/release.yaml)
[![Tag Release](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/tag-release.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/tag-release.yaml)
[![Pages](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/pages.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/pages.yaml)
[![Security](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/security.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/security.yaml)
[![CodeQL](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/codeql.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/codeql.yaml)
[![Trivy](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/trivy.yaml/badge.svg)](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/trivy.yaml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/vshulcz/mpc-autoscaler/badge)](https://securityscorecards.dev/viewer/?uri=github.com/vshulcz/mpc-autoscaler)
[![Codecov](https://codecov.io/gh/vshulcz/mpc-autoscaler/branch/main/graph/badge.svg)](https://codecov.io/gh/vshulcz/mpc-autoscaler)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Go](https://img.shields.io/badge/go-1.25-00ADD8?logo=go&logoColor=white)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Helm](https://img.shields.io/badge/helm-chart-0F1689?logo=helm&logoColor=white)
![Container](https://img.shields.io/badge/GHCR-toy--load-181717?logo=github&logoColor=white)

Predictive autoscaling playground for Kubernetes: a controllable Go workload, Helm deployment, live MPC controller, offline simulator, and reproducible experiment tooling.

The core question: can a small Model Predictive Control loop anticipate demand and scale more smoothly than reactive HPA baselines under step, spike, and seasonal traffic?

Docs site: <https://vshulcz.github.io/mpc-autoscaler/>.

Roadmap board: <https://github.com/users/vshulcz/projects/2>. Active work is tracked through milestones `v0.2.0`, `thesis-reproducibility`, and `v0.3.0`.

Contribution guidelines live in `CONTRIBUTING.md`. Support guidance lives in `SUPPORT.md`. Release steps are documented in `docs/RELEASE.md`. Security reporting guidance lives in `SECURITY.md`.

## Highlights

- controllable HTTP workload with Prometheus metrics, Helm chart, raw manifests, and GHCR release image;
- online MPC controller that can run in dry-run mode or apply Kubernetes scale decisions;
- offline simulator and grid-search tooling for controller tuning;
- repeatable HPA and MPC runners for `step`, `spike`, and `seasonality` scenarios;
- curated evidence policy that keeps bulky raw runs out of Git while preserving provenance;
- CI, release, dependency-update, issue-template, and security automation for public maintenance.

The project combines three parts:

- `toy-load/`: a standalone Go module with a controllable HTTP workload service. See `toy-load/README.md` for API details and the [runtime configuration table](toy-load/README.md#configuration).
- `analysis/`: offline and online MPC tooling used to tune and evaluate the controller.
- `deploy/`, `dashboards/`, and `loadgen/`: ArgoCD applications, monitoring assets, Grafana dashboards, and repeatable load-generation scripts. See `loadgen/README.md` for runner details.

## Scope

This repository is intended for controlled experiments rather than for production use. The goal is to compare a reactive HPA-style policy against an MPC-based controller under reproducible traffic profiles.

Supported experiment scenarios:

- `step`: sustained increase in load.
- `spike`: short high-intensity burst.
- `seasonality`: smooth sinusoidal variation.

## Architecture

```mermaid
flowchart LR
  Load[Load profiles] --> Workload[toy-load /work]
  Workload --> Metrics[Prometheus metrics]
  Metrics --> HPA[HPA baseline]
  Metrics --> MPC[MPC controller]
  HPA --> Scale[Kubernetes scale target]
  MPC --> Scale
  Scale --> Workload
  Runs[Run artifacts] --> Analysis[Analysis package]
  Analysis --> Results[Summaries and figures]
```

See `docs/ARCHITECTURE.md` for component boundaries, data flow, and extension points.

## Prerequisites

- Go `1.25`
- Python `3.11+`
- Docker
- `kubectl`
- Helm
- access to a Kubernetes cluster for online experiments

Optional but useful:

- `vegeta` for local load generation
- `coverage.py` for local Python coverage reports
- a local virtual environment in `.venv/` for Python tooling

## Repository Layout

```text
toy-load/                      Standalone Go module for the controllable workload service
  cmd/toy-load/                Go application entry point
  internal/                    Config, HTTP handling, metrics, and workload simulation
  deploy/helm/toy-load/        Helm chart for the service
  deploy/manifests/            Raw Kubernetes manifests for the service
analysis/
  mpc_autoscaler_analysis/     Python package for offline simulation, online control, and artifact summaries
  mpc_autoscaler_analysis/data/traces/
                                Small input traces for offline simulations
  tests/                       Dependency-light unit tests for analysis tooling
deploy/
  argocd/                      ArgoCD applications
  monitoring/                  Kustomize monitoring stack manifests used in experiments
dashboards/                    Grafana dashboard JSON
loadgen/scripts/               Local and in-cluster load-generation entry points
docs/                          Architecture, reproducibility, and release notes
```

New experiment artifacts are written to ignored `experiments/_runs/` by default.
Curated local evidence and archive roots stay ignored under `experiments/`; the
repository commits only lightweight indices and packaging instructions.

## Main Entry Points

These are the scripts and commands you are most likely to use:

- `make -C toy-load run`: run the service locally.
- `bash loadgen/scripts/run_hpa_experiment_incluster.sh <scenario>`: run one HPA baseline experiment in-cluster.
- `bash loadgen/scripts/run_mpc_experiment_incluster.sh <scenario>`: run one MPC-controlled experiment in-cluster.
- `bash loadgen/scripts/run_hpa_mpc_batch.sh [N_MPC [N_HPA]]`: run matched HPA and MPC batches.
- `bash loadgen/scripts/run_mpc_v3_batch.sh [scenario|all]`: run the calibrated MPC-only batch.
- `mpc-offline-sim ...`: run the offline simulator on a trace after installing `analysis`.
- `docs/REPRODUCIBILITY.md`: choose the lightest reproduction path for local checks, offline simulation, saved evidence, or live cluster runs.

## Local Development

Run the service:

```bash
make toy-load-run
curl "http://localhost:9090/work?cpu_ms=10&jitter_ms=5"
curl http://localhost:9090/metrics
```

Useful Make targets:

```bash
make help
make fmt
make check
make coverage
make toy-load-run
make toy-load-build
```

`make check` runs the toy-load checks used in CI: formatting check, `go vet`, tests, Helm lint, and Helm template rendering.
`make coverage` writes Go and Python coverage reports under ignored `coverage/`.

## Python Environment

For offline analysis and the online MPC controller, create a virtual environment and install the analysis package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e analysis
```

Example offline run:

```bash
mpc-generate-synthetic-trace \
  --scenario step \
  --out analysis/out/step.csv

mpc-offline-sim \
  --trace-csv analysis/out/step.csv \
  --out-dir analysis/out/offline/step
```

## Deployment

Deploy with Helm:

```bash
helm upgrade --install toy-load toy-load/deploy/helm/toy-load \
  --namespace default \
  --create-namespace
```

Or apply the raw manifests:

```bash
kubectl apply -f toy-load/deploy/manifests
```

Monitoring manifests require Prometheus Operator and Grafana Operator CRDs:

```bash
kubectl apply -k deploy/monitoring
```

ArgoCD application manifests live under `deploy/argocd/`.

The Helm chart defaults to `ghcr.io/vshulcz/toy-load:main`. For a pinned run, override the tag explicitly:

```bash
helm upgrade --install toy-load toy-load/deploy/helm/toy-load \
  --namespace default \
  --set image.tag=<commit-or-release-tag>
```

## Verifying Release Downloads

GitHub Releases include cross-platform `toy-load` binaries, a packaged Helm
chart, and `SHA256SUMS`. Verify downloaded assets before unpacking or installing
them.

Linux:

```bash
VERSION=v0.1.0
ARCH=amd64 # or arm64
BASE="https://github.com/vshulcz/mpc-autoscaler/releases/download/${VERSION}"

curl -LO "${BASE}/toy-load-${VERSION}-linux-${ARCH}.tar.gz"
curl -LO "${BASE}/toy-load-${VERSION#v}.tgz"
curl -LO "${BASE}/SHA256SUMS"

grep -E " (toy-load-${VERSION}-linux-${ARCH}.tar.gz|toy-load-${VERSION#v}.tgz)$" SHA256SUMS \
  | sha256sum -c -
```

macOS:

```bash
VERSION=v0.1.0
ARCH=arm64 # or amd64
BASE="https://github.com/vshulcz/mpc-autoscaler/releases/download/${VERSION}"

curl -LO "${BASE}/toy-load-${VERSION}-darwin-${ARCH}.tar.gz"
curl -LO "${BASE}/toy-load-${VERSION#v}.tgz"
curl -LO "${BASE}/SHA256SUMS"

grep -E " (toy-load-${VERSION}-darwin-${ARCH}.tar.gz|toy-load-${VERSION#v}.tgz)$" SHA256SUMS \
  | shasum -a 256 -c -
```

## Running Experiments

For a staged reproduction path, start with `docs/REPRODUCIBILITY.md`. It separates local checks, offline simulations, saved-artifact summaries, live Kubernetes experiments, and release reproduction.

Single-run baseline and MPC workflows:

```bash
# HPA baseline
bash loadgen/scripts/run_hpa_experiment_incluster.sh step

# MPC controller
bash loadgen/scripts/run_mpc_experiment_incluster.sh step
```

Matched batch runs:

```bash
# default: 5 MPC runs and 3 HPA runs per scenario
bash loadgen/scripts/run_hpa_mpc_batch.sh

# custom counts
bash loadgen/scripts/run_hpa_mpc_batch.sh 3 2
```

Calibrated MPC-only batch:

```bash
# 8 calibrated MPC v3 runs per scenario
bash loadgen/scripts/run_mpc_v3_batch.sh all
```

Batch logs are written to ignored `experiments/_runs/progress/`.

## Result Summaries

The online controller writes a CSV control log for each MPC run. A helper script converts run artifacts into compact CSV summaries:

```bash
mpc-summarize-run \
  --run-dir experiments/_runs/mpc-online/step/<run-id> \
  --out-phase-csv /tmp/step_phases.csv \
  --out-control-csv /tmp/step_control.csv
```

## MPC Formulation

The controller uses a backlog-state MPC formulation.

State update between control ticks:

```math
b_0^{(t)} = \max\!\left(0,\; b_0^{(t-1)} + \Delta t(\lambda_{t-1} - \mu\rho^\star r_{t-1})\right)
```

Optimization problem solved each tick:

```math
\min_{x,b}\; \alpha\lVert b\rVert_2^2 + \beta\lVert D x - e_1 r_t\rVert_2^2 + \gamma \mathbf{1}^{\mathsf{T}}x
```

subject to:

```math
\begin{aligned}
b_k &\ge b_{k-1} + \Delta t(\hat\lambda_{t+k} - \mu\rho^\star x_k), \\
b_k &\ge 0, \\
\lvert x_k - x_{k-1}\rvert &\le x^{\max\text{-step}}, \\
x^{\min} &\le x_k \le x^{\max}.
\end{aligned}
```

Here, $\hat\lambda$ is a short-horizon demand forecast, $\mu$ is the calibrated throughput capacity per replica, and $\rho^\star$ is the target utilisation threshold.

## Observability

Key metrics exported by `toy-load`:

| Metric | Meaning |
| --- | --- |
| `toy_http_requests_total{method,path,code}` | request count |
| `toy_http_request_duration_seconds` | request latency histogram |
| `toy_in_flight_requests` | current number of in-flight requests |
| `toy_work_cpu_ms` | requested CPU work per request |
| `toy_errors_total{reason}` | application error counters |

Useful PromQL queries:

```promql
sum(rate(toy_http_requests_total{path="/work"}[1m]))

histogram_quantile(
  0.95,
  sum(rate(toy_http_request_duration_seconds_bucket{path="/work"}[1m])) by (le)
)

toy_in_flight_requests
```

## CI And Releases

GitHub Actions runs the following checks on pushes and pull requests:

- formatting check with `gofmt`
- `go vet` in `toy-load/`
- `go test ./...` in `toy-load/`
- Go and Python coverage collection with uploaded CI artifacts
- dependency-light Python unit tests and compile checks
- shell syntax checks for experiment runners
- GitHub Actions workflow linting with `actionlint`
- JSON validation for Grafana dashboards and Helm schema
- Helm lint
- Helm template rendering
- Kustomize rendering for monitoring manifests
- CodeQL analysis for Go and Python
- Go vulnerability scanning with `govulncheck`
- Trivy filesystem and container image scanning with SARIF uploads
- OpenSSF Scorecard supply-chain checks
- dependency review on pull requests

Container images are built and published to `ghcr.io/vshulcz/toy-load` on main pushes and release runs. Tags include `main`, `sha-*`, semver release tags, and `latest` for semver releases.
The image build also publishes SBOM and provenance attestations.

Release automation is tag driven:

- run the `Tag Release` workflow with a tag like `v0.1.0`, or push an annotated `v*.*.*` tag manually;
- `Release` builds cross-platform `toy-load` binaries, packages the Helm chart, writes checksums, publishes the GHCR image, and creates a GitHub Release.

See `docs/RELEASE.md` for the full release checklist.

## Contributing

Useful contribution areas include controller comparators, traffic traces, dashboard panels, artifact parsers, Kubernetes portability, and documentation for reproducible experiments.

See `ROADMAP.md` for project directions and `CONTRIBUTING.md` before opening a pull request.

## License

Apache License 2.0. See `LICENSE`.
