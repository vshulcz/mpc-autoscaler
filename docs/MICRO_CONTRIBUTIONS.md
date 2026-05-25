# Micro Contributions

This lane is for small, reviewable pull requests, including AI-assisted work. The goal is to turn small contributor effort into verified improvements without accepting vague, fabricated, or risky changes.

## Good Micro PRs

Good micro PRs change one small thing and prove it with a quick check.

| Type | Example | Required check |
| --- | --- | --- |
| Command clarity | Fix one documented command that is missing a flag or path. | Paste the command you checked, or run `git diff --check`. |
| Link repair | Replace one broken or stale docs link with an existing target. | Verify the target exists in the repository or is a stable absolute URL. |
| Metric explanation | Add one sentence mapping a dashboard panel to a Prometheus metric. | Link the exact dashboard or metric name. |
| Trace example | Add one small trace usage example using committed files. | Use `mpc-validate-trace --trace-csv <path>`. |
| Error-message note | Document one common setup error and the shortest fix. | Mention the command or environment where the error appears. |

## AI-Assisted PR Rules

AI-generated drafts are welcome when the contributor verifies them. A pull request is easier to merge when it follows these rules:

- touch one topic only;
- cite exact file paths, commands, metrics, or issue numbers;
- do not invent benchmark claims, results, paths, releases, or contributors;
- do not add generated experiment outputs or raw artifacts;
- run `git diff --check` before opening the PR;
- say what was AI-assisted and what was manually verified.

## Avoid These

These PRs are unlikely to be accepted:

- broad README rewrites without a concrete bug or unclear command;
- generic “improve grammar” sweeps across many files;
- new result claims not tied to `docs/RESULTS.md`, `docs/BENCHMARK_MATRIX.md`, or exact evidence aliases;
- links to files that are not committed;
- changes to workflows, release automation, security policy, or generated artifacts without prior discussion.

## Best First Microtasks

Start with one of these if you want a quick, useful contribution:

- improve one setup sentence after running a documented command;
- add one missing cross-link between `README.md`, `docs/`, `site/`, and `experiments/`;
- add one dashboard metric note tied to a Prometheus query;
- add one CLI example using a real flag from `analysis/pyproject.toml`;
- add one toy-load HTTP example using an endpoint from `toy-load/README.md`.

If unsure, open a micro contribution issue first and describe the exact file you want to touch.

## Example PR Path

1. Pick one issue labeled `good first issue`.
2. Change one file or one tightly related docs section.
3. Verify one concrete target: command, link, metric, path, or rendered page.
4. Open the PR with the issue number and the verification result.
