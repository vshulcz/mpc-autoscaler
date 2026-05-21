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

Example:

```bash
curl "http://localhost:9090/work?cpu_ms=25&sleep_ms=10&jitter_ms=5&payload_bytes=128&err_rate=0.01&id=demo"
```

## Configuration

Configuration is environment-based.

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `9090` |
| `METRICS_PATH` | Prometheus metrics path. Must start with `/` and not overlap built-in endpoints. | `/metrics` |
| `READ_TIMEOUT` | HTTP read timeout. Must be a positive Go duration. | `5s` |
| `WRITE_TIMEOUT` | HTTP write timeout. Must be a positive Go duration. | `20s` |
| `IDLE_TIMEOUT` | HTTP idle timeout. Must be a positive Go duration. | `60s` |
| `MAX_HEADER_BYTES` | Maximum HTTP request header size in bytes. | `1048576` |
| `LOG_LEVEL` | Log level: `debug`, `info`, `warn`, `warning`, or `error`. | `info` |
| `APP_NAME` | Name attached to structured logs. | `toy-load` |

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
