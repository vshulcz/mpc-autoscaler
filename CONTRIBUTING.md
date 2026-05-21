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

## Questions Before Code

Use the [Q&A entry thread](https://github.com/vshulcz/mpc-autoscaler/discussions/77) for setup, reproducibility, Docker, Helm, and analysis questions. This keeps how-to answers searchable instead of burying them in pull request comments.

When an answer solves your question, mark it as accepted. That turns the thread into reusable project documentation for the next contributor.

## Before Opening A Pull Request

1. Make sure the change has a clear scope.
2. Keep generated artifacts and local experiment outputs out of Git unless they are intentionally curated evidence files.
3. Update documentation when commands, paths, or operational behavior change.

## CODEOWNERS Review Routing

The repository uses [`.github/CODEOWNERS`](.github/CODEOWNERS) to route reviews to the maintainer for sensitive changes. Expect extra care for workflow, release, security, and supply-chain paths because those files can affect published artifacts, automation credentials, or contributor trust.

## Automatic PR Labels

When you open a pull request, [`.github/labeler.yml`](.github/labeler.yml) automatically adds labels based on the files you changed:

| Label | Triggered by |
| --- | --- |
| `documentation` | changes to README, docs, site |
| `docs-site` | changes to site/ or Pages workflow |
| `python` | changes to analysis/ |
| `go` | changes to toy-load Go code |
| `helm` | changes to the Helm chart |
| `observability` | changes to dashboards or monitoring |
| `experiment-automation` | changes to loadgen or experiments |
| `release` | changes to release workflows or RELEASE.md |
| `github-actions` | changes to workflows or labeler config |

These labels help reviewers understand the scope of your change at a glance. If the labeler does not assign a label, your change may span multiple areas or touch paths not yet covered by the configuration.

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

## Docs-Only Pull Requests

For changes limited to documentation (no code, workflow, or configuration changes), use this condensed checklist:

- [ ] changes are limited to `docs/`, `README.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `SECURITY.md`, or `site/`;
- [ ] links are valid (existing anchors, absolute URLs, or relative paths);
- [ ] no generated artifacts, experiments, or credentials are included.

This keeps docs-only PRs lightweight and fast to review.

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
