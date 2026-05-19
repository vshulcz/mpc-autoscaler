#!/usr/bin/env bash
set -uo pipefail  # no -e: single run failure must not abort the batch

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_mpc_v3_batch.sh [step|spike|seasonality|all]

Runs the calibrated MPC-online batch for one scenario or for all scenarios.

Environment variables:
  KUBE_NAMESPACE      Namespace with the workload (default: default)
  WORKLOAD_NAME       Deployment name (default: toy-load-toy-load)
  KUBECTL_PROXY_PORT  Local port for kubectl proxy (default: 8001)
  N_RUNS              Runs per scenario (default: 8)
  SETTLE_SECONDS      Delay after reset before each run (default: 60)
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SCENARIO="${1:-all}"
N_RUNS="${N_RUNS:-8}"
SETTLE_SECONDS="${SETTLE_SECONDS:-60}"
SCENARIOS=()

if [[ "$SCENARIO" == "-h" || "$SCENARIO" == "--help" ]]; then
  usage
  exit 0
fi

case "${SCENARIO}" in
  step|spike|seasonality)
    SCENARIOS=("${SCENARIO}")
    ;;
  all)
    SCENARIOS=(step spike seasonality)
    ;;
  *)
    echo "Unknown scenario: ${SCENARIO}" >&2
    usage >&2
    exit 1
    ;;
esac

# Calibrated parameters (offline grid search, J-score optimised)
export MPC_ALPHA="${MPC_ALPHA:-5.0}"
export MPC_BETA="${MPC_BETA:-1.0}"
export MPC_GAMMA="${MPC_GAMMA:-0.05}"
export MPC_HORIZON="${MPC_HORIZON:-8}"
export MPC_EMERG_INFLIGHT="${MPC_EMERG_INFLIGHT:-20.0}"
export MPC_EMERG_STEP="${MPC_EMERG_STEP:-4}"

KUBE_NAMESPACE="${KUBE_NAMESPACE:-default}"
WORKLOAD_NAME="${WORKLOAD_NAME:-toy-load-toy-load}"
KUBECTL_PROXY_PORT="${KUBECTL_PROXY_PORT:-8001}"
export KUBE_NAMESPACE WORKLOAD_NAME

BATCH_LOG="${REPO_ROOT}/experiments/_runs/progress/mpc_v3_batch_$(date -u +'%Y%m%dT%H%M%SZ').log"
mkdir -p "$(dirname "$BATCH_LOG")"

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$BATCH_LOG"
}

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
  exit 1
fi

if [[ ! "${N_RUNS}" =~ ^[0-9]+$ || "${N_RUNS}" -lt 1 ]]; then
  echo "N_RUNS must be a positive integer" >&2
  exit 1
fi

if [[ ! "${SETTLE_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "SETTLE_SECONDS must be a non-negative integer" >&2
  exit 1
fi

# Start a single kubectl proxy for the whole batch.
# All kubectl calls go through localhost HTTP → no TLS handshake per call.
PROXY_PID=""
start_proxy() {
  kubectl proxy --port="${KUBECTL_PROXY_PORT}" --address=127.0.0.1 >/dev/null 2>&1 &
  PROXY_PID=$!
  sleep 2
  if ! kill -0 "${PROXY_PID}" 2>/dev/null; then
    echo "ERROR: kubectl proxy failed to start" >&2
    exit 1
  fi
  export KUBECTL_SERVER="http://127.0.0.1:${KUBECTL_PROXY_PORT}"
  export KUBECTL_OPTS="--server=${KUBECTL_SERVER}"
  log "kubectl proxy started (pid=${PROXY_PID}, port=${KUBECTL_PROXY_PORT})"
}
stop_proxy() {
  if [[ -n "${PROXY_PID}" ]]; then
    kill "${PROXY_PID}" 2>/dev/null || true
    PROXY_PID=""
  fi
}
trap stop_proxy EXIT

start_proxy

# Reset deployment to min replicas and wait for them to be ready.
# This ensures every run starts from the same initial state.
prepare_run() {
  local min_rep="${MPC_MIN_REPLICAS:-2}"
  log "Resetting ${WORKLOAD_NAME} to ${min_rep} replicas"
  kubectl ${KUBECTL_OPTS:-} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas="${min_rep}"
  kubectl ${KUBECTL_OPTS:-} -n "${KUBE_NAMESPACE}" rollout status deploy/"${WORKLOAD_NAME}" --timeout=180s
  log "Settling ${SETTLE_SECONDS}s before next run"
  sleep "${SETTLE_SECONDS}"
}

TOTAL_FAILED=0

run_scenario() {
  local sc="$1"
  local failed=0
  log "========================================"
  log "Scenario: ${sc} (${N_RUNS} runs)"
  log "Config: alpha=${MPC_ALPHA} beta=${MPC_BETA} gamma=${MPC_GAMMA} horizon=${MPC_HORIZON} emergency_threshold=${MPC_EMERG_INFLIGHT}"
  log "========================================"
  for i in $(seq 1 "${N_RUNS}"); do
    local rc=0
    RUN_ID="$(date -u +'%Y%m%dT%H%M%SZ')-mpc-v3-${sc}-r${i}"
    log "--- Preparing run ${i}/${N_RUNS} ---"
    prepare_run
    log "--- Run ${i}/${N_RUNS}: ${RUN_ID} ---"
    if bash "${REPO_ROOT}/loadgen/scripts/run_mpc_experiment_incluster.sh" "${sc}" "${RUN_ID}" >> "$BATCH_LOG" 2>&1; then
      log "Run ${i} completed"
    else
      rc=$?
      log "Run ${i} failed (exit ${rc}), continuing batch"
      failed=$((failed + 1))
      TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
  done
  log "All ${N_RUNS} ${sc} runs finished (${failed} failed)"
}

for scenario in "${SCENARIOS[@]}"; do
  run_scenario "$scenario"
done

log "Batch complete"
if [[ "${TOTAL_FAILED}" -gt 0 ]]; then
  exit 1
fi
