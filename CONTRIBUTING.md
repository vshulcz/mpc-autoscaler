# Contributing

This repository combines three kinds of work:

- `toy-load/`: Go service, Helm chart, and container packaging.
- `analysis/`: offline and online MPC tooling.
- `deploy/`, `dashboards/`, and `loadgen/`: experiment infrastructure and repeatable runners.

Small, focused pull requests are easier to review than broad mixed changes. The project has two useful contribution lanes: research feedback for baselines, traces, and failure cases; and micro PRs for small verified docs, examples, links, and metric explanations. Broad wording-only rewrites are lower priority, but narrow fixes are welcome when they are checked against real files or commands.

## Best First Feedback

If you are new to the project, the best contribution is usually not a pull request. Start with one reproducible check:

```bash
python3 -m pip install -e analysis
mpc-validate-trace --trace-csv analysis/mpc_autoscaler_analysis/data/traces/baseline_spike_profile_dt15.csv
mpc-offline-sim \
  --trace-csv analysis/mpc_autoscaler_analysis/data/traces/baseline_spike_profile_dt15.csv \
  --out-dir analysis/out/offline/spike
```

Then open a reproduction feedback issue or Q&A comment with:

- the command you ran;
- the output path or error;
- one concrete thing that would make the result easier to trust, reproduce, or compare.

## Micro PRs

Micro pull requests are welcome when they stay small and verifiable. Good micro PRs fix one command, one link, one metric explanation, one setup note, or one example that can be checked quickly.

Fast path:

1. Pick one issue labeled [`good first issue`](https://github.com/vshulcz/mpc-autoscaler/labels/good%20first%20issue) or open the micro contribution form.
2. Touch one topic, preferably one file.
3. Verify one concrete thing: a command, link target, metric name, file path, or rendered docs page.
4. Open the PR with the issue number and the exact verification you ran.

Start here:

- Micro contribution guide: [`docs/MICRO_CONTRIBUTIONS.md`](docs/MICRO_CONTRIBUTIONS.md)
- Micro contribution issue form: <https://github.com/vshulcz/mpc-autoscaler/issues/new?template=micro_contribution.yml>

Before opening a micro PR, make sure it:

- touches one topic only;
- cites exact file paths, commands, metrics, or issue numbers;
- avoids invented benchmark claims, result paths, releases, and contributors;
- keeps generated experiment artifacts out of Git;
- runs `git diff --check`.

## Good First Issues

External contributions are welcome. The fastest path is to pick an issue labeled `good first issue` or `help wanted` from the public roadmap board:

- Roadmap board: <https://github.com/users/vshulcz/projects/2>
- Starter issues: <https://github.com/vshulcz/mpc-autoscaler/labels/good%20first%20issue>
- Broader contributor queue: <https://github.com/vshulcz/mpc-autoscaler/labels/help%20wanted>

Good starter pull requests usually touch one of these areas:

- one runnable command or example that was unclear;
- one link or cross-reference verified against a committed file;
- one benchmark table cell backed by a committed summary or exact evidence alias;
- one Grafana/dashboard explanation tied to a Prometheus metric;
- one lightweight parser or CLI-help test;
- one reproduction checklist improvement tied to a command you ran.

Before starting, comment on the issue if you want to avoid duplicated work. Draft PRs are fine for small docs-only fixes when the scope and verification are clear.

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

## Pull Request Title Examples

Use a short conventional title that names the affected area:

- `docs: add loadgen output directory reference`
- `test: cover trace validator missing timestamp`
- `release: document GHCR image digest verification`
- `dashboard: map HPA panels to Prometheus metrics`

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
