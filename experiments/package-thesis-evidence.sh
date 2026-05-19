#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT="${1:-/tmp/mpc-autoscaler-thesis-evidence.tar.gz}"

cd "${REPO_ROOT}"

tar --exclude='__pycache__' --exclude='.DS_Store' -czf "${OUT}" \
  experiments/README.md \
  experiments/MANIFEST.md \
  experiments/EVIDENCE_MAP.csv \
  experiments/ARCHIVE_INDEX.md \
  experiments/package-thesis-evidence.sh \
  experiments/templates/run-meta.template.yaml \
  experiments/thesis-evidence/main/hpa60-cpu-hpa-max70 \
  experiments/thesis-evidence/main/hybrid-sa-max70-tuned \
  experiments/thesis-evidence/comparators/proxy-hpa-safety-max70 \
  experiments/thesis-evidence/comparators/no-qp-reactive-max70 \
  experiments/thesis-evidence/comparators/vanilla-hpa80-max70

shasum -a 256 "${OUT}" > "${OUT}.sha256"
printf 'wrote %s\n' "${OUT}"
printf 'wrote %s.sha256\n' "${OUT}"
