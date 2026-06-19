# toy-load

`toy-load` is a small HTTP service for autoscaling experiments. Each request can
ask the service to burn CPU, sleep, add random latency jitter, return a payload,
or intentionally fail. The service exposes Prometheus metrics used by the thesis
experiments and by the MPC/HPA comparison tooling.

## Run Locally

Run commands from this `toy-load/` directory.

```bash
go run ./cmd/toy-load
curl "http://localhost:9090/work?cpu_ms=10&sleep_ms=20&jitter_ms=5"
curl http://localhost:9090/metrics
```

Build binary:

```bash
make build
./bin/toy-load
```

Build container:

```bash
docker build -t toy-load:local .
docker run --rm -p 9090:9090 toy-load:local
```

## HTTP API

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | `GET` | Service metadata and endpoint links. |
| `/healthz` | `GET` | Liveness probe. Returns `ok`. |
| `/readyz` | `GET` | Readiness probe. Returns `ok` after server start. |
| `/work` | `GET` | Execute controllable synthetic work. |
| `/metrics` | `GET` | Prometheus metrics. Path is configurable. |

Unknown paths return `404`. Unsupported methods return `405` with `Allow: GET`.

## Work Parameters

`GET /work` accepts query parameters:

| Parameter | Default | Bounds | Meaning |
| --- | ---: | ---: | --- |
| `cpu_ms` | `0` | `0..5000` | Approximate CPU busy-loop time in milliseconds. |
| `sleep_ms` | `0` | `0..5000` | Fixed sleep time in milliseconds. |
| `jitter_ms` | `0` | `0..5000` | Random extra sleep in `[0, jitter_ms)`. |
| `payload_bytes` | `0` | `0..1048576` | Plain-text response payload size. |
| `err_rate` | `0` | `0..1` | Probability of returning HTTP `500`. |
| `id` | empty | string | Request identifier copied to debug logs. |

Integer values outside bounds are clamped. Invalid integer or float formats
return `400`.

## Curl Examples

Start `toy-load` first:

```bash
go run ./cmd/toy-load
```

Check liveness and metrics endpoints:

```bash
curl -i http://localhost:9090/healthz
curl -i http://localhost:9090/metrics
```

`/healthz` returns HTTP `200` with body `ok`. `/metrics` returns HTTP `200`
with Prometheus text output.

Run common `/work` scenarios:

```bash
curl -i "http://localhost:9090/work?id=baseline"
curl -i "http://localhost:9090/work?cpu_ms=250&id=cpu-heavy"
curl -i "http://localhost:9090/work?sleep_ms=50&jitter_ms=100&id=jitter"
curl -i "http://localhost:9090/work?err_rate=1&id=forced-error"
```

The baseline, CPU-heavy, and jitter requests return HTTP `200` with a
plain-text response shaped like `work: cpu_ms=250 sleep_ms=0 jitter_ms=0`.
The forced error-rate request returns HTTP `500` with body `error`.

Generate a small burst for autoscaling and metrics checks:

```bash
for i in $(seq 1 10); do
  curl -s "http://localhost:9090/work?cpu_ms=100&sleep_ms=25&id=burst-${i}" >/dev/null
done

curl -s http://localhost:9090/metrics | grep '^toy_http_requests_total'
```

## Configuration

Configuration is environment-based.

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `9090` |
| `METRICS_PATH` | Prometheus metrics path. Must start with `/` and not overlap built-in endpoints. | `/metrics` |
| `READ_TIMEOUT` | HTTP read timeout. Must be a positive Go duration. | `5s` |
| `READ_HEADER_TIMEOUT` | HTTP header read timeout. Protects against slow-header clients. | `5s` |
| `WRITE_TIMEOUT` | HTTP write timeout. Must be a positive Go duration. | `20s` |
| `IDLE_TIMEOUT` | HTTP idle timeout. Must be a positive Go duration. | `60s` |
| `SHUTDOWN_TIMEOUT` | Graceful shutdown deadline. Must exceed the worst-case `/work` duration so in-flight requests can finish. | `25s` |
| `MAX_HEADER_BYTES` | Maximum HTTP request header size in bytes. | `1048576` |
| `MAX_QUERY_ID_BYTES` | Maximum length of the optional `?id=` query parameter. Clamped silently to cap log size. | `256` |
| `LOG_LEVEL` | Log level: `debug`, `info`, `warn`, `warning`, or `error`. | `info` |
| `APP_NAME` | Name attached to structured logs. | `toy-load` |

> Set Kubernetes `terminationGracePeriodSeconds` to at least `SHUTDOWN_TIMEOUT + 5s` so the pod is not killed before graceful shutdown completes.

## Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `toy_http_requests_total` | `method`, `path`, `code` | Request count, every route. |
| `toy_http_request_duration_seconds` | `method`, `path` | Request latency histogram, buckets reach 30s. |
| `toy_in_flight_requests` | none | Current in-flight `/work` request count. |
| `toy_work_cpu_seconds` | none | Requested CPU work, in seconds (Prometheus base unit). |
| `toy_work_sleep_seconds` | none | Requested fixed sleep, in seconds. |
| `toy_work_jitter_seconds` | none | Requested jitter bound, in seconds. |
| `toy_errors_total` | `path`, `reason` | Application error counters. |
| `toy_panics_total` | `path` | Recovered handler panics. |

Useful PromQL:

```promql
sum(rate(toy_http_requests_total{path="/work"}[1m]))
histogram_quantile(0.95, sum(rate(toy_http_request_duration_seconds_bucket{path="/work"}[1m])) by (le))
toy_in_flight_requests
```

## Kubernetes

Deploy with Helm:

```bash
helm upgrade --install toy-load deploy/helm/toy-load \
  --namespace default \
  --create-namespace
```

The chart configures non-root execution, read-only root filesystem, dropped Linux
capabilities, no service-account token mount, a 30 s termination grace period,
a PodDisruptionBudget keeping `minAvailable=1`, probes, resource requests, HPA,
and Prometheus scrape annotations. NetworkPolicy and Prometheus Operator
resources, plus the Grafana dashboard ConfigMap, are off by default because they
require cluster-specific CRDs/controllers or a known scrape source.

### Helm Values Reference

The chart values schema is kept at
[`deploy/helm/toy-load/values.schema.json`](deploy/helm/toy-load/values.schema.json).

| Area | Values | Defaults | Change when |
| --- | --- | --- | --- |
| Image | `image.repository`, `image.tag`, `image.digest`, `image.pullPolicy` | `ghcr.io/vshulcz/toy-load`, `main`, `""`, `IfNotPresent` | Pin a release tag, pin by `sha256:` digest for reproducibility, use a forked/private image, or force image refreshes during development. |
| Service | `service.type`, `service.port`, `service.targetPort` | `ClusterIP`, `80`, `http` | Expose the workload with `NodePort`/`LoadBalancer`, or map traffic through non-default service ports. |
| Resources | `resources.requests.cpu`, `resources.requests.memory`, `resources.limits.cpu`, `resources.limits.memory` | `100m`, `64Mi`, `500m`, `256Mi` | Match cluster capacity, tune pod scheduling, or adjust the CPU signal used by HPA. |
| HPA | `autoscaling.enabled`, `autoscaling.minReplicas`, `autoscaling.maxReplicas`, `autoscaling.targetCPUUtilizationPercentage`, `autoscaling.behavior` | `true`, `2`, `12`, `60`, scale up `200%/30s`, scale down `50%/60s` with `300s` stabilization | Disable the chart-managed HPA for external controllers, or tune replica bounds and scaling speed for experiments. |
| Pod hardening | `automountServiceAccountToken`, `terminationGracePeriodSeconds`, `topologySpreadConstraints` | `false`, `30`, `[]` | The workload never calls the Kubernetes API, so the token mount stays off. Raise grace period if you increase `SHUTDOWN_TIMEOUT`. Add spread constraints to distribute replicas across zones/nodes. |
| Disruption | `podDisruptionBudget.enabled`, `podDisruptionBudget.minAvailable`, `podDisruptionBudget.maxUnavailable` | `true`, `1`, unset | Keep at least one replica alive during voluntary disruption (node drains, rolling updates). |
| Network policy | `networkPolicy.enabled`, `networkPolicy.ingress.from` | `false`, `[]` | Enable to restrict ingress to the HTTP port; populate `from` with namespace/pod selectors of your scrape source. |
| Prometheus Operator | `prometheusOperator.enabled`, `prometheusOperator.serviceMonitor.*`, `prometheusOperator.podMonitor.*` | `false`; ServiceMonitor interval `30s`, scrape timeout `10s`, release namespace; PodMonitor disabled, interval `30s`, release namespace | Install `ServiceMonitor`/`PodMonitor` resources in clusters with Prometheus Operator CRDs instead of relying on scrape annotations. |
| Dashboard | `dashboard.enabled`, `dashboard.namespace` | `false`, release namespace | Create the Grafana dashboard ConfigMap when a Grafana sidecar watches ConfigMaps labeled `grafana_dashboard=1`. |

Override resource requests for a single experiment with `--set`:

```bash
helm upgrade --install toy-load deploy/helm/toy-load \
  --namespace default \
  --create-namespace \
  --set resources.requests.cpu=250m \
  --set resources.requests.memory=128Mi
```

The HPA CPU target is calculated against the requested CPU. Raising
`resources.requests.cpu` can lower reported utilization for the same load and
delay scale-up; lowering it can make the HPA more sensitive.

Enable Prometheus Operator integration when `ServiceMonitor` CRD is installed:

```bash
helm upgrade --install toy-load deploy/helm/toy-load \
  --namespace default \
  --create-namespace \
  --set prometheusOperator.enabled=true
```

Enable dashboard ConfigMap only when Grafana sidecar watches dashboard ConfigMaps:

```bash
helm upgrade --install toy-load deploy/helm/toy-load \
  --namespace default \
  --create-namespace \
  --set dashboard.enabled=true
```

Raw manifests are available for plain Kubernetes clusters:

```bash
kubectl apply -f deploy/manifests
```

## Experiment Role

In the thesis experiments, `toy-load` is the controlled workload under HPA and
MPC policies. Load-generator scripts drive `/work`, Prometheus records service
metrics, and analysis tooling summarizes latency, success ratio, in-flight
requests, and replica behavior.

## Status Code Reference

This section records the status codes users should expect while testing `/work`.

| Scenario | Example | Expected status | Notes |
| --- | --- | --- | --- |
| Success | `curl -i "http://localhost:9090/work?id=baseline"` | `200` | Normal `/work` requests return a plain-text response. |
| Invalid query values | `curl -i "http://localhost:9090/work?cpu_ms=abc"` | `400` | Invalid integer or float formats are rejected. |
| Unknown path | `curl -i http://localhost:9090/does-not-exist` | `404` | Unrecognized paths return not found. |
| Invalid method | `curl -i -X POST http://localhost:9090/work` | `405` | Only `GET` is supported; response includes `Allow: GET`. |
| Forced error | `curl -i "http://localhost:9090/work?err_rate=1&id=forced-error"` | `500` | `err_rate=1` forces an application error response. |

These examples match the curl style used above: they target `localhost:9090` and
use `-i` when showing the HTTP status line and headers.
