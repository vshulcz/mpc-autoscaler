#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_hpa_experiment_incluster.sh <scenario> [run-id]

Scenarios:
  step        20 -> 80 -> 40 RPS
  spike       20 -> 200 -> 20 RPS
  seasonality 20 one-minute sinusoidal phases (20..120 RPS)

Environment variables:
  KUBE_NAMESPACE   Kubernetes namespace with workload (default: default)
  WORKLOAD_NAME    Service/Deployment/HPA base name (default: toy-load-toy-load)
  VEGETA_IMAGE     In-cluster vegeta image (default: peterevans/vegeta)
  CPU_MS           cpu_ms workload param (default: 20)
  JITTER_MS        jitter_ms workload param (default: 5)
  CLIENT_TIMEOUT   vegeta timeout (default: 30s)
  OUT_ROOT         Output root (default: <repo>/experiments/_runs/baseline)
  PYTHON_BIN       Python executable for seasonality rate generation (default: python3)
  RUN_MODE         Metadata value for run mode (default: baseline-incluster)
  RUN_META_APPEND_FILE Optional YAML snippet appended to run-meta.yaml
  WATCH_REPLICAS_INTERVAL Seconds between replica watch samples (0 disables; default: 0)
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

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ "$SCENARIO" == "seasonality" ]] && ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "${PYTHON_BIN} is required for seasonality profile generation" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

KUBE_NAMESPACE="${KUBE_NAMESPACE:-default}"
WORKLOAD_NAME="${WORKLOAD_NAME:-toy-load-toy-load}"
VEGETA_IMAGE="${VEGETA_IMAGE:-peterevans/vegeta}"
CPU_MS="${CPU_MS:-20}"
JITTER_MS="${JITTER_MS:-5}"
CLIENT_TIMEOUT="${CLIENT_TIMEOUT:-30s}"
KUBECTL_OPTS="${KUBECTL_OPTS:-}"
RUN_MODE="${RUN_MODE:-baseline-incluster}"
RUN_META_APPEND_FILE="${RUN_META_APPEND_FILE:-}"
WATCH_REPLICAS_INTERVAL="${WATCH_REPLICAS_INTERVAL:-0}"

OUT_ROOT="${OUT_ROOT:-${REPO_ROOT}/experiments/_runs/baseline}"
RUN_ID="${2:-$(date -u +'%Y%m%dT%H%M%SZ')-incluster}"
RUN_DIR="${OUT_ROOT}/${SCENARIO}/${RUN_ID}"
if [[ -e "$RUN_DIR" ]]; then
  echo "Run directory already exists: $RUN_DIR" >&2
  exit 1
fi
mkdir -p "$RUN_DIR"

TARGET_URL="http://${WORKLOAD_NAME}.${KUBE_NAMESPACE}.svc.cluster.local/work?cpu_ms=${CPU_MS}&jitter_ms=${JITTER_MS}"
PHASES_CSV="${RUN_DIR}/phases.csv"
REPORT_TXT="${RUN_DIR}/incluster-report.txt"
META_FILE="${RUN_DIR}/run-meta.yaml"
REPLICA_WATCH_CSV="${RUN_DIR}/replica-watch.csv"

echo "phase_idx,duration,rate_rps" > "$PHASES_CSV"
echo "GET ${TARGET_URL}" > "${RUN_DIR}/target.txt"

PHASE_LINES=""
PHASE_INDEX=0

add_phase() {
  local duration="$1"
  local rate="$2"
  PHASE_INDEX=$((PHASE_INDEX + 1))
  echo "${PHASE_INDEX},${duration},${rate}" >> "$PHASES_CSV"
  PHASE_LINES+=$'\n'"phase ${PHASE_INDEX} ${duration} ${rate}"
}

case "$SCENARIO" in
  step)
    add_phase 5m 20
    add_phase 5m 80
    add_phase 5m 40
    MAX_RUN_SECONDS=1200
    ;;
  spike)
    add_phase 3m 20
    add_phase 30s 200
    add_phase 3m 20
    MAX_RUN_SECONDS=700
    ;;
  seasonality)
    for i in $(seq 0 19); do
      rate=$("$PYTHON_BIN" -c "import math; i=${i}; rate=int(round(70 + 50 * math.sin(2 * math.pi * i / 20))); rate=min(120, max(20, rate)); print(rate)")
      add_phase 1m "$rate"
    done
    MAX_RUN_SECONDS=1800
    ;;
esac

kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get hpa "$WORKLOAD_NAME" -o yaml > "${RUN_DIR}/hpa-live.yaml" 2>/dev/null || true
kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get deploy "$WORKLOAD_NAME" -o yaml > "${RUN_DIR}/deployment-live.yaml" 2>/dev/null || true

RUN_ID_LC="$(echo "$RUN_ID" | tr '[:upper:]' '[:lower:]')"
POD_NAME="vegeta-${SCENARIO}-${RUN_ID_LC}"
POD_NAME="$(echo "$POD_NAME" | tr -c 'a-z0-9-' '-' | sed -E 's/^-+//; s/-+$//; s/-+/-/g' | cut -c1-63 | sed -E 's/^-+//; s/-+$//')"
if [[ -z "$POD_NAME" ]]; then
  POD_NAME="vegeta-${SCENARIO}-run"
fi

read -r -d '' REMOTE_CMD <<EOF || true
set -e
TARGET="${TARGET_URL}"
phase() {
  idx="\$1"
  duration="\$2"
  rate="\$3"
  echo "Phase \${idx}: rate=\${rate} rps duration=\${duration}"
  echo "GET \${TARGET}" | vegeta attack -duration="\${duration}" -rate="\${rate}" -timeout="${CLIENT_TIMEOUT}" | vegeta report
}
${PHASE_LINES}
EOF

STARTED_AT_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "Running in-cluster scenario=${SCENARIO} target=${TARGET_URL}"

WATCH_PID=""
if [[ "${WATCH_REPLICAS_INTERVAL}" =~ ^[0-9]+$ && "${WATCH_REPLICAS_INTERVAL}" -gt 0 ]]; then
  echo "ts_utc,elapsed_s,spec_replicas,ready_replicas,available_replicas,hpa_current_replicas,hpa_desired_replicas" > "${REPLICA_WATCH_CSV}"
  WATCH_START_EPOCH="$(date -u +%s)"
  (
    while true; do
      now_epoch="$(date -u +%s)"
      elapsed="$((now_epoch - WATCH_START_EPOCH))"
      ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
      spec_replicas="$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get deploy "$WORKLOAD_NAME" -o jsonpath='{.spec.replicas}' 2>/dev/null || true)"
      ready_replicas="$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get deploy "$WORKLOAD_NAME" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
      available_replicas="$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get deploy "$WORKLOAD_NAME" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || true)"
      hpa_current="$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get hpa "$WORKLOAD_NAME" -o jsonpath='{.status.currentReplicas}' 2>/dev/null || true)"
      hpa_desired="$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get hpa "$WORKLOAD_NAME" -o jsonpath='{.status.desiredReplicas}' 2>/dev/null || true)"
      printf '%s,%s,%s,%s,%s,%s,%s\n' "$ts" "$elapsed" "${spec_replicas:-0}" "${ready_replicas:-0}" "${available_replicas:-0}" "${hpa_current:-0}" "${hpa_desired:-0}" >> "${REPLICA_WATCH_CSV}"
      sleep "${WATCH_REPLICAS_INTERVAL}"
    done
  ) &
  WATCH_PID=$!
fi

# Create pod without --rm/-i: avoids the race where kubectl deletes the pod
# mid-run when log streaming hiccups, losing all output after the first line.
kubectl ${KUBECTL_OPTS} --request-timeout=60s -n "$KUBE_NAMESPACE" run "$POD_NAME" \
  --image="$VEGETA_IMAGE" \
  --restart=Never \
  --pod-running-timeout=5m \
  --command -- sh -c "$REMOTE_CMD"

# Wait for pod to become Running (or already Succeeded/Failed).
echo "Waiting for pod to start..."
for _i in $(seq 1 60); do
  _PHASE=$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get pod "$POD_NAME" \
    -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
  if [[ "$_PHASE" == "Running" || "$_PHASE" == "Succeeded" || "$_PHASE" == "Failed" ]]; then
    echo "Pod phase: $_PHASE"
    break
  fi
  sleep 3
done

# Stream logs while separately watching pod completion. This avoids indefinite
# hangs when the Kubernetes log stream stalls or returns an early EOF.
kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" logs -f "$POD_NAME" \
  > "$REPORT_TXT" 2>&1 &
LOG_PID=$!

POD_TIMED_OUT=false
POD_DEADLINE=$(( $(date -u +%s) + MAX_RUN_SECONDS ))
while [[ "$(date -u +%s)" -lt "${POD_DEADLINE}" ]]; do
  if [[ -s "${REPORT_TXT}" ]]; then
    PHASE_REPORTS=$(grep -c '^Latencies     \[min, mean, 50, 90, 95, 99, max\]' "${REPORT_TXT}" || true)
    if [[ "${PHASE_REPORTS}" -ge "${PHASE_INDEX}" ]]; then
      break
    fi
  fi
  _PHASE=$(kubectl ${KUBECTL_OPTS} --request-timeout=30s -n "$KUBE_NAMESPACE" get pod "$POD_NAME" \
    -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
  if [[ "$_PHASE" == "Succeeded" || "$_PHASE" == "Failed" ]]; then
    break
  fi
  sleep 5
done

_PHASE=$(kubectl ${KUBECTL_OPTS} --request-timeout=30s -n "$KUBE_NAMESPACE" get pod "$POD_NAME" \
  -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
if [[ "$_PHASE" != "Succeeded" && "$_PHASE" != "Failed" ]]; then
  PHASE_REPORTS=$(grep -c '^Latencies     \[min, mean, 50, 90, 95, 99, max\]' "${REPORT_TXT}" 2>/dev/null || true)
  if [[ "${PHASE_REPORTS}" -lt "${PHASE_INDEX}" ]]; then
    POD_TIMED_OUT=true
  fi
fi

kill "${LOG_PID}" >/dev/null 2>&1 || true
wait "${LOG_PID}" >/dev/null 2>&1 || true
if [[ -n "${WATCH_PID}" ]]; then
  kill "${WATCH_PID}" >/dev/null 2>&1 || true
  wait "${WATCH_PID}" >/dev/null 2>&1 || true
  WATCH_PID=""
fi

# Final snapshot: ensures we have the last lines even if the streaming client
# exited early.
kubectl ${KUBECTL_OPTS} --request-timeout=60s -n "$KUBE_NAMESPACE" logs "$POD_NAME" \
  > "$REPORT_TXT" 2>/dev/null || true

if [[ "${POD_TIMED_OUT}" == true ]]; then
  if [[ -n "${WATCH_PID}" ]]; then
    kill "${WATCH_PID}" >/dev/null 2>&1 || true
    wait "${WATCH_PID}" >/dev/null 2>&1 || true
    WATCH_PID=""
  fi
  kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" delete pod "$POD_NAME" \
    --ignore-not-found >/dev/null 2>&1 || true
  echo "vegeta pod timed out after ${MAX_RUN_SECONDS}s" >&2
  exit 124
fi

# Propagate vegeta exit code so the batch can detect hard failures.
POD_EXIT=$(kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" get pod "$POD_NAME" \
  -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}' \
  2>/dev/null || echo "0")

# Clean up pod.
kubectl ${KUBECTL_OPTS} -n "$KUBE_NAMESPACE" delete pod "$POD_NAME" \
  --ignore-not-found >/dev/null 2>&1 || true

FINISHED_AT_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

CLUSTER_CONTEXT="${KUBECTL_CONTEXT:-}"
if [[ -z "${CLUSTER_CONTEXT}" ]]; then
  CLUSTER_CONTEXT="$(kubectl ${KUBECTL_OPTS} config current-context 2>/dev/null || echo unknown)"
fi

if [[ "${POD_EXIT}" != "0" && -n "${POD_EXIT}" ]]; then
  echo "vegeta pod exited with code ${POD_EXIT}" >&2
  exit "${POD_EXIT}"
fi
GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
GIT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

cat > "$META_FILE" <<EOF
scenario: "${SCENARIO}"
mode: "${RUN_MODE}"
run_id: "${RUN_ID}"
started_at_utc: "${STARTED_AT_UTC}"
finished_at_utc: "${FINISHED_AT_UTC}"
cluster_context: "${CLUSTER_CONTEXT}"
namespace: "${KUBE_NAMESPACE}"
workload_name: "${WORKLOAD_NAME}"
target_url: "${TARGET_URL}"
profile_file: "phases.csv"
runner_image: "${VEGETA_IMAGE}"
workload_knobs:
  cpu_ms: ${CPU_MS}
  jitter_ms: ${JITTER_MS}
client:
  timeout: "${CLIENT_TIMEOUT}"
git:
  commit: "${GIT_COMMIT}"
  branch: "${GIT_BRANCH}"
artifacts:
  report_txt: "incluster-report.txt"
  hpa_live: "hpa-live.yaml"
  deployment_live: "deployment-live.yaml"
EOF

if [[ -f "${REPLICA_WATCH_CSV}" ]]; then
  printf '  replica_watch: "replica-watch.csv"\n' >> "$META_FILE"
fi

if [[ -n "${RUN_META_APPEND_FILE}" && -f "${RUN_META_APPEND_FILE}" ]]; then
	printf '\n' >> "$META_FILE"
	cat "$RUN_META_APPEND_FILE" >> "$META_FILE"
fi

echo "Saved in-cluster run artifacts to: ${RUN_DIR}"
