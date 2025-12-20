# mpc-autoscaler / toy-load

![CI](https://github.com/vshulcz/mpc-autoscaler/actions/workflows/ci.yaml/badge.svg)

`toy-load` is a stateless Go HTTP microservice that simulates controllable CPU and latency per request, surfaces Prometheus metrics, and ships with Helm/manifest deploy assets, Grafana dashboards, and vegeta-based load generators for autoscaling experiments.

### Features
- `/work` endpoint exposes knobs (`cpu_ms`, `sleep_ms`, `jitter_ms`, `err_rate`, `payload_bytes`, `id`) to shape workload.
- `/metrics` emits custom metrics (`toy_http_requests_total`, latency histograms, workload histograms, error counters, `toy_in_flight_requests`) plus Go/process defaults.
- Structured slog logging with `LOG_LEVEL` support, graceful shutdown, and strict request validation.
- Helm chart with configurable namespace, Prometheus annotation vs ServiceMonitor toggle, Grafana dashboard ConfigMap, and default probes/resources ready for ArgoCD/k3s.
- Vegeta scripts for step, spike, and seasonal traffic generation.

### Local development
```bash
go run ./cmd/toy-load
curl "http://localhost:9090/work?cpu_ms=10&sleep_ms=5"
curl http://localhost:9090/metrics
```

### Testing and tooling
```bash
make fmt
make vet
make test
```

### Container build
```bash
IMAGE=ghcr.io/vshulcz/toy-load:main make docker-build
IMAGE=ghcr.io/vshulcz/toy-load:main make docker-push
```

### CI/CD
- `.github/workflows/ci.yaml` runs on PRs and pushes to `main`.
- Jobs: gofmt/go vet/go test, Docker buildx cache, push `ghcr.io/vshulcz/toy-load:{main,<git-sha>}` on `main`.
- Tags matching `v*.*.*` additionally push `ghcr.io/vshulcz/toy-load:{latest,<tag>}`.
- Workflow logs surface Helm template/lint output to ensure chart stays deployable.

### Helm deployment
```bash
helm upgrade --install toy-load deploy/helm/toy-load \
  --namespace default --create-namespace
```
`values.yaml` allows overriding namespace, replicas, resources, probes, logging, and Prometheus Operator integration (`prometheusOperator.enabled=true` installs the ServiceMonitor; otherwise pod annotations enable scraping).

### Raw manifests
For lightweight clusters or GitOps bootstrapping, apply the base manifests:
```bash
kubectl apply -f deploy/manifests
```

### ArgoCD deployment
```bash
kubectl apply -n argocd -f deploy/argocd/toy-load.yaml
```
The Application syncs the Helm chart from `main`, enabling automated prune/self-heal with namespace auto-create.

### Toy monitoring stack (isolated Grafana/Prometheus)
Deploy a dedicated monitoring stack in `toy-monitoring` that reuses your existing Prometheus/Grafana operators (no Helm CRDs, no chart install):
```bash
kubectl apply -n argocd -f deploy/argocd/toy-monitoring.yaml
```
Access Grafana:
```bash
kubectl -n toy-monitoring port-forward svc/toy-grafana 3000:80
```
Log in at `http://127.0.0.1:3000` with user `admin` and password `admin`. Anonymous viewer is enabled for quick access. The dashboard is picked up via the `grafana_dashboard=1` label.

### Validation checklist
- Probes: `kubectl get pods` should show passing `/healthz` + `/readyz`.
- Prometheus: confirm the service is scraped via annotations or the ServiceMonitor.
- Grafana: import `dashboards/toy-load-dashboard.json` manually or rely on the ConfigMap in the Helm release (`grafana_dashboard: "1"` label for sidecars).
- PromQL snippets:
  - RPS: `sum(rate(toy_http_requests_total{path="/work"}[1m]))`
  - Error RPS: `sum(rate(toy_http_requests_total{path="/work",code=~"5.."}[1m]))`
  - p95 latency: `histogram_quantile(0.95, sum(rate(toy_http_request_duration_seconds_bucket{path="/work"}[1m])) by (le))`

### Load generation scripts
Set `SERVICE_URL` if needed (defaults to `http://toy-load.default.svc.cluster.local/work`) and run:
```bash
cd loadgen/scripts
./step.sh
./spike.sh
./seasonality.sh
```
Each script stores vegeta binaries under `loadgen/scripts/results/` (`*.bin` and `*.txt`) while printing live reports.

Typical metrics capture flow:
- Port-forward Grafana (`kubectl -n monitoring port-forward svc/grafana 3000:80`) and import the dashboard or rely on the ConfigMap rendered by Helm.
- Run one of the vegeta scripts; observe `toy_http_requests_total` rate, error rate, and latency quantiles shifting per phase.
- Persist vegeta reports from `loadgen/scripts/results` when sharing experiments.

### Observability
- ServiceMonitor/PodMonitor and annotations ensure Prometheus coverage in operator or vanilla setups.
- Grafana dashboard panels: request rate, error rate, latency quantiles, in-flight gauge, replica counts, CPU, and memory.
- Metrics include `toy_work_cpu_ms`, `toy_work_sleep_ms`, `toy_work_jitter_ms`, and `toy_errors_total{reason="..."}` to drive HPA/MPC experiments.
