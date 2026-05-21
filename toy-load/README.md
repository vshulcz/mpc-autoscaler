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

### Helm Values Reference

The chart values schema is kept at
[`deploy/helm/toy-load/values.schema.json`](deploy/helm/toy-load/values.schema.json).

| Area | Values | Defaults | Change when |
| --- | --- | --- | --- |
| Image | `image.repository`, `image.tag`, `image.pullPolicy` | `ghcr.io/vshulcz/toy-load`, `main`, `IfNotPresent` | Pin a release or commit tag, use a forked/private image, or force image refreshes during development. |
| Service | `service.type`, `service.port`, `service.targetPort` | `ClusterIP`, `80`, `http` | Expose the workload with `NodePort`/`LoadBalancer`, or map traffic through non-default service ports. |
| Resources | `resources.requests.cpu`, `resources.requests.memory`, `resources.limits.cpu`, `resources.limits.memory` | `100m`, `64Mi`, `500m`, `256Mi` | Match cluster capacity, tune pod scheduling, or adjust the CPU signal used by HPA. |
| HPA | `autoscaling.enabled`, `autoscaling.minReplicas`, `autoscaling.maxReplicas`, `autoscaling.targetCPUUtilizationPercentage`, `autoscaling.behavior` | `true`, `2`, `12`, `60`, scale up `200%/30s`, scale down `50%/60s` with `300s` stabilization | Disable the chart-managed HPA for external controllers, or tune replica bounds and scaling speed for experiments. |
| Prometheus Operator | `prometheusOperator.enabled`, `prometheusOperator.serviceMonitor.*`, `prometheusOperator.podMonitor.*` | `false`; ServiceMonitor interval `30s`, scrape timeout `10s`, release namespace; PodMonitor disabled, interval `30s`, release namespace | Install `ServiceMonitor`/`PodMonitor` resources in clusters with Prometheus Operator CRDs instead of relying on scrape annotations. |
| Dashboard | `dashboard.enabled`, `dashboard.namespace` | `false`, release namespace | Create the Grafana dashboard ConfigMap when a Grafana sidecar watches ConfigMaps labeled `grafana_dashboard=1`. |

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
