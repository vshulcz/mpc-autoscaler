# Release Process

Releases are semver-tag driven and attach reproducible build outputs to GitHub Releases.

## Manual Tag Flow

1. Open the `Tag Release` workflow in GitHub Actions.
2. Enter a tag like `v0.1.0`.
3. The workflow creates and pushes an annotated tag from the selected branch.
4. The workflow dispatches `Release` for that tag.

## Release Outputs

The `Release` workflow publishes:

- `toy-load-<tag>-linux-amd64.tar.gz`
- `toy-load-<tag>-linux-arm64.tar.gz`
- `toy-load-<tag>-darwin-amd64.tar.gz`
- `toy-load-<tag>-darwin-arm64.tar.gz`
- `toy-load-<chart-version>.tgz`
- `SHA256SUMS`

The `Release` workflow publishes the matching container image tags to GHCR:

- `ghcr.io/vshulcz/toy-load:<tag>`
- `ghcr.io/vshulcz/toy-load:latest`
- `ghcr.io/vshulcz/toy-load:sha-<short-sha>`

## Local Preflight

Run before creating a release tag:

```bash
make check
make coverage
helm template toy-load toy-load/deploy/helm/toy-load \
  --namespace default \
  --set prometheusOperator.enabled=true \
  --set dashboard.enabled=true >/dev/null
kubectl kustomize deploy/monitoring >/dev/null
```

Keep raw experiment outputs ignored under `experiments/`; export thesis evidence with `experiments/package-thesis-evidence.sh` when an external archive is needed.
