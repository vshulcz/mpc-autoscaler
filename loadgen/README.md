# loadgen

Repeatable load-generation entry points for `toy-load` experiments.

## Profiles

Supported scenarios:

- `step`: 20 -> 80 -> 40 RPS.
- `spike`: 20 -> 200 -> 20 RPS.
- `seasonality`: 20 one-minute sinusoidal phases in the 20..120 RPS range.

## Local Vegeta Runs

Use these scripts when `vegeta` can reach the service directly:

```bash
bash loadgen/scripts/run_step_profile.sh
bash loadgen/scripts/run_spike_profile.sh
bash loadgen/scripts/run_seasonality_profile.sh
```

Defaults target `http://toy-load-toy-load.default.svc.cluster.local/work`.
Override with `SERVICE_URL`, or set `WORKLOAD_NAME` and `KUBE_NAMESPACE`.
Common knobs: `CPU_MS`, `JITTER_MS`, `CLIENT_TIMEOUT`, `RESULT_DIR`.

## In-Cluster Runs

Single HPA baseline run:

```bash
bash loadgen/scripts/run_hpa_experiment_incluster.sh step
```

Single MPC-controlled run:

```bash
bash loadgen/scripts/run_mpc_experiment_incluster.sh step
```

The MPC wrapper temporarily removes the HPA and starts the online controller with
`--apply` by default. Set `MPC_APPLY=0` to collect recommendations without
controller scaling.

Common environment variables:

- `KUBE_NAMESPACE`: workload namespace, default `default`.
- `WORKLOAD_NAME`: Service/Deployment/HPA name, default `toy-load-toy-load`.
- `KUBECTL_OPTS`: extra `kubectl` flags, such as `--context <name>`.
- `OUT_ROOT`: output root, defaulting to ignored `experiments/_runs/<workflow>`.
- `WATCH_REPLICAS_INTERVAL`: seconds between replica samples, `0` disables.

## Batch Scripts

- `run_hpa_mpc_batch.sh`: matched HPA and MPC runs for all scenarios.
- `run_hpa_target_grid.sh`: CPU HPA target sweep.
- `run_mpc_isolation_batch.sh`: one-factor MPC component diagnostics.
- `run_mpc_v3_batch.sh`: calibrated MPC-only batch.
- `run_normalized_night_pipeline.sh`: long tuning pipeline used for final candidate selection.

Batch scripts keep going after individual run failures, then exit non-zero if any
run failed. New artifacts and progress logs are written under ignored `experiments/_runs/`,
which is gitignored. Curated thesis evidence lives separately under
`experiments/thesis-evidence/`.
