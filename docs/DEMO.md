# Ten-Second Demo

This demo is the fast reader path: show why the repository exists without making a production claim.

For a slightly longer technical walkthrough, start with [`docs/MPC_VS_HPA_60_SECONDS.md`](MPC_VS_HPA_60_SECONDS.md).

![Ten-second autoscaling loop](../site/assets/figures/ten-second-demo.gif)

## Storyboard

| Time | Message | Repository backing |
| ---: | --- | --- |
| 0-2s | Synthetic traffic creates a controlled spike. | `loadgen/`, `analysis/mpc_autoscaler_analysis/data/traces/` |
| 2-4s | `toy-load` exposes request and latency metrics. | `toy-load/README.md#metrics` |
| 4-6s | HPA reacts to measured pressure; MPC forecasts short-horizon demand. | `docs/ARCHITECTURE.md`, `analysis/` |
| 6-8s | Compare p95, p99, success, and replica behavior. | `docs/BENCHMARK_MATRIX.md`, `docs/RESULTS.md` |
| 8-10s | Publish exact paths, caveats, and rebuild commands. | `docs/METHODOLOGY.md`, `docs/LIMITATIONS.md`, `experiments/MANIFEST.md` |

## Safe Caption

`mpc-autoscaler` is a reproducible Kubernetes autoscaling lab: one controllable workload, HPA baseline, MPC controller, offline simulator, and evidence policy. Current public numbers cover one tracked spike pair, so the useful claim is methodology and reproducibility, not production superiority.

## Post Hook

I built a small research repo for Kubernetes autoscaling experiments: HPA baseline versus an MPC controller on controlled traffic profiles. It includes a Go workload, Helm chart, Prometheus metrics, offline simulator, benchmark matrix, release automation, and explicit limitations.
