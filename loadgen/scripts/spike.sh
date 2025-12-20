set -euo pipefail

if ! command -v vegeta >/dev/null 2>&1; then
  echo "vegeta binary is required on PATH" >&2
  exit 1
fi

BASE_URL="${SERVICE_URL:-http://toy-load.default.svc.cluster.local/work}"
TARGET="${BASE_URL}"
if [[ "$TARGET" == *\?* ]]; then
  TARGET="${TARGET}&cpu_ms=20&jitter_ms=5"
else
  TARGET="${TARGET}?cpu_ms=20&jitter_ms=5"
fi

RESULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../results"
mkdir -p "$RESULT_DIR"
TS="$(date +"%Y%m%d%H%M%S")"
BIN_FILE="$RESULT_DIR/spike-${TS}.bin"
REPORT_FILE="$RESULT_DIR/spike-${TS}.txt"
: > "$BIN_FILE"

attack_phase() {
  local duration="$1"
  local rate="$2"
  echo "Phase: rate=${rate} rps duration=${duration}"
  echo "GET ${TARGET}" | vegeta attack -duration="$duration" -rate="$rate" \
    | tee >(cat >>"$BIN_FILE") \
    | vegeta report
}

attack_phase 3m 20
attack_phase 30s 200
attack_phase 3m 20

vegeta report <"$BIN_FILE" | tee "$REPORT_FILE"
