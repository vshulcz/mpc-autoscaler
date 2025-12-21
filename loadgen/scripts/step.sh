set -euo pipefail

if ! command -v vegeta >/dev/null 2>&1; then
  echo "vegeta binary is required on PATH" >&2
  exit 1
fi

BASE_URL="${SERVICE_URL:-http://toy-load.default.svc.cluster.local/work}"
if [[ "$BASE_URL" == *\?* ]]; then
  TARGET="${BASE_URL}&cpu_ms=20&jitter_ms=5"
else
  TARGET="${BASE_URL}?cpu_ms=20&jitter_ms=5"
fi

RESULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../results"
mkdir -p "$RESULT_DIR"
TS="$(date +"%Y%m%d%H%M%S")"
BIN_FILE="$RESULT_DIR/step-${TS}.bin"
REPORT_FILE="$RESULT_DIR/step-${TS}.txt"

echo "Running step profile against $TARGET"
: > "$BIN_FILE"

attack_phase() {
  local duration="$1"
  local rate="$2"
  echo "Phase: rate=${rate} rps, duration=${duration}"
  echo "GET ${TARGET}" | vegeta attack -duration="$duration" -rate="$rate" \
    | tee -a "$BIN_FILE" \
    | vegeta report
}

attack_phase 5m 20
attack_phase 5m 80
attack_phase 5m 40

echo "Writing summary report to $REPORT_FILE"
vegeta report <"$BIN_FILE" | tee "$REPORT_FILE"
