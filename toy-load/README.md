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

| Env Var | Default | Meaning |
| --- | --- | --- |
| `PORT` | `9090` | HTTP listen port. |
| `METRICS_PATH` | `/metrics` | Prometheus metrics path. Must start with `/` and not overlap built-in endpoints. |
| `READ_TIMEOUT` | `5s` | HTTP read timeout. Must be positive. |
| `WRITE_TIMEOUT` | `20s` | HTTP write timeout. Must be positive. |
| `IDLE_TIMEOUT` | `60s` | HTTP idle timeout. Must be positive. |
| `MAX_HEADER_BYTES` | `1048576` | Max HTTP request header size. |
| `LOG_LEVEL` | `info` | `debug`, `info`, `warn`, `warning`, or `error`. |
| `APP_NAME` | `toy-load` | Name attached to structured logs. |

## Metrics

| Metric | Labels | Meaning |
| --- | --- | --- |
| `toy_http_requests_total` | `method`, `path`, `code` | Request count. |
| `toy_http_request_duration_seconds` | `method`, `path` | Request latency histogram. |
| `toy_in_flight_requests` | none | Current in-flight request count. |
| `toy_work_cpu_ms` | none | Requested CPU work. |
| `toy_work_sleep_ms` | none | Requested fixed sleep. |
| `toy_work_jitter_ms` | none | Requested jitter bound. |
| `toy_errors_total` | `path`, `reason` | Application error counters. |

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
capabilities, probes, resource requests, HPA, and Prometheus scrape annotations.
Prometheus Operator resources and Grafana dashboard ConfigMap are disabled by
default because they require cluster-specific CRDs/controllers.

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
