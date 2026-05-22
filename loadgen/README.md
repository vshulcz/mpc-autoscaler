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

| Variable | Default | Used by | Notes |
| --- | --- | --- | --- |
| `KUBE_NAMESPACE` | `default` | local, HPA, MPC, batch | Workload namespace. Also contributes to the default service URL. |
| `WORKLOAD_NAME` | `toy-load-toy-load` | local, HPA, MPC, batch | Service/Deployment/HPA base name. Also contributes to the default service URL. |
| `SERVICE_URL` | `http://${WORKLOAD_NAME}.${KUBE_NAMESPACE}.svc.cluster.local/work` | local | Overrides the local Vegeta target URL. |
| `CPU_MS` | `20` | local, HPA | Adds the `cpu_ms` workload query parameter. |
| `JITTER_MS` | `5` | local, HPA | Adds the `jitter_ms` workload query parameter. |
| `CLIENT_TIMEOUT` | `30s` | local, HPA | Vegeta request timeout. |
| `KUBECTL_OPTS` | empty | HPA, MPC, batch | Extra `kubectl` flags, such as `--context <name>`. |
| `VEGETA_IMAGE` | `peterevans/vegeta` | HPA | In-cluster load-generator image. |
| `PYTHON_BIN` | `python3` | HPA, seasonality local | Python executable for seasonality rate generation. |
| `WATCH_REPLICAS_INTERVAL` | `0` | HPA | Seconds between replica samples; `0` disables replica watch output. |
| `MPC_PYTHON` | `<repo>/.venv/bin/python` | MPC, MPC batch | Python executable for the online controller. |
| `MPC_APPLY` | `1` | MPC | Passes `--apply` to the controller; set `0` for recommendations only. |
| `MPC_STEP_SECONDS` | `15` | MPC | Controller loop interval; some scenarios override this when unset. |
| `MPC_MIN_REPLICAS` | `2` | MPC, MPC batch | Lower replica bound; some scenarios override this when unset. |
| `MPC_MAX_REPLICAS` | `70` | MPC, MPC batch | Upper replica bound. |
| `MPC_HORIZON` | `8` | MPC, MPC batch | Prediction horizon. |
| `MPC_RATE_WINDOW` | `1m` | MPC | Prometheus rate window; some scenarios override this when unset. |
| `RESULT_DIR` | `loadgen/results` | local | Artifact path for local `.bin` and `.txt` Vegeta results. |
| `OUT_ROOT` | `experiments/_runs/baseline` for HPA, `experiments/_runs/mpc-online` for MPC, script-specific for batches | HPA, MPC, batch | Artifact path root for run directories. |

Artifact paths are affected by `RESULT_DIR` for local profile scripts and by
`OUT_ROOT` plus the optional second run-id argument for in-cluster HPA/MPC
scripts. Batch scripts also write progress logs under
`experiments/_runs/progress/`. The normalized night pipeline also accepts
`ROOT` to move its `experiments/_runs/mpc-normalized-night` artifact tree. Use
each script's `--help` output for the full list of MPC tuning variables.

## Output Directories

Local Vegeta scripts write `.bin` and `.txt` artifacts under `RESULT_DIR`, which
defaults to `loadgen/results`. In-cluster and batch scripts write run roots
under `experiments/_runs/`, including `experiments/_runs/progress/` for progress
logs. These generated directories are ignored by Git; copy only curated
experiment evidence into `experiments/thesis-evidence/`.

HPA example:

```bash
KUBE_NAMESPACE=default \
WORKLOAD_NAME=toy-load-toy-load \
OUT_ROOT="$PWD/experiments/_runs/baseline" \
WATCH_REPLICAS_INTERVAL=5 \
bash loadgen/scripts/run_hpa_experiment_incluster.sh spike hpa-spike-smoke
```

MPC example:

```bash
KUBE_NAMESPACE=default \
WORKLOAD_NAME=toy-load-toy-load \
MPC_APPLY=0 \
MPC_MIN_REPLICAS=4 \
OUT_ROOT="$PWD/experiments/_runs/mpc-online" \
bash loadgen/scripts/run_mpc_experiment_incluster.sh step mpc-step-dry-run
```

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
