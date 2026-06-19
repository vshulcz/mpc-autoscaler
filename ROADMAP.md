# Roadmap

Where this repo is going. See [`docs/RESULTS.md`](docs/RESULTS.md) for the current evidence baseline and [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for what the numbers do not prove.

## Near-term

- Keep the public entrypoint focused on the 60-second MPC-vs-HPA walkthrough.
- Promote indexed evidence roots into published numeric cells where summaries can be rebuilt.
- Add more offline policy comparators beside HPA and the current MPC variants.
- Ship a local demo that exercises service, metrics, and offline analysis without a cluster.
- Improve dashboard panels for controller decisions, replica lag, and saturation signals.
- Tighten Python static checks (`mypy`, `ruff`) once the dependency footprint is stable.

## Milestones

| Milestone | Outcome |
| --- | --- |
| `v0.2.0` | Stable public interface docs for workload endpoints, metrics, trace CSVs, CLIs, and evidence aliases. |
| `thesis-reproducibility` | Benchmark matrix with rebuilt HPA, Hybrid-SA, and comparator cells where archives are available. |
| `v0.3.0` | Cluster-neutral quick demo plus failure-mode checks for missing metrics, solver fallback, and dry-run recommendations. |

## Research directions

- Compare against KEDA, predictive HPA variants, and queue-aware reactive policies.
- Multi-service autoscaling: one controller coordinating multiple Deployments.
- Model-identification tools for estimating per-replica capacity from saved runs.
- Safety constraints for cold starts, rate limits, and noisy demand forecasts.
- Repeatable cluster-neutral benchmark harness.

## Feedback that moves the needle

Methodology criticism is worth more than docs cleanup. High-leverage feedback:

- HPA baseline settings that would make the comparison more credible.
- Production-like trace shapes reducible to small public CSV examples.
- Failure cases for missing metrics, solver fallback, cold starts, noisy forecasts, rate limits.
- Comparator proposals with enough detail to implement or simulate.
- Evidence-table or dashboard changes tied to exact paths, metrics, or commands.

## Good first contributions

- Run the bundled spike-trace validation path and report unclear setup assumptions.
- Pick one task from [`docs/MICRO_CONTRIBUTIONS.md`](docs/MICRO_CONTRIBUTIONS.md); verify with `git diff --check`.
- Add a small synthetic traffic trace and a matching offline simulation example.
- Improve a `toy-load/README.md` example after testing on a named Kubernetes distribution.
- Add a dashboard panel note that maps the panel to an exact Prometheus metric.
- Add tests around an uncovered artifact-parser edge case.
- Improve one load-generation script error message without changing experiment semantics.

## Non-goals

- Not a production autoscaler distribution.
- Not a replacement for the HPA or KEDA.
- Prioritises clear experiments and reproducible evidence over broad platform support.
