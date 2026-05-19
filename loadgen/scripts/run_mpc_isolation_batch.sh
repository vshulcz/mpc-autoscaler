#!/usr/bin/env bash
set -uo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_mpc_isolation_batch.sh

Runs one-factor MPC isolation diagnostics:
  hold_safe     forecast=hold, safety overrides enabled
  es_no_safety  forecast=es, QP/MPC core, safety overrides disabled
  es_safety     forecast=es, QP/MPC core, default safety overrides enabled
  no_qp_reactive reactive proxy rule, safety overrides enabled
  proxy_hpa_safety proxy rule with EMA/downscale stabilization and safety overrides

Environment variables:
  KUBE_NAMESPACE     default: default
  WORKLOAD_NAME      default: toy-load-toy-load
  OUT_ROOT           default: <repo>/experiments/_runs/mpc-isolation
  N_RUNS             default: 1
  SCENARIOS          default: "step spike seasonality"
  VARIANTS           default: "es_no_safety es_safety"
  SETTLE_SECONDS     default: 60
  HPA_GUARD_INTERVAL_SECONDS default: 5
  MPC_NORMALIZED_OBJECTIVE default: 1
  MPC_NORMALIZATION_REFERENCE_REPLICAS default: 12
  MPC_CONSTRAINT_TOLERANCE default: 1e-2
  MPC_MAX_REPLICAS default: 70
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
OUT_ROOT="${OUT_ROOT:-${REPO_ROOT}/experiments/_runs/mpc-isolation}"
N_RUNS="${N_RUNS:-1}"
SCENARIOS="${SCENARIOS:-step spike seasonality}"
VARIANTS="${VARIANTS:-es_no_safety es_safety}"
SETTLE_SECONDS="${SETTLE_SECONDS:-60}"
KUBECTL_OPTS="${KUBECTL_OPTS:-}"
HPA_GUARD_INTERVAL_SECONDS="${HPA_GUARD_INTERVAL_SECONDS:-5}"

export KUBE_NAMESPACE WORKLOAD_NAME OUT_ROOT KUBECTL_OPTS
export MPC_ALPHA="${MPC_ALPHA:-2.5}"
export MPC_BETA="${MPC_BETA:-0.5}"
export MPC_GAMMA="${MPC_GAMMA:-0.20}"
export MPC_HORIZON="${MPC_HORIZON:-8}"
export MPC_MAX_REPLICAS="${MPC_MAX_REPLICAS:-70}"
export MPC_NORMALIZED_OBJECTIVE="${MPC_NORMALIZED_OBJECTIVE:-1}"
export MPC_NORMALIZATION_REFERENCE_REPLICAS="${MPC_NORMALIZATION_REFERENCE_REPLICAS:-12}"
export MPC_CONSTRAINT_TOLERANCE="${MPC_CONSTRAINT_TOLERANCE:-1e-2}"
export MPC_DEMAND_MODE="${MPC_DEMAND_MODE:-served_plus_inflight}"
export MPC_INFLIGHT_GAIN="${MPC_INFLIGHT_GAIN:-4.0}"
export MPC_DEMAND_CAP_RPS="${MPC_DEMAND_CAP_RPS:-400.0}"
export MPC_PYTHON="${MPC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
export MPC_CONTROL_MODE="${MPC_CONTROL_MODE:-qp}"

USER_MPC_STEP_SECONDS_SET="${MPC_STEP_SECONDS+x}"
USER_MPC_STEP_SECONDS="${MPC_STEP_SECONDS-}"
USER_MPC_MIN_REPLICAS_SET="${MPC_MIN_REPLICAS+x}"
USER_MPC_MIN_REPLICAS="${MPC_MIN_REPLICAS-}"
USER_MPC_RATE_WINDOW_SET="${MPC_RATE_WINDOW+x}"
USER_MPC_RATE_WINDOW="${MPC_RATE_WINDOW-}"
USER_MPC_EMERG_INFLIGHT_SET="${MPC_EMERG_INFLIGHT+x}"
USER_MPC_EMERG_INFLIGHT="${MPC_EMERG_INFLIGHT-}"
USER_MPC_EMERG_STEP_SET="${MPC_EMERG_STEP+x}"
USER_MPC_EMERG_STEP="${MPC_EMERG_STEP-}"
USER_MPC_EMERG_MODE_SET="${MPC_EMERG_MODE+x}"
USER_MPC_EMERG_MODE="${MPC_EMERG_MODE-}"
USER_MPC_SURGE_DELTA_THRESHOLD_SET="${MPC_SURGE_DELTA_THRESHOLD+x}"
USER_MPC_SURGE_DELTA_THRESHOLD="${MPC_SURGE_DELTA_THRESHOLD-}"
USER_MPC_SURGE_STEP_SET="${MPC_SURGE_STEP+x}"
USER_MPC_SURGE_STEP="${MPC_SURGE_STEP-}"
USER_MPC_CAPACITY_TRIGGER_FRACTION_SET="${MPC_CAPACITY_TRIGGER_FRACTION+x}"
USER_MPC_CAPACITY_TRIGGER_FRACTION="${MPC_CAPACITY_TRIGGER_FRACTION-}"
USER_MPC_CAPACITY_TRIGGER_STEP_SET="${MPC_CAPACITY_TRIGGER_STEP+x}"
USER_MPC_CAPACITY_TRIGGER_STEP="${MPC_CAPACITY_TRIGGER_STEP-}"
USER_MPC_STEP_MIN_REPLICAS_SET="${MPC_STEP_MIN_REPLICAS+x}"
USER_MPC_STEP_MIN_REPLICAS="${MPC_STEP_MIN_REPLICAS-}"
USER_MPC_STEP_SURGE_DELTA_THRESHOLD_SET="${MPC_STEP_SURGE_DELTA_THRESHOLD+x}"
USER_MPC_STEP_SURGE_DELTA_THRESHOLD="${MPC_STEP_SURGE_DELTA_THRESHOLD-}"
USER_MPC_STEP_SURGE_STEP_SET="${MPC_STEP_SURGE_STEP+x}"
USER_MPC_STEP_SURGE_STEP="${MPC_STEP_SURGE_STEP-}"
USER_MPC_STEP_EMERG_MODE_SET="${MPC_STEP_EMERG_MODE+x}"
USER_MPC_STEP_EMERG_MODE="${MPC_STEP_EMERG_MODE-}"
USER_MPC_SPIKE_MIN_REPLICAS_SET="${MPC_SPIKE_MIN_REPLICAS+x}"
USER_MPC_SPIKE_MIN_REPLICAS="${MPC_SPIKE_MIN_REPLICAS-}"
USER_MPC_SPIKE_SURGE_DELTA_THRESHOLD_SET="${MPC_SPIKE_SURGE_DELTA_THRESHOLD+x}"
USER_MPC_SPIKE_SURGE_DELTA_THRESHOLD="${MPC_SPIKE_SURGE_DELTA_THRESHOLD-}"
USER_MPC_SPIKE_EMERG_MODE_SET="${MPC_SPIKE_EMERG_MODE+x}"
USER_MPC_SPIKE_EMERG_MODE="${MPC_SPIKE_EMERG_MODE-}"

BATCH_ID="$(date -u +'%Y%m%dT%H%M%SZ')-mpc-isolation"
BATCH_LOG="${OUT_ROOT}/${BATCH_ID}.log"
mkdir -p "${OUT_ROOT}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${BATCH_LOG}"
}

format_duration() {
  local seconds="$1"
  local hours=$((seconds / 3600))
  local minutes=$(((seconds % 3600) / 60))
  local secs=$((seconds % 60))
  printf '%02dh%02dm%02ds' "${hours}" "${minutes}" "${secs}"
}

log_progress() {
  local completed="$1"
  local now elapsed remaining eta avg
  now="$(date -u +%s)"
  elapsed=$((now - BATCH_STARTED_AT))
  remaining=$((PLANNED_RUNS - completed))
  if [[ "${completed}" -gt 0 ]]; then
    avg=$((elapsed / completed))
    eta=$((avg * remaining))
  else
    eta=0
  fi
  log "Progress: ${completed}/${PLANNED_RUNS} done, failed=${failed}, remaining=${remaining}, elapsed=$(format_duration "${elapsed}"), eta=$(format_duration "${eta}")"
}

wait_available_replicas() {
  local wanted="$1"
  local deadline=$(( $(date -u +%s) + 180 ))
  local available spec_replicas
  while [[ "$(date -u +%s)" -lt "${deadline}" ]]; do
    available="$(kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" get deploy "${WORKLOAD_NAME}" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || true)"
    spec_replicas="$(kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" get deploy "${WORKLOAD_NAME}" -o jsonpath='{.spec.replicas}' 2>/dev/null || true)"
    if [[ "${available:-0}" == "${wanted}" && "${spec_replicas:-0}" == "${wanted}" ]]; then
      return 0
    fi
    if [[ "${spec_replicas:-0}" != "${wanted}" ]]; then
      log "Reapplying ${WORKLOAD_NAME} replicas=${wanted} during prepare"
      kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >> "${BATCH_LOG}" 2>&1 || true
      kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas="${wanted}" >> "${BATCH_LOG}" 2>&1 || true
    fi
    sleep 3
  done
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" get deploy "${WORKLOAD_NAME}" >> "${BATCH_LOG}" 2>&1 || true
  return 1
}

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
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

HPA_GUARD_PID=""

start_hpa_guard() {
  log "Starting batch HPA guard"
  (
    while true; do
      kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >/dev/null 2>&1 || true
      sleep "${HPA_GUARD_INTERVAL_SECONDS}"
    done
  ) &
  HPA_GUARD_PID=$!
}

restore_hpa() {
  if [[ -n "${HPA_GUARD_PID}" ]]; then
    kill "${HPA_GUARD_PID}" >/dev/null 2>&1 || true
    wait "${HPA_GUARD_PID}" >/dev/null 2>&1 || true
    HPA_GUARD_PID=""
  fi
  if [[ "${HAVE_INITIAL_HPA}" == true ]]; then
    kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" replace --force -f "${INITIAL_HPA}" >/dev/null 2>&1 || true
  fi
  rm -f "${INITIAL_HPA}" >/dev/null 2>&1 || true
}
trap restore_hpa EXIT

start_hpa_guard

prepare_run() {
  local min_rep="${MPC_MIN_REPLICAS:-2}"
  log "Resetting ${WORKLOAD_NAME} to ${min_rep} replicas"
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >> "${BATCH_LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas="${min_rep}" >> "${BATCH_LOG}" 2>&1 || return 1
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" rollout status deploy/"${WORKLOAD_NAME}" --timeout=180s >> "${BATCH_LOG}" 2>&1 || return 1
  wait_available_replicas "${min_rep}" || return 1
  log "Settling ${SETTLE_SECONDS}s"
  sleep "${SETTLE_SECONDS}"
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >> "${BATCH_LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas="${min_rep}" >> "${BATCH_LOG}" 2>&1 || return 1
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" rollout status deploy/"${WORKLOAD_NAME}" --timeout=180s >> "${BATCH_LOG}" 2>&1 || return 1
  wait_available_replicas "${min_rep}" || return 1
}

apply_user_controller_overrides() {
  [[ -n "${USER_MPC_STEP_SECONDS_SET}" ]] && export MPC_STEP_SECONDS="${USER_MPC_STEP_SECONDS}"
  [[ -n "${USER_MPC_MIN_REPLICAS_SET}" ]] && export MPC_MIN_REPLICAS="${USER_MPC_MIN_REPLICAS}"
  [[ -n "${USER_MPC_RATE_WINDOW_SET}" ]] && export MPC_RATE_WINDOW="${USER_MPC_RATE_WINDOW}"
  [[ -n "${USER_MPC_EMERG_INFLIGHT_SET}" ]] && export MPC_EMERG_INFLIGHT="${USER_MPC_EMERG_INFLIGHT}"
  [[ -n "${USER_MPC_EMERG_STEP_SET}" ]] && export MPC_EMERG_STEP="${USER_MPC_EMERG_STEP}"
  [[ -n "${USER_MPC_EMERG_MODE_SET}" ]] && export MPC_EMERG_MODE="${USER_MPC_EMERG_MODE}"
  [[ -n "${USER_MPC_SURGE_DELTA_THRESHOLD_SET}" ]] && export MPC_SURGE_DELTA_THRESHOLD="${USER_MPC_SURGE_DELTA_THRESHOLD}"
  [[ -n "${USER_MPC_SURGE_STEP_SET}" ]] && export MPC_SURGE_STEP="${USER_MPC_SURGE_STEP}"
  [[ -n "${USER_MPC_CAPACITY_TRIGGER_FRACTION_SET}" ]] && export MPC_CAPACITY_TRIGGER_FRACTION="${USER_MPC_CAPACITY_TRIGGER_FRACTION}"
  [[ -n "${USER_MPC_CAPACITY_TRIGGER_STEP_SET}" ]] && export MPC_CAPACITY_TRIGGER_STEP="${USER_MPC_CAPACITY_TRIGGER_STEP}"
  if [[ "${CURRENT_SCENARIO:-}" == "step" ]]; then
    [[ -n "${USER_MPC_STEP_MIN_REPLICAS_SET}" ]] && export MPC_MIN_REPLICAS="${USER_MPC_STEP_MIN_REPLICAS}"
    [[ -z "${USER_MPC_STEP_MIN_REPLICAS_SET}" && -z "${USER_MPC_MIN_REPLICAS_SET}" ]] && export MPC_MIN_REPLICAS="4"
    [[ -n "${USER_MPC_STEP_SURGE_DELTA_THRESHOLD_SET}" ]] && export MPC_SURGE_DELTA_THRESHOLD="${USER_MPC_STEP_SURGE_DELTA_THRESHOLD}"
    [[ -n "${USER_MPC_STEP_SURGE_STEP_SET}" ]] && export MPC_SURGE_STEP="${USER_MPC_STEP_SURGE_STEP}"
    [[ -n "${USER_MPC_STEP_EMERG_MODE_SET}" ]] && export MPC_EMERG_MODE="${USER_MPC_STEP_EMERG_MODE}"
  fi
  if [[ "${CURRENT_SCENARIO:-}" == "spike" ]]; then
    [[ -n "${USER_MPC_SPIKE_MIN_REPLICAS_SET}" ]] && export MPC_MIN_REPLICAS="${USER_MPC_SPIKE_MIN_REPLICAS}"
    [[ -z "${USER_MPC_SPIKE_MIN_REPLICAS_SET}" && -z "${USER_MPC_MIN_REPLICAS_SET}" ]] && export MPC_MIN_REPLICAS="6"
    [[ -n "${USER_MPC_SPIKE_SURGE_DELTA_THRESHOLD_SET}" ]] && export MPC_SURGE_DELTA_THRESHOLD="${USER_MPC_SPIKE_SURGE_DELTA_THRESHOLD}"
    [[ -n "${USER_MPC_SPIKE_EMERG_MODE_SET}" ]] && export MPC_EMERG_MODE="${USER_MPC_SPIKE_EMERG_MODE}"
  fi
  return 0
}

run_variant() {
  local variant="$1"
  unset MPC_STEP_SECONDS MPC_MIN_REPLICAS MPC_RATE_WINDOW MPC_EMERG_INFLIGHT MPC_EMERG_STEP MPC_EMERG_MODE MPC_SURGE_DELTA_THRESHOLD MPC_SURGE_STEP MPC_CAPACITY_TRIGGER_FRACTION MPC_CAPACITY_TRIGGER_STEP
  export MPC_CONTROL_MODE=qp
  case "${variant}" in
    es_no_safety)
      export MPC_FORECAST=es
      export MPC_EMERG_INFLIGHT=1000000000
      export MPC_SURGE_DELTA_THRESHOLD=1000000000
      export MPC_CAPACITY_TRIGGER_FRACTION=2.0
      ;;
    hold_safe)
      export MPC_FORECAST=hold
      apply_user_controller_overrides
      ;;
    es_safety)
      export MPC_FORECAST=es
      apply_user_controller_overrides
      ;;
    no_qp_reactive)
      export MPC_CONTROL_MODE=no_qp_reactive
      export MPC_FORECAST=hold
      apply_user_controller_overrides
      ;;
    proxy_hpa_safety)
      export MPC_CONTROL_MODE=proxy_hpa_safety
      export MPC_FORECAST=hold
      apply_user_controller_overrides
      ;;
    *)
      echo "Unknown variant: ${variant}" >&2
      return 2
      ;;
  esac
}

failed=0
total=0
completed=0
PLANNED_RUNS=0
for _variant in ${VARIANTS}; do
  for _scenario in ${SCENARIOS}; do
    PLANNED_RUNS=$((PLANNED_RUNS + N_RUNS))
  done
done
BATCH_STARTED_AT="$(date -u +%s)"
log "Batch ${BATCH_ID} start: variants=${VARIANTS}; scenarios=${SCENARIOS}; n=${N_RUNS}"
log_progress 0

for variant in ${VARIANTS}; do
  for scenario in ${SCENARIOS}; do
    case "${scenario}" in
      step|spike|seasonality) ;;
      *)
        echo "Unknown scenario: ${scenario}" >&2
        exit 2
        ;;
    esac
    CURRENT_SCENARIO="${scenario}"
    if ! run_variant "${variant}"; then
      exit 2
    fi
    for i in $(seq 1 "${N_RUNS}"); do
      total=$((total + 1))
      run_id="$(date -u +'%Y%m%dT%H%M%SZ')-${variant}-${scenario}-r${i}"
      log "Run ${total}: variant=${variant} scenario=${scenario} repeat=${i}/${N_RUNS} run_id=${run_id}"
      if ! prepare_run; then
        log "Prepare failed for ${run_id}"
        failed=$((failed + 1))
        completed=$((completed + 1))
        log_progress "${completed}"
        continue
      fi
      if MPC_SKIP_HPA_RESTORE=1 bash "${REPO_ROOT}/loadgen/scripts/run_mpc_experiment_incluster.sh" "${scenario}" "${run_id}" >> "${BATCH_LOG}" 2>&1; then
        log "Run completed: ${run_id}"
      else
        rc=$?
        failed=$((failed + 1))
        log "Run failed: ${run_id} exit=${rc}"
      fi
      completed=$((completed + 1))
      log_progress "${completed}"
    done
  done
done

log "Batch complete: total=${total} failed=${failed} out_root=${OUT_ROOT}"
if [[ "${failed}" -gt 0 ]]; then
  exit 1
fi
exit 0
