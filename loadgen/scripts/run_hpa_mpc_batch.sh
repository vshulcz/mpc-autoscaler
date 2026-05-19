#!/usr/bin/env bash

set -uo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_hpa_mpc_batch.sh [N_MPC [N_HPA]]

Runs fresh HPA baseline experiments and MPC experiments for each scenario:
  step, spike, seasonality

Arguments:
  N_MPC  Number of MPC runs per scenario (default: 5)
  N_HPA  Number of HPA runs per scenario (default: 3)

Environment variables:
  COOLDOWN_SECONDS  Delay between runs (default: 30)
  KUBECTL_OPTS      kubectl flags passed through to child scripts
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

N_MPC="${1:-5}"
N_HPA="${2:-3}"
COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-30}"
SCENARIOS=(step spike seasonality)

validate_positive_int() {
  local value="$1"
  local name="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || [[ "$value" -lt 0 ]]; then
    echo "${name} must be a non-negative integer, got: ${value}" >&2
    exit 1
  fi
}

validate_positive_int "$N_MPC" "N_MPC"
validate_positive_int "$N_HPA" "N_HPA"
validate_positive_int "$COOLDOWN_SECONDS" "COOLDOWN_SECONDS"

BATCH_LOG="${REPO_ROOT}/experiments/_runs/progress/hpa_mpc_batch_$(date -u +'%Y%m%dT%H%M%SZ').log"
mkdir -p "$(dirname "$BATCH_LOG")"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$BATCH_LOG"; }
log "=== HPA/MPC batch START: N_MPC=${N_MPC} N_HPA=${N_HPA} ==="

PASS=0
FAIL=0

run_one() {
  local label="$1"
  local out_root="$2"
  local script_name="$3"
  local run_prefix="$4"
  local scenario="$5"
  local idx="$6"
  local run_id
  local rc=0

  run_id="$(date -u +'%Y%m%dT%H%M%SZ')-${run_prefix}-${scenario}-r${idx}"
  log "START ${label} ${scenario} run ${idx} (${run_id})"

  if OUT_ROOT="${out_root}" \
    bash "${REPO_ROOT}/loadgen/scripts/${script_name}" \
    "${scenario}" "${run_id}" >> "$BATCH_LOG" 2>&1; then
    log "OK    ${label} ${scenario} run ${idx}"
    PASS=$((PASS + 1))
  else
    rc=$?
    log "FAIL  ${label} ${scenario} run ${idx} (exit ${rc})"
    FAIL=$((FAIL + 1))
  fi

  if [[ "$COOLDOWN_SECONDS" -gt 0 ]]; then
    sleep "$COOLDOWN_SECONDS"
  fi
}

run_mpc() {
  run_one \
    "MPC" \
    "${REPO_ROOT}/experiments/_runs/mpc-online" \
    "run_mpc_experiment_incluster.sh" \
    "mpc-v2" \
    "$1" \
    "$2"
}

run_hpa() {
  run_one \
    "HPA" \
    "${REPO_ROOT}/experiments/_runs/baseline" \
    "run_hpa_experiment_incluster.sh" \
    "hpa-v2" \
    "$1" \
    "$2"
}

run_scenario() {
  local scenario="$1"
  local i

  log "--- Scenario: ${scenario} ---"
  for i in $(seq 1 "$N_HPA"); do run_hpa "$scenario" "$i"; done
  for i in $(seq 1 "$N_MPC"); do run_mpc "$scenario" "$i"; done
}

for scenario in "${SCENARIOS[@]}"; do
  run_scenario "$scenario"
done

log "=== DONE: pass=${PASS} fail=${FAIL} ==="
if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
