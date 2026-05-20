# Contributing

This repository combines three kinds of work:

- `toy-load/`: Go service, Helm chart, and container packaging.
- `analysis/`: offline and online MPC tooling.
- `deploy/`, `dashboards/`, and `loadgen/`: experiment infrastructure and repeatable runners.

Small, focused pull requests are easier to review than broad mixed changes.

## Good First Issues

External contributions are welcome. The fastest path is to pick an issue labeled `good first issue` or `help wanted` from the public roadmap board:

- Roadmap board: <https://github.com/users/vshulcz/projects/2>
- Starter issues: <https://github.com/vshulcz/mpc-autoscaler/labels/good%20first%20issue>
- Broader contributor queue: <https://github.com/vshulcz/mpc-autoscaler/labels/help%20wanted>

Good starter pull requests usually touch one of these areas:

- documentation tables and examples;
- Pages site copy or experiment-gallery links;
- small Grafana dashboard improvements;
- lightweight tests around parsers and CLI help;
- release verification and reproducibility checklist improvements.

Before starting, comment on the issue with your intended approach. This avoids duplicated work and makes review faster.

## Before Opening A Pull Request

1. Make sure the change has a clear scope.
2. Keep generated artifacts and local experiment outputs out of Git unless they are intentionally curated evidence files.
3. Update documentation when commands, paths, or operational behavior change.

## Local Checks

Run the standard repository checks before opening a pull request:

```bash
make check
```

If you touch release-facing or packaging paths, also run:

```bash
make coverage
helm template toy-load toy-load/deploy/helm/toy-load \
  --namespace default \
  --set prometheusOperator.enabled=true \
  --set dashboard.enabled=true >/dev/null
kubectl kustomize deploy/monitoring >/dev/null
```

## Pull Request Expectations

- explain what changed and why;
- link the issue you are addressing, for example `Fixes #14`;
- mention affected areas (`toy-load`, `analysis`, `loadgen`, `deploy`);
- note any experiment methodology impact;
- call out follow-up work or known limitations.

## Repository Conventions

- keep shell runners under `loadgen/scripts/` executable and syntax-clean;
- keep experiment evidence lightweight in Git and store bulky outputs outside the repository;
- prefer semver tags (`vX.Y.Z`) for releases;
- avoid mixing code cleanups with experiment result updates in the same pull request unless they are directly tied.

## Releases

Release automation is documented in `docs/RELEASE.md`.
