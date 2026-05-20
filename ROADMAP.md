# Roadmap

This project is useful for people interested in Kubernetes autoscaling, predictive control, reproducible experiments, and small research systems that can still be run locally.

## Near-Term Directions

- Publish compact result figures and a short experiment narrative in repository docs.
- Add more offline policy comparators beside HPA and the current MPC variants.
- Add a minimal local demo that exercises the service, metrics, and offline analysis without a cluster.
- Improve dashboard panels for controller decisions, replica lag, and saturation signals.
- Add stricter static checks for Python once the dependency footprint is stable.

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
