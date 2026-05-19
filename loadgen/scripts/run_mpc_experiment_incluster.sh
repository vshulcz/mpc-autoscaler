#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_mpc_experiment_incluster.sh <scenario> [run-id]

Scenarios:
  step | spike | seasonality

This wrapper:
1) temporarily removes HPA for the workload,
2) runs online MPC control loop,
3) executes in-cluster load scenario,
4) restores HPA from backup.

Environment variables:
  KUBE_NAMESPACE        default: default
  WORKLOAD_NAME         default: toy-load-toy-load
  OUT_ROOT              default: <repo>/experiments/_runs/mpc-online
  MPC_PYTHON            default: <repo>/.venv/bin/python
  MPC_STEP_SECONDS      default: 15
  MPC_DURATION_SECONDS  default: 1500
  MPC_CONTROL_MODE      default: qp
  MPC_FORECAST          default: es
  MPC_ES_ALPHA          default: 0.45
  MPC_HORIZON           default: 8
  MPC_ALPHA             default: 2.5
  MPC_BETA              default: 0.5
  MPC_GAMMA             default: 0.20
  MPC_RHO_STAR          default: 0.70
  MPC_CAPACITY          default: 25.0
  MPC_NORMALIZATION_REFERENCE_REPLICAS default: 12
  MPC_MIN_REPLICAS      default: 2
  MPC_MAX_REPLICAS      default: 70
  MPC_MAX_STEP          default: 2
  MPC_CONSTRAINT_TOLERANCE default: 1e-2
  MPC_NORMALIZED_OBJECTIVE default: 1
  MPC_DEMAND_MODE       default: served_plus_inflight
  MPC_INFLIGHT_GAIN     default: 4.0
  MPC_DEMAND_CAP_RPS    default: 400.0
  MPC_EMERG_INFLIGHT    default: 20.0
  MPC_EMERG_STEP        default: 4
  MPC_EMERG_MODE        default: step
  MPC_RATE_WINDOW       default: 1m
  MPC_PROM_QUERY_RETRIES   default: 3
  MPC_PROM_QUERY_BACKOFF   default: 0.3
  MPC_SURGE_DELTA_THRESHOLD default: 1000000000 (disabled)
  MPC_SURGE_STEP            default: 2
  MPC_CAPACITY_TRIGGER_FRACTION default: 2.0 (disabled)
  MPC_CAPACITY_TRIGGER_STEP default: 2
  MPC_PROXY_EMA_ALPHA default: 0.45
  MPC_PROXY_DOWNSCALE_STABILIZATION_SECONDS default: 300
  MPC_HPA_GUARD_INTERVAL default: 15
  MPC_APPLY            default: 1 (pass --apply to controller; set 0 for dry-run recommendations)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

SCENARIO="$1"
case "$SCENARIO" in
  step|spike|seasonality) ;;
  *)
    echo "Unsupported scenario: $SCENARIO" >&2
    usage
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

KUBE_NAMESPACE="${KUBE_NAMESPACE:-default}"
WORKLOAD_NAME="${WORKLOAD_NAME:-toy-load-toy-load}"
OUT_ROOT="${OUT_ROOT:-${REPO_ROOT}/experiments/_runs/mpc-online}"
RUN_ID="${2:-$(date -u +'%Y%m%dT%H%M%SZ')-mpc-incluster}"
RUN_DIR="${OUT_ROOT}/${SCENARIO}/${RUN_ID}"
MPC_PYTHON="${MPC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
KUBECTL_CONTEXT="${KUBECTL_CONTEXT:-}"

MPC_STEP_SECONDS_WAS_SET="${MPC_STEP_SECONDS+x}"
MPC_MIN_REPLICAS_WAS_SET="${MPC_MIN_REPLICAS+x}"
MPC_RATE_WINDOW_WAS_SET="${MPC_RATE_WINDOW+x}"
MPC_EMERG_INFLIGHT_WAS_SET="${MPC_EMERG_INFLIGHT+x}"
MPC_EMERG_STEP_WAS_SET="${MPC_EMERG_STEP+x}"
MPC_EMERG_MODE_WAS_SET="${MPC_EMERG_MODE+x}"
MPC_SURGE_DELTA_WAS_SET="${MPC_SURGE_DELTA_THRESHOLD+x}"
MPC_SURGE_STEP_WAS_SET="${MPC_SURGE_STEP+x}"
MPC_CAP_FRAC_WAS_SET="${MPC_CAPACITY_TRIGGER_FRACTION+x}"
MPC_CAP_STEP_WAS_SET="${MPC_CAPACITY_TRIGGER_STEP+x}"

MPC_STEP_SECONDS="${MPC_STEP_SECONDS:-15}"
MPC_DURATION_SECONDS="${MPC_DURATION_SECONDS:-1500}"
MPC_CONTROL_MODE="${MPC_CONTROL_MODE:-qp}"
MPC_FORECAST="${MPC_FORECAST:-es}"
MPC_ES_ALPHA="${MPC_ES_ALPHA:-0.45}"
MPC_HORIZON="${MPC_HORIZON:-8}"
MPC_ALPHA="${MPC_ALPHA:-2.5}"
MPC_BETA="${MPC_BETA:-0.5}"
MPC_GAMMA="${MPC_GAMMA:-0.20}"
MPC_RHO_STAR="${MPC_RHO_STAR:-0.70}"
MPC_CAPACITY="${MPC_CAPACITY:-25.0}"
MPC_NORMALIZATION_REFERENCE_REPLICAS="${MPC_NORMALIZATION_REFERENCE_REPLICAS:-12}"
MPC_MIN_REPLICAS="${MPC_MIN_REPLICAS:-2}"
MPC_MAX_REPLICAS="${MPC_MAX_REPLICAS:-70}"
MPC_MAX_STEP="${MPC_MAX_STEP:-2}"
MPC_CONSTRAINT_TOLERANCE="${MPC_CONSTRAINT_TOLERANCE:-1e-2}"
MPC_NORMALIZED_OBJECTIVE="${MPC_NORMALIZED_OBJECTIVE:-1}"
MPC_DEMAND_MODE="${MPC_DEMAND_MODE:-served_plus_inflight}"
MPC_INFLIGHT_GAIN="${MPC_INFLIGHT_GAIN:-4.0}"
MPC_DEMAND_CAP_RPS="${MPC_DEMAND_CAP_RPS:-400.0}"
MPC_EMERG_INFLIGHT="${MPC_EMERG_INFLIGHT:-20.0}"
MPC_EMERG_STEP="${MPC_EMERG_STEP:-4}"
MPC_EMERG_MODE="${MPC_EMERG_MODE:-step}"
MPC_RATE_WINDOW="${MPC_RATE_WINDOW:-1m}"
MPC_PROM_QUERY_RETRIES="${MPC_PROM_QUERY_RETRIES:-3}"
MPC_PROM_QUERY_BACKOFF="${MPC_PROM_QUERY_BACKOFF:-0.3}"
MPC_SURGE_DELTA_THRESHOLD="${MPC_SURGE_DELTA_THRESHOLD:-1000000000}"
MPC_SURGE_STEP="${MPC_SURGE_STEP:-2}"
MPC_CAPACITY_TRIGGER_FRACTION="${MPC_CAPACITY_TRIGGER_FRACTION:-2.0}"
MPC_CAPACITY_TRIGGER_STEP="${MPC_CAPACITY_TRIGGER_STEP:-2}"
MPC_DOWNSCALE_COOLDOWN_SECONDS="${MPC_DOWNSCALE_COOLDOWN_SECONDS:-0}"
MPC_DOWNSCALE_INFLIGHT_THRESHOLD="${MPC_DOWNSCALE_INFLIGHT_THRESHOLD:--1}"
MPC_MAX_DOWNSCALE_STEP="${MPC_MAX_DOWNSCALE_STEP:-0}"
MPC_PROXY_EMA_ALPHA="${MPC_PROXY_EMA_ALPHA:-0.45}"
MPC_PROXY_DOWNSCALE_STABILIZATION_SECONDS="${MPC_PROXY_DOWNSCALE_STABILIZATION_SECONDS:-300}"
MPC_HPA_GUARD_INTERVAL="${MPC_HPA_GUARD_INTERVAL:-15}"
MPC_APPLY="${MPC_APPLY:-1}"

if [[ "${SCENARIO}" == "step" || "${SCENARIO}" == "seasonality" ]]; then
  # Step/seasonality: 30s metric window — better than 1m default for 15s control step.
  if [[ -z "${MPC_RATE_WINDOW_WAS_SET}" ]]; then
    MPC_RATE_WINDOW="30s"
  fi
fi

if [[ "${SCENARIO}" == "step" && -z "${MPC_MIN_REPLICAS_WAS_SET}" ]]; then
  MPC_MIN_REPLICAS="4"
fi

if [[ "${SCENARIO}" == "step" ]]; then
  if [[ -z "${MPC_SURGE_DELTA_WAS_SET}" ]]; then
    MPC_SURGE_DELTA_THRESHOLD="12.0"
  fi
  if [[ -z "${MPC_SURGE_STEP_WAS_SET}" ]]; then
    MPC_SURGE_STEP="4"
  fi
fi

if [[ "${SCENARIO}" == "spike" ]]; then
  # Spike-specific safety defaults; explicit env overrides still win.
  if [[ -z "${MPC_MIN_REPLICAS_WAS_SET}" ]]; then
    MPC_MIN_REPLICAS="6"
  fi
  if [[ -z "${MPC_STEP_SECONDS_WAS_SET}" ]]; then
    MPC_STEP_SECONDS="5"
  fi
  if [[ -z "${MPC_RATE_WINDOW_WAS_SET}" ]]; then
    MPC_RATE_WINDOW="15s"
  fi
  if [[ -z "${MPC_EMERG_INFLIGHT_WAS_SET}" ]]; then
    MPC_EMERG_INFLIGHT="4.0"
  fi
  if [[ -z "${MPC_EMERG_STEP_WAS_SET}" ]]; then
    MPC_EMERG_STEP="6"
  fi
  if [[ -z "${MPC_EMERG_MODE_WAS_SET}" ]]; then
    MPC_EMERG_MODE="step"
  fi
  if [[ -z "${MPC_SURGE_DELTA_WAS_SET}" ]]; then
    MPC_SURGE_DELTA_THRESHOLD="1000000000"
  fi
  if [[ -z "${MPC_SURGE_STEP_WAS_SET}" ]]; then
    MPC_SURGE_STEP="4"
  fi
  if [[ -z "${MPC_CAP_FRAC_WAS_SET}" ]]; then
    MPC_CAPACITY_TRIGGER_FRACTION="0.85"
  fi
  if [[ -z "${MPC_CAP_STEP_WAS_SET}" ]]; then
    MPC_CAPACITY_TRIGGER_STEP="4"
  fi
fi

TMP_DIR="$(mktemp -d)"
HPA_BACKUP="${TMP_DIR}/hpa-backup.yaml"
MPC_LOG="${TMP_DIR}/mpc-control-log.csv"
MPC_STDOUT="${TMP_DIR}/mpc-loop.log"
META_APPEND_FILE="${TMP_DIR}/run-meta-extra.yaml"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
  exit 1
fi

if [[ ! -x "$MPC_PYTHON" ]]; then
  echo "MPC python not found or not executable: $MPC_PYTHON" >&2
  exit 1
fi

MPC_PID=""
HPA_GUARD_PID=""
HPA_REMOVED=false

# If caller set KUBECTL_SERVER (e.g. kubectl proxy), use it for all calls.
KUBECTL_OPTS="${KUBECTL_OPTS:-}"

# Retry wrapper: kube_retry <retries> <delay_s> <kubectl args...>
kube_retry() {
  local retries="$1"; shift
  local delay="$1";   shift
  local attempt=1
  while true; do
    if kubectl ${KUBECTL_OPTS} "$@" 2>&1; then
      return 0
    fi
    if [[ "${attempt}" -ge "${retries}" ]]; then
      echo "kube_retry: all ${retries} attempts failed for: kubectl $*" >&2
      return 1
    fi
    echo "kube_retry: attempt ${attempt} failed, retrying in ${delay}s..." >&2
    sleep "${delay}"
    attempt=$((attempt + 1))
  done
}

cleanup() {
  if [[ -n "${HPA_GUARD_PID}" ]]; then
    kill "${HPA_GUARD_PID}" >/dev/null 2>&1 || true
    wait "${HPA_GUARD_PID}" >/dev/null 2>&1 || true
    HPA_GUARD_PID=""
  fi
  if [[ -n "${MPC_PID}" ]]; then
    kill "${MPC_PID}" >/dev/null 2>&1 || true
    wait "${MPC_PID}" >/dev/null 2>&1 || true
  fi
  if [[ "${HPA_REMOVED}" == true && -n "${HPA_BACKUP:-}" && -f "${HPA_BACKUP}" ]]; then
    kube_retry 5 5 -n "${KUBE_NAMESPACE}" replace --force -f "${HPA_BACKUP}" >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP_DIR}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Checking HPA ${KUBE_NAMESPACE}/${WORKLOAD_NAME}"
if kube_retry 3 2 -n "${KUBE_NAMESPACE}" get hpa "${WORKLOAD_NAME}" -o yaml > "${HPA_BACKUP}" 2>/dev/null; then
  echo "Deleting HPA to avoid control conflict"
  if ! kube_retry 7 5 -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found; then
    echo "ERROR: could not delete HPA after 7 attempts" >&2
    exit 1
  fi
  HPA_REMOVED=true
else
  echo "HPA not present, skipping backup/delete"
  HPA_BACKUP=""
fi

cat > "${META_APPEND_FILE}" <<EOF
control_mode: "mpc-online"
control_log: "mpc-control-log.csv"
control_stdout: "mpc-loop.log"
mpc_normalized_objective: "${MPC_NORMALIZED_OBJECTIVE}"
mpc_normalization_reference_replicas: "${MPC_NORMALIZATION_REFERENCE_REPLICAS}"
mpc_constraint_tolerance: "${MPC_CONSTRAINT_TOLERANCE}"
mpc_control_mode: "${MPC_CONTROL_MODE}"
mpc_forecast: "${MPC_FORECAST}"
mpc_es_alpha: "${MPC_ES_ALPHA}"
mpc_horizon: "${MPC_HORIZON}"
mpc_alpha: "${MPC_ALPHA}"
mpc_beta: "${MPC_BETA}"
mpc_gamma: "${MPC_GAMMA}"
mpc_rho_star: "${MPC_RHO_STAR}"
mpc_capacity_per_replica: "${MPC_CAPACITY}"
mpc_min_replicas: "${MPC_MIN_REPLICAS}"
mpc_max_replicas: "${MPC_MAX_REPLICAS}"
mpc_max_step: "${MPC_MAX_STEP}"
mpc_step_seconds: "${MPC_STEP_SECONDS}"
mpc_metric_rate_window: "${MPC_RATE_WINDOW}"
mpc_demand_mode: "${MPC_DEMAND_MODE}"
mpc_inflight_gain: "${MPC_INFLIGHT_GAIN}"
mpc_demand_cap_rps: "${MPC_DEMAND_CAP_RPS}"
mpc_emergency_inflight_threshold: "${MPC_EMERG_INFLIGHT}"
mpc_emergency_step: "${MPC_EMERG_STEP}"
mpc_emergency_mode: "${MPC_EMERG_MODE}"
mpc_surge_delta_threshold: "${MPC_SURGE_DELTA_THRESHOLD}"
mpc_surge_step: "${MPC_SURGE_STEP}"
mpc_capacity_trigger_fraction: "${MPC_CAPACITY_TRIGGER_FRACTION}"
mpc_capacity_trigger_step: "${MPC_CAPACITY_TRIGGER_STEP}"
mpc_apply: "${MPC_APPLY}"
EOF

if [[ -n "${HPA_BACKUP}" ]]; then
  printf 'hpa_backup: "hpa-backup.yaml"\n' >> "${META_APPEND_FILE}"
fi

echo "Starting HPA guard loop (interval=${MPC_HPA_GUARD_INTERVAL}s)"
(
  while true; do
    sleep "${MPC_HPA_GUARD_INTERVAL}"
    if kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" get hpa "${WORKLOAD_NAME}" >/dev/null 2>&1; then
      echo "HPA guard: deleting re-created HPA ${KUBE_NAMESPACE}/${WORKLOAD_NAME}"
      kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >/dev/null 2>&1 || true
    fi
  done
) &
HPA_GUARD_PID=$!

echo "MPC tuning: scenario=${SCENARIO} window=${MPC_RATE_WINDOW} norm_ref=${MPC_NORMALIZATION_REFERENCE_REPLICAS} emerg_inflight=${MPC_EMERG_INFLIGHT} emerg_step=${MPC_EMERG_STEP} emerg_mode=${MPC_EMERG_MODE} surge_delta=${MPC_SURGE_DELTA_THRESHOLD} surge_step=${MPC_SURGE_STEP} cap_frac=${MPC_CAPACITY_TRIGGER_FRACTION} cap_step=${MPC_CAPACITY_TRIGGER_STEP} downscale_cooldown=${MPC_DOWNSCALE_COOLDOWN_SECONDS} downscale_inflight=${MPC_DOWNSCALE_INFLIGHT_THRESHOLD} max_downscale_step=${MPC_MAX_DOWNSCALE_STEP}"

MPC_NORMALIZED_ARGS=()
if [[ "${MPC_NORMALIZED_OBJECTIVE}" == "1" || "${MPC_NORMALIZED_OBJECTIVE}" == "true" ]]; then
  MPC_NORMALIZED_ARGS+=(--normalized-objective)
fi

MPC_APPLY_ARGS=(--dry-run)
if [[ "${MPC_APPLY}" == "1" || "${MPC_APPLY}" == "true" ]]; then
  MPC_APPLY_ARGS=(--apply)
fi

echo "Starting MPC loop in background"
PYTHONPATH="${REPO_ROOT}/analysis${PYTHONPATH:+:${PYTHONPATH}}" "${MPC_PYTHON}" -m mpc_autoscaler_analysis.online.control_loop \
  --namespace "${KUBE_NAMESPACE}" \
  --deployment "${WORKLOAD_NAME}" \
  --step-seconds "${MPC_STEP_SECONDS}" \
  --duration-seconds "${MPC_DURATION_SECONDS}" \
  --control-mode "${MPC_CONTROL_MODE}" \
  --forecast "${MPC_FORECAST}" \
  --es-alpha "${MPC_ES_ALPHA}" \
  --horizon "${MPC_HORIZON}" \
  --alpha "${MPC_ALPHA}" \
  --beta "${MPC_BETA}" \
  --gamma "${MPC_GAMMA}" \
  --rho-star "${MPC_RHO_STAR}" \
  --capacity-per-replica "${MPC_CAPACITY}" \
  --normalization-reference-replicas "${MPC_NORMALIZATION_REFERENCE_REPLICAS}" \
  --min-replicas "${MPC_MIN_REPLICAS}" \
  --max-replicas "${MPC_MAX_REPLICAS}" \
  --max-step "${MPC_MAX_STEP}" \
  --constraint-tolerance "${MPC_CONSTRAINT_TOLERANCE}" \
  --demand-mode "${MPC_DEMAND_MODE}" \
  --inflight-gain "${MPC_INFLIGHT_GAIN}" \
  --demand-cap-rps "${MPC_DEMAND_CAP_RPS}" \
  --emergency-inflight-threshold "${MPC_EMERG_INFLIGHT}" \
  --emergency-step "${MPC_EMERG_STEP}" \
  --emergency-mode "${MPC_EMERG_MODE}" \
  --metric-rate-window "${MPC_RATE_WINDOW}" \
  --prom-query-retries "${MPC_PROM_QUERY_RETRIES}" \
  --prom-query-backoff-seconds "${MPC_PROM_QUERY_BACKOFF}" \
  --kube-context "${KUBECTL_CONTEXT}" \
  --surge-delta-threshold "${MPC_SURGE_DELTA_THRESHOLD}" \
  --surge-step "${MPC_SURGE_STEP}" \
  --capacity-trigger-fraction "${MPC_CAPACITY_TRIGGER_FRACTION}" \
  --capacity-trigger-step "${MPC_CAPACITY_TRIGGER_STEP}" \
  --downscale-cooldown-seconds "${MPC_DOWNSCALE_COOLDOWN_SECONDS}" \
  --downscale-inflight-threshold "${MPC_DOWNSCALE_INFLIGHT_THRESHOLD}" \
  --max-downscale-step "${MPC_MAX_DOWNSCALE_STEP}" \
  --proxy-ema-alpha "${MPC_PROXY_EMA_ALPHA}" \
  --proxy-downscale-stabilization-seconds "${MPC_PROXY_DOWNSCALE_STABILIZATION_SECONDS}" \
  "${MPC_NORMALIZED_ARGS[@]}" \
  "${MPC_APPLY_ARGS[@]}" \
  --log-csv "${MPC_LOG}" \
  > "${MPC_STDOUT}" 2>&1 &
MPC_PID=$!

sleep 2

echo "Running in-cluster load scenario: ${SCENARIO} (${RUN_ID})"
LOAD_STATUS=0
set +e
OUT_ROOT="${OUT_ROOT}" \
KUBE_NAMESPACE="${KUBE_NAMESPACE}" \
WORKLOAD_NAME="${WORKLOAD_NAME}" \
KUBECTL_OPTS="${KUBECTL_OPTS}" \
RUN_MODE="mpc-incluster" \
RUN_META_APPEND_FILE="${META_APPEND_FILE}" \
bash "${REPO_ROOT}/loadgen/scripts/run_hpa_experiment_incluster.sh" "${SCENARIO}" "${RUN_ID}"
LOAD_STATUS=$?
set -e

echo "Stopping MPC loop"
kill "${MPC_PID}" >/dev/null 2>&1 || true
wait "${MPC_PID}" >/dev/null 2>&1 || true
MPC_PID=""

if [[ -n "${HPA_GUARD_PID}" ]]; then
  kill "${HPA_GUARD_PID}" >/dev/null 2>&1 || true
  wait "${HPA_GUARD_PID}" >/dev/null 2>&1 || true
  HPA_GUARD_PID=""
fi

mkdir -p "${RUN_DIR}"
if [[ -n "${HPA_BACKUP:-}" && -f "${HPA_BACKUP}" ]]; then
  cp "${HPA_BACKUP}" "${RUN_DIR}/hpa-backup.yaml"
fi
if [[ -f "${MPC_LOG}" ]]; then
  cp "${MPC_LOG}" "${RUN_DIR}/mpc-control-log.csv"
else
  echo "WARNING: MPC control log not found (controller may have crashed): ${MPC_LOG}" >&2
fi
if [[ -f "${MPC_STDOUT}" ]]; then
  cp "${MPC_STDOUT}" "${RUN_DIR}/mpc-loop.log"
fi

if [[ "${MPC_SKIP_HPA_RESTORE:-0}" != "1" && "${HPA_REMOVED}" == true && -n "${HPA_BACKUP:-}" && -f "${HPA_BACKUP}" ]]; then
  echo "Restoring HPA"
  if ! kube_retry 7 5 -n "${KUBE_NAMESPACE}" replace --force -f "${HPA_BACKUP}" >/dev/null 2>&1; then
    echo "WARNING: could not restore HPA; continuing" >&2
  fi
fi
HPA_REMOVED=false

echo "MPC run artifacts saved to: ${RUN_DIR}"

if [[ "${LOAD_STATUS}" != "0" ]]; then
  exit "${LOAD_STATUS}"
fi
