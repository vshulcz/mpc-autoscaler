#!/usr/bin/env bash
set -uo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_hpa_target_grid.sh

Environment variables:
  KUBE_NAMESPACE     default: default
  WORKLOAD_NAME      default: toy-load-toy-load
  OUT_ROOT           default: <repo>/experiments/_runs/hpa-target-grid
  TARGETS            default: "60 100 150 200 250 300 350"
  SCENARIOS          default: "step spike seasonality"
  N_RUNS             default: 1
  SETTLE_SECONDS     default: 60
  KUBECTL_OPTS       kubectl flags, e.g. "--context vshulcz-cluster"
  ARGO_NAMESPACE     default: argocd
  ARGO_APP           default: toy-load
  MANAGE_ARGO_AUTOSYNC default: 1
  WATCH_REPLICAS_INTERVAL default: 5
  HPA_MAX_REPLICAS   optional maxReplicas override for run variants
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
OUT_ROOT="${OUT_ROOT:-${REPO_ROOT}/experiments/_runs/hpa-target-grid}"
TARGETS="${TARGETS:-60 100 150 200 250 300 350}"
SCENARIOS="${SCENARIOS:-step spike seasonality}"
N_RUNS="${N_RUNS:-1}"
SETTLE_SECONDS="${SETTLE_SECONDS:-60}"
KUBECTL_OPTS="${KUBECTL_OPTS:-}"
ARGO_NAMESPACE="${ARGO_NAMESPACE:-argocd}"
ARGO_APP="${ARGO_APP:-toy-load}"
MANAGE_ARGO_AUTOSYNC="${MANAGE_ARGO_AUTOSYNC:-1}"
WATCH_REPLICAS_INTERVAL="${WATCH_REPLICAS_INTERVAL:-5}"
BASE_HPA_TARGET="${BASE_HPA_TARGET:-60}"
HPA_MAX_REPLICAS="${HPA_MAX_REPLICAS:-}"

BATCH_ID="$(date -u +'%Y%m%dT%H%M%SZ')-hpa-target-grid"
BATCH_LOG="${OUT_ROOT}/${BATCH_ID}.log"
mkdir -p "${OUT_ROOT}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${BATCH_LOG}"
}

restore_baseline() {
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >>"${BATCH_LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas=2 >>"${BATCH_LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" rollout status deploy/"${WORKLOAD_NAME}" --timeout=180s >>"${BATCH_LOG}" 2>&1 || true
  helm template toy-load "${REPO_ROOT}/toy-load/deploy/helm/toy-load" --namespace "${KUBE_NAMESPACE}" --show-only templates/hpa.yaml \
    | kubectl ${KUBECTL_OPTS} apply -f - >>"${BATCH_LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" annotate hpa "${WORKLOAD_NAME}" \
    "argocd.argoproj.io/tracking-id=${ARGO_APP}:autoscaling/HorizontalPodAutoscaler:${KUBE_NAMESPACE}/${WORKLOAD_NAME}" \
    --overwrite >>"${BATCH_LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" patch hpa "${WORKLOAD_NAME}" --type=json \
    -p="[{\"op\":\"replace\",\"path\":\"/spec/metrics/0/resource/target/averageUtilization\",\"value\":${BASE_HPA_TARGET}}]" \
    >>"${BATCH_LOG}" 2>&1 || true
}

restore_argocd() {
  if [[ "${MANAGE_ARGO_AUTOSYNC}" == "1" ]]; then
    kubectl ${KUBECTL_OPTS} -n "${ARGO_NAMESPACE}" patch application "${ARGO_APP}" --type=merge \
      -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true},"syncOptions":["CreateNamespace=true","RespectIgnoreDifferences=true"]}}}' \
      >>"${BATCH_LOG}" 2>&1 || true
  fi
}

cleanup() {
  restore_argocd
  restore_baseline
}

if [[ ! "${N_RUNS}" =~ ^[0-9]+$ || "${N_RUNS}" -lt 1 ]]; then
  echo "N_RUNS must be a positive integer" >&2
  exit 1
fi

if [[ -n "${HPA_MAX_REPLICAS}" && (! "${HPA_MAX_REPLICAS}" =~ ^[0-9]+$ || "${HPA_MAX_REPLICAS}" -lt 1) ]]; then
  echo "HPA_MAX_REPLICAS must be a positive integer" >&2
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
  exit 1
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required on PATH" >&2
  exit 1
fi

trap cleanup EXIT

if [[ "${MANAGE_ARGO_AUTOSYNC}" == "1" ]]; then
  log "Suspending Argo auto-sync for ${ARGO_NAMESPACE}/${ARGO_APP}"
  kubectl ${KUBECTL_OPTS} -n "${ARGO_NAMESPACE}" patch application "${ARGO_APP}" --type=json \
    -p='[{"op":"remove","path":"/spec/syncPolicy/automated"}]' >>"${BATCH_LOG}" 2>&1 || true
fi

failed=0
total=0
log "Batch ${BATCH_ID} start: targets=${TARGETS}; scenarios=${SCENARIOS}; n=${N_RUNS}"

for target in ${TARGETS}; do
  if [[ ! "${target}" =~ ^[0-9]+$ ]]; then
    log "Skipping invalid target=${target}"
    continue
  fi
  for scenario in ${SCENARIOS}; do
    case "${scenario}" in
      step|spike|seasonality) ;;
      *) log "Skipping invalid scenario=${scenario}"; continue ;;
    esac
    for run_idx in $(seq 1 "${N_RUNS}"); do
      total=$((total + 1))
      run_id="$(date -u +'%Y%m%dT%H%M%SZ')-hpa-t${target}-${scenario}-r${run_idx}"
      target_root="${OUT_ROOT}/target_${target}"
      meta_extra="$(mktemp)"
      cat >"${meta_extra}" <<EOF
hpa_target_average_utilization: ${target}
EOF

      log "Run ${total}: target=${target} scenario=${scenario} run_id=${run_id}"
      restore_baseline
      kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" patch hpa "${WORKLOAD_NAME}" --type=json \
        -p="[{\"op\":\"replace\",\"path\":\"/spec/metrics/0/resource/target/averageUtilization\",\"value\":${target}}]" \
        >>"${BATCH_LOG}" 2>&1 || true
      if [[ -n "${HPA_MAX_REPLICAS}" ]]; then
        kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" patch hpa "${WORKLOAD_NAME}" --type=json \
          -p="[{\"op\":\"replace\",\"path\":\"/spec/maxReplicas\",\"value\":${HPA_MAX_REPLICAS}}]" \
          >>"${BATCH_LOG}" 2>&1 || true
        printf 'hpa_max_replicas: %s\n' "${HPA_MAX_REPLICAS}" >>"${meta_extra}"
      fi
      log "Settling ${SETTLE_SECONDS}s"
      sleep "${SETTLE_SECONDS}"

      WATCH_REPLICAS_INTERVAL="${WATCH_REPLICAS_INTERVAL}" \
      RUN_MODE="hpa-target-grid" \
      RUN_META_APPEND_FILE="${meta_extra}" \
      OUT_ROOT="${target_root}" \
      KUBE_NAMESPACE="${KUBE_NAMESPACE}" \
      WORKLOAD_NAME="${WORKLOAD_NAME}" \
      KUBECTL_OPTS="${KUBECTL_OPTS}" \
      bash "${SCRIPT_DIR}/run_hpa_experiment_incluster.sh" "${scenario}" "${run_id}" \
        >>"${BATCH_LOG}" 2>&1
      status=$?
      rm -f "${meta_extra}" >/dev/null 2>&1 || true
      if [[ "${status}" != "0" ]]; then
        failed=$((failed + 1))
        log "Run failed: target=${target} scenario=${scenario} status=${status}"
      else
        log "Run completed: target=${target} scenario=${scenario} run_id=${run_id}"
      fi
    done
  done
done

log "Batch complete: total=${total} failed=${failed} out_root=${OUT_ROOT}"
if [[ "${failed}" -gt 0 ]]; then
  exit 1
fi
exit 0
