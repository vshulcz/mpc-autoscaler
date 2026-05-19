# Dashboards

Standalone Grafana dashboard JSON for manual import.

- `toy-load-dashboard.json` uses only metrics scraped from `toy-load` and Prometheus target labels.
- The deployed copy lives under `deploy/monitoring/dashboards/` so ArgoCD/Kustomize can load it without referencing files outside the application path.
