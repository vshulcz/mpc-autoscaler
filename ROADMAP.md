# Roadmap

This project is useful for people interested in Kubernetes autoscaling, predictive control, reproducible experiments, and small research systems that can still be run locally.

## Near-Term Directions

- Keep the public entrypoint focused on the 60-second MPC-vs-HPA walkthrough instead of scattered docs links.
- Expand the benchmark matrix from indexed evidence roots into published numeric cells where summaries can be rebuilt.
- Add more offline policy comparators beside HPA and the current MPC variants.
- Add a minimal local demo that exercises the service, metrics, and offline analysis without a cluster.
- Improve dashboard panels for controller decisions, replica lag, and saturation signals.
- Add stricter static checks for Python once the dependency footprint is stable.

## Feedback Requests

The project needs methodology criticism more than generic docs cleanup. High-leverage feedback includes:

- HPA baseline settings that would make the comparison more credible.
- Production-like trace shapes that can be reduced to small public CSV examples.
- Failure cases for missing metrics, solver fallback, cold starts, noisy forecasts, and rate limits.
- Comparator proposals with enough detail to implement or simulate.
- Evidence-table or dashboard changes tied to exact paths, metrics, or commands.

## Micro Contribution Lane

Micro PRs are useful when they are narrow and verified. Good candidates are one-command fixes, one-link repairs, one dashboard metric note, one toy-load example, or one setup note tied to an observed command. See [`docs/MICRO_CONTRIBUTIONS.md`](docs/MICRO_CONTRIBUTIONS.md).

## Practitioner Roadmap

| Milestone | Outcome | Why it matters |
| --- | --- | --- |
| `v0.2.0` | Stable public interface docs for workload endpoints, metrics, trace CSVs, CLIs, and evidence aliases. | Readers can script against documented surfaces instead of reverse-engineering internals. |
| `thesis-reproducibility` | Benchmark matrix with rebuilt HPA, Hybrid-SA, and comparator cells where archives are available. | Result discussion moves beyond one representative spike pair without overclaiming. |
| `v0.3.0` | Cluster-neutral quick demo and failure-mode checks for missing metrics, solver fallback, and dry-run recommendations. | Practitioners can evaluate safety boundaries before trying live apply mode. |

## Good First Contributions

- Run the bundled spike trace validation path and report unclear setup assumptions.
- Pick one microtask from `docs/MICRO_CONTRIBUTIONS.md` and verify it with `git diff --check`.
- Add a small synthetic traffic trace and a matching offline simulation example.
- Improve one `toy-load/README.md` example after testing it on a named Kubernetes distribution.
- Add one dashboard panel note that maps the panel to an exact Prometheus metric.
- Add tests around an uncovered artifact parser edge case.
- Improve one load-generation script error message without changing experiment semantics.

## Research Directions

- Compare against KEDA, predictive HPA variants, and queue-aware reactive policies.
- Explore multi-service autoscaling where one controller coordinates multiple Deployments.
- Add model-identification tools for estimating per-replica capacity from saved runs.
- Study safety constraints for cold starts, rate limits, and noisy demand forecasts.
- Package a repeatable benchmark harness for public cluster-neutral comparison.

## Non-Goals

- This is not a production-ready autoscaler distribution.
- This is not a replacement for Kubernetes HPA or KEDA.
- This repository prioritizes clear experiments and reproducible evidence over broad platform support.
