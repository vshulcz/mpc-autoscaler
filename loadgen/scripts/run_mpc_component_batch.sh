#!/usr/bin/env bash
set -uo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_mpc_component_batch.sh

Runs supporting MPC component diagnostics:
  hold_safe     forecast=hold, safety defaults enabled
  es_no_safety  forecast=es, spike/queue safety disabled

Environment variables:
  KUBE_NAMESPACE     default: default
  WORKLOAD_NAME      default: toy-load-toy-load
  OUT_ROOT           default: <repo>/experiments/_runs/mpc-component
  N_RUNS             default: 3
  SCENARIOS          default: "spike seasonality"
  VARIANTS           default: "hold_safe es_no_safety"
  SETTLE_SECONDS     default: 60
  KUBECTL_OPTS       kubectl flags passed through to child scripts
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

KUBE_NAMESPACE="${KUBE_NAMESPACE:-default}"
WORKLOAD_NAME="${WORKLOAD_NAME:-toy-load-toy-load}"
OUT_ROOT="${OUT_ROOT:-${REPO_ROOT}/experiments/_runs/mpc-component}"
N_RUNS="${N_RUNS:-3}"
SCENARIOS="${SCENARIOS:-spike seasonality}"
VARIANTS="${VARIANTS:-hold_safe es_no_safety}"
SETTLE_SECONDS="${SETTLE_SECONDS:-60}"
KUBECTL_OPTS="${KUBECTL_OPTS:-}"

export KUBE_NAMESPACE WORKLOAD_NAME OUT_ROOT KUBECTL_OPTS
export MPC_ALPHA="${MPC_ALPHA:-5.0}"
export MPC_BETA="${MPC_BETA:-1.0}"
export MPC_GAMMA="${MPC_GAMMA:-0.05}"
export MPC_HORIZON="${MPC_HORIZON:-8}"
export MPC_DEMAND_MODE="${MPC_DEMAND_MODE:-served_plus_inflight}"
export MPC_INFLIGHT_GAIN="${MPC_INFLIGHT_GAIN:-4.0}"
export MPC_DEMAND_CAP_RPS="${MPC_DEMAND_CAP_RPS:-400.0}"
export MPC_PYTHON="${MPC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"

BATCH_ID="$(date -u +'%Y%m%dT%H%M%SZ')-mpc-components"
BATCH_LOG="${OUT_ROOT}/${BATCH_ID}.log"
mkdir -p "${OUT_ROOT}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${BATCH_LOG}"
}

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
  exit 1
fi

if [[ ! -x "${MPC_PYTHON}" ]]; then
  echo "MPC python not found or not executable: ${MPC_PYTHON}" >&2
  exit 1
fi

if [[ ! "${N_RUNS}" =~ ^[0-9]+$ || "${N_RUNS}" -lt 1 ]]; then
  echo "N_RUNS must be a positive integer" >&2
  exit 1
fi

INITIAL_HPA="$(mktemp)"
HAVE_INITIAL_HPA=false
if kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" get hpa "${WORKLOAD_NAME}" -o yaml > "${INITIAL_HPA}" 2>/dev/null; then
  HAVE_INITIAL_HPA=true
fi

restore_hpa() {
  if [[ "${HAVE_INITIAL_HPA}" == true ]]; then
    kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" replace --force -f "${INITIAL_HPA}" >/dev/null 2>&1 || true
  fi
  rm -f "${INITIAL_HPA}" >/dev/null 2>&1 || true
}
trap restore_hpa EXIT

prepare_run() {
  local min_rep="${MPC_MIN_REPLICAS:-2}"
  log "Resetting ${WORKLOAD_NAME} to ${min_rep} replicas"
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas="${min_rep}" >> "${BATCH_LOG}" 2>&1 || return 1
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" rollout status deploy/"${WORKLOAD_NAME}" --timeout=180s >> "${BATCH_LOG}" 2>&1 || return 1
  log "Settling ${SETTLE_SECONDS}s"
  sleep "${SETTLE_SECONDS}"
}

run_variant() {
  local variant="$1"
  case "${variant}" in
    hold_safe)
      export MPC_FORECAST=hold
      unset MPC_EMERG_INFLIGHT MPC_SURGE_DELTA_THRESHOLD MPC_CAPACITY_TRIGGER_FRACTION
      ;;
    es_no_safety)
      export MPC_FORECAST=es
      export MPC_EMERG_INFLIGHT=1000000000
      export MPC_SURGE_DELTA_THRESHOLD=1000000000
      export MPC_CAPACITY_TRIGGER_FRACTION=2.0
      ;;
    *)
      echo "Unknown variant: ${variant}" >&2
      return 2
      ;;
  esac
}

failed=0
total=0
log "Batch ${BATCH_ID} start: variants=${VARIANTS}; scenarios=${SCENARIOS}; n=${N_RUNS}"

for variant in ${VARIANTS}; do
  if ! run_variant "${variant}"; then
    exit 2
  fi
  for scenario in ${SCENARIOS}; do
    case "${scenario}" in
      step|spike|seasonality) ;;
      *)
        echo "Unknown scenario: ${scenario}" >&2
        exit 2
        ;;
    esac
    for i in $(seq 1 "${N_RUNS}"); do
      total=$((total + 1))
      run_id="$(date -u +'%Y%m%dT%H%M%SZ')-${variant}-${scenario}-r${i}"
      log "Run ${total}: variant=${variant} scenario=${scenario} repeat=${i}/${N_RUNS} run_id=${run_id}"
      if ! prepare_run; then
        log "Prepare failed for ${run_id}"
        failed=$((failed + 1))
        continue
      fi
      if bash "${REPO_ROOT}/loadgen/scripts/run_mpc_experiment_incluster.sh" "${scenario}" "${run_id}" >> "${BATCH_LOG}" 2>&1; then
        log "Run completed: ${run_id}"
      else
        rc=$?
        failed=$((failed + 1))
        log "Run failed: ${run_id} exit=${rc}"
      fi
    done
  done
done

log "Batch complete: total=${total} failed=${failed} out_root=${OUT_ROOT}"
if [[ "${failed}" -gt 0 ]]; then
  exit 1
fi
exit 0
