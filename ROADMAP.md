# Roadmap

This project is useful for people interested in Kubernetes autoscaling, predictive control, reproducible experiments, and small research systems that can still be run locally.

## Near-Term Directions

- Expand the benchmark matrix from indexed evidence roots into published numeric cells where summaries can be rebuilt.
- Add more offline policy comparators beside HPA and the current MPC variants.
- Add a minimal local demo that exercises the service, metrics, and offline analysis without a cluster.
- Improve dashboard panels for controller decisions, replica lag, and saturation signals.
- Add stricter static checks for Python once the dependency footprint is stable.

## Practitioner Roadmap

| Milestone | Outcome | Why it matters |
| --- | --- | --- |
| `v0.2.0` | Stable public interface docs for workload endpoints, metrics, trace CSVs, CLIs, and evidence aliases. | Readers can script against documented surfaces instead of reverse-engineering internals. |
| `thesis-reproducibility` | Benchmark matrix with rebuilt HPA, Hybrid-SA, and comparator cells where archives are available. | Result discussion moves beyond one representative spike pair without overclaiming. |
| `v0.3.0` | Cluster-neutral quick demo and failure-mode checks for missing metrics, solver fallback, and dry-run recommendations. | Practitioners can evaluate safety boundaries before trying live apply mode. |

## Good First Contributions

- Add a small synthetic traffic trace and a matching offline simulation example.
- Improve `toy-load/README.md` examples for one Kubernetes distribution.
- Add dashboard screenshots or panel documentation.
- Add tests around an uncovered artifact parser edge case.
- Improve error messages in load-generation scripts without changing experiment semantics.

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
