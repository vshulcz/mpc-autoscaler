# Monitoring Manifests

Kustomize manifests for the Prometheus and Grafana stack used by the thesis experiments.

## Prerequisites

- Prometheus Operator CRDs installed (`monitoring.coreos.com/v1`).
- Grafana Operator CRDs installed (`grafana.integreatly.org/v1beta1`).
- `toy-load` deployed in the `default` namespace with its Helm chart defaults.

## Apply

```bash
kubectl apply -k deploy/monitoring
```

The stack creates a `toy-monitoring` namespace, one Prometheus instance, one Grafana instance, and a dashboard loaded from `deploy/monitoring/dashboards/toy-load-dashboard.json`.

The `ServiceMonitor` uses a 30-second scrape interval to match the final thesis experiment setup.

Grafana is configured for anonymous Viewer access and is exposed only as a `ClusterIP` service. Use `kubectl port-forward` for local access.
