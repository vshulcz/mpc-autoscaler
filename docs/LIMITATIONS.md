# Limitations

This page lists known boundaries so the repository can be shared without overstating the work.

## Not Production Software

`mpc-autoscaler` is research software. It is not a drop-in replacement for Kubernetes HPA, KEDA, VPA, or production autoscaling platforms.

Production use would need more work around failure modes, RBAC, rollout safety, noisy metrics, multi-workload interactions, SLOs, alerting, and operational ownership.

## Synthetic Workload

The main workload is `toy-load`, a controllable HTTP service. This makes experiments repeatable, but it does not represent all real applications.

Missing production factors include:

- database and cache dependencies;
- queueing systems;
- cold starts and image pulls across heterogeneous nodes;
- multi-service backpressure;
- real user traffic patterns;
- application-level SLO constraints.

## Limited Public Result Scope

`docs/RESULTS.md` currently exposes a representative spike comparison, not a full aggregate benchmark suite. `docs/BENCHMARK_MATRIX.md` makes this explicit by separating indexed evidence coverage from published numeric cells.

The current snapshot is useful for explaining the workflow and inviting review. It should not be read as a general claim that MPC outperforms HPA.

## Baseline Sensitivity

HPA behavior depends on target utilization, stabilization windows, metric freshness, pod readiness, cluster capacity, and workload shape. A poorly tuned HPA baseline can make any alternative look better than it is.

Comparisons should keep HPA settings visible and include multiple targets or sensitivity checks where possible.

## MPC Assumptions

The MPC controller relies on short-horizon demand estimates, calibrated throughput capacity per replica, and optimization settings. If those assumptions drift, the controller can under-scale, over-scale, or oscillate.

Important caveats:

- forecasts are simplified;
- model parameters are workload-specific;
- solver status must be inspected;
- safety fallbacks matter as much as the nominal MPC solution;
- dry-run recommendations are safer than apply mode while tuning.

## Cluster Dependence

Live results depend on Kubernetes version, node capacity, scheduler behavior, metrics-server or Prometheus setup, network conditions, and competing workloads.

Reproducing exact numbers on another cluster is unlikely. Reproducing qualitative behavior is more realistic.

## Evidence Packaging

Raw experiment artifacts are intentionally not all committed to Git. The repository commits lightweight summaries, figures, manifests, and packaging commands. Full audit or paper-grade review may require access to external evidence archives.

## What Would Strengthen The Work

- Aggregate tables across multiple runs and seeds.
- More HPA target sweeps and controller comparators.
- Real workload traces or anonymized production-like traces.
- Clear SLO and cost objectives.
- Better visualization of replica timing, latency, and resource proxy tradeoffs.
- Failure-injection tests for missing metrics, solver failure, and API errors.
- Independent reproduction on another cluster.
