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

## Verify Release Assets

Download `SHA256SUMS` with the binary or Helm chart you plan to use, then
verify the selected files before unpacking them.

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

After the release finishes, download `SHA256SUMS` and verify at least one Linux
binary, one macOS binary, and the Helm chart package with the commands above.

Keep raw experiment outputs ignored under `experiments/`; export thesis evidence with `experiments/package-thesis-evidence.sh` when an external archive is needed.
