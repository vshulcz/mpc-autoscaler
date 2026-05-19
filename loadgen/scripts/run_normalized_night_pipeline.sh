#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROOT="${ROOT:-${REPO_ROOT}/experiments/_runs/mpc-normalized-night}"
PY="${MPC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
LOG="${ROOT}/night-pipeline.log"
KUBE_NAMESPACE="${KUBE_NAMESPACE:-default}"
WORKLOAD_NAME="${WORKLOAD_NAME:-toy-load-toy-load}"
KUBECTL_OPTS="${KUBECTL_OPTS:-}"
ARGO_APP="${ARGO_APP:-toy-load}"
BASE_HPA_TARGET="${BASE_HPA_TARGET:-60}"
SETTLE_SECONDS="${SETTLE_SECONDS:-60}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  bash loadgen/scripts/run_normalized_night_pipeline.sh

Environment variables:
  ROOT             output root (default: <repo>/experiments/_runs/mpc-normalized-night)
  MPC_PYTHON       Python executable (default: <repo>/.venv/bin/python)
  KUBE_NAMESPACE   Kubernetes namespace (default: default)
  WORKLOAD_NAME    Deployment/HPA name (default: toy-load-toy-load)
  KUBECTL_OPTS     kubectl flags
  ARGO_APP         ArgoCD app name for optional tracking annotation (default: toy-load)
  BASE_HPA_TARGET  restored CPU HPA target (default: 60)
  SETTLE_SECONDS   settle delay passed to child batches (default: 60)
EOF
  exit 0
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required on PATH" >&2
  exit 1
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required on PATH" >&2
  exit 1
fi

if [[ ! -x "${PY}" ]]; then
  echo "MPC python not found or not executable: ${PY}" >&2
  exit 1
fi

if [[ ! "${BASE_HPA_TARGET}" =~ ^[0-9]+$ || "${BASE_HPA_TARGET}" -lt 1 ]]; then
  echo "BASE_HPA_TARGET must be a positive integer" >&2
  exit 1
fi

if [[ ! "${SETTLE_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "SETTLE_SECONDS must be a non-negative integer" >&2
  exit 1
fi

mkdir -p "${ROOT}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${LOG}"
}

restore_cluster() {
  log "Restoring CPU-HPA baseline"
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" delete hpa "${WORKLOAD_NAME}" --ignore-not-found >/dev/null 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" scale deploy "${WORKLOAD_NAME}" --replicas=2 >/dev/null 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" rollout status deploy/"${WORKLOAD_NAME}" --timeout=180s >>"${LOG}" 2>&1 || true
  helm template toy-load "${REPO_ROOT}/toy-load/deploy/helm/toy-load" --namespace "${KUBE_NAMESPACE}" --show-only templates/hpa.yaml | kubectl ${KUBECTL_OPTS} apply -f - >>"${LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" annotate hpa "${WORKLOAD_NAME}" \
    "argocd.argoproj.io/tracking-id=${ARGO_APP}:autoscaling/HorizontalPodAutoscaler:${KUBE_NAMESPACE}/${WORKLOAD_NAME}" \
    --overwrite >>"${LOG}" 2>&1 || true
  kubectl ${KUBECTL_OPTS} -n "${KUBE_NAMESPACE}" patch hpa "${WORKLOAD_NAME}" --type=json \
    -p="[{\"op\":\"replace\",\"path\":\"/spec/metrics/0/resource/target/averageUtilization\",\"value\":${BASE_HPA_TARGET}}]" \
    >>"${LOG}" 2>&1 || true
}

run_batch() {
  local label="$1"
  local out_root="$2"
  local variants="$3"
  local scenarios="$4"
  local n_runs="$5"
  local beta="$6"
  local gamma="$7"

  log "START ${label}: variants=${variants}; scenarios=${scenarios}; n=${n_runs}; beta=${beta}; gamma=${gamma}; out=${out_root}"
  OUT_ROOT="${out_root}" \
  N_RUNS="${n_runs}" \
  VARIANTS="${variants}" \
  SCENARIOS="${scenarios}" \
  SETTLE_SECONDS="${SETTLE_SECONDS}" \
  KUBE_NAMESPACE="${KUBE_NAMESPACE}" \
  WORKLOAD_NAME="${WORKLOAD_NAME}" \
  KUBECTL_OPTS="${KUBECTL_OPTS}" \
  MPC_NORMALIZED_OBJECTIVE=1 \
  MPC_ALPHA=5.0 \
  MPC_BETA="${beta}" \
  MPC_GAMMA="${gamma}" \
  MPC_PYTHON="${PY}" \
  bash "${REPO_ROOT}/loadgen/scripts/run_mpc_isolation_batch.sh" >>"${LOG}" 2>&1
  log "DONE ${label}"
}

summarize_and_select_spike() {
  "${PY}" - "${ROOT}" <<'PY'
from pathlib import Path
import csv, math, re, sys

root = Path(sys.argv[1])
spike_root = root / "spike_tune"
summary_path = root / "spike_tune_summary.csv"
top_path = root / "top2_spike.txt"

def num(s):
    return float(s.replace("p", "."))

def parse_name(name):
    b, g = name.split("_")
    return num(b[1:]), num(g[1:])

def parse_lat(x):
    x = x.strip()
    m = re.match(r"([0-9.]+)(µs|ms|s)$", x)
    if not m:
        return math.nan
    v = float(m.group(1))
    unit = m.group(2)
    return v / 1000 if unit == "µs" else v if unit == "ms" else v * 1000

def parse_report(path):
    phases = []
    cur = None
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"Phase (\d+): rate=([0-9.]+) rps duration=(.*)", line)
        if m:
            cur = {"phase": int(m.group(1)), "rate": float(m.group(2))}
            phases.append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r"Requests\s+\[total, rate, throughput\]\s+(\d+),\s*([0-9.]+),\s*([0-9.]+)", line)
        if m:
            cur["requests"] = int(m.group(1))
        m = re.search(r"Latencies\s+\[min, mean, 50, 90, 95, 99, max\]\s+(.+)", line)
        if m:
            vals = [v.strip() for v in m.group(1).split(",")]
            cur["p95_ms"] = parse_lat(vals[4])
            cur["p99_ms"] = parse_lat(vals[5])
        m = re.search(r"Status Codes\s+\[code:count\]\s+(.+)", line)
        if m:
            counts = {int(k): int(v) for k, v in re.findall(r"(\d+):(\d+)", m.group(1))}
            cur["ok"] = counts.get(200, 0)
            cur["fail"] = sum(counts.values()) - counts.get(200, 0)
    return phases

def summarize_run(run):
    phases = parse_report(run / "incluster-report.txt")
    focus = phases[1]
    total = sum(p.get("requests", 0) for p in phases)
    ok = sum(p.get("ok", 0) for p in phases)
    fail = sum(p.get("fail", 0) for p in phases)
    rows = list(csv.DictReader((run / "mpc-control-log.csv").open()))
    reps = [int(r["applied_replicas"]) for r in rows]
    avg = sum(reps) / len(reps)
    var = sum(abs(reps[i] - reps[i - 1]) for i in range(1, len(reps)))
    bad = sum(1 for r in rows if r["solver_status"] != "optimal")
    return {
        "p95_ms": focus.get("p95_ms", math.nan),
        "p99_ms": focus.get("p99_ms", math.nan),
        "success_pct": ok / total * 100 if total else math.nan,
        "fail": fail,
        "avg_replicas": avg,
        "V": var,
        "bad_qp": bad,
    }

rows = []
for cfg in sorted(p.name for p in spike_root.iterdir() if p.is_dir()):
    beta, gamma = parse_name(cfg)
    runs = list((spike_root / cfg / "spike").glob("*"))
    if not runs or not (runs[-1] / "mpc-control-log.csv").exists():
        continue
    s = summarize_run(runs[-1])
    invalid = 1 if s["p95_ms"] >= 10000 or s["success_pct"] < 99.0 else 0
    score = (
        invalid * 1_000_000
        + max(0, 99.8 - s["success_pct"]) * 2000
        + max(0, s["p95_ms"] - 210) * 2
        + max(0, s["p99_ms"] - 300)
        + max(0, s["avg_replicas"] - 9.88) * 500
        + max(0, s["V"] - 27) * 25
        + s["avg_replicas"] * 10
        + s["V"] * 2
        + s["p95_ms"] * 0.05
        + s["bad_qp"] * 100
    )
    rows.append({"config": cfg, "beta": beta, "gamma": gamma, "score": score, **s})

rows.sort(key=lambda r: r["score"])
with summary_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["config", "beta", "gamma", "score", "p95_ms", "p99_ms", "success_pct", "fail", "avg_replicas", "V", "bad_qp"])
    writer.writeheader()
    writer.writerows(rows)
with top_path.open("w") as f:
    for r in rows[:2]:
        f.write(f"{r['config']} {r['beta']} {r['gamma']} {r['score']}\n")
PY
}

select_final() {
  "${PY}" - "${ROOT}" <<'PY'
from pathlib import Path
import csv, math, re, sys

root = Path(sys.argv[1])
top = [line.split() for line in (root / "top2_spike.txt").read_text().splitlines() if line.strip()]
summary_path = root / "final_candidate_summary.csv"
selected_path = root / "selected_final.sh"

limits = {
    "step": {"p95": 1372, "p99": 2285, "avg": 10.87, "V": 40},
    "spike": {"p95": 210, "p99": 281, "avg": 9.88, "V": 27},
    "seasonality": {"p95": 83, "p99": 99, "avg": 11.43, "V": 70},
}

def parse_lat(x):
    x = x.strip()
    m = re.match(r"([0-9.]+)(µs|ms|s)$", x)
    if not m:
        return math.nan
    v = float(m.group(1))
    unit = m.group(2)
    return v / 1000 if unit == "µs" else v if unit == "ms" else v * 1000

def parse_report(path):
    phases = []
    cur = None
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"Phase (\d+): rate=([0-9.]+) rps duration=(.*)", line)
        if m:
            cur = {"phase": int(m.group(1)), "rate": float(m.group(2))}
            phases.append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r"Requests\s+\[total, rate, throughput\]\s+(\d+),\s*([0-9.]+),\s*([0-9.]+)", line)
        if m:
            cur["requests"] = int(m.group(1))
        m = re.search(r"Latencies\s+\[min, mean, 50, 90, 95, 99, max\]\s+(.+)", line)
        if m:
            vals = [v.strip() for v in m.group(1).split(",")]
            cur["p95_ms"] = parse_lat(vals[4])
            cur["p99_ms"] = parse_lat(vals[5])
        m = re.search(r"Status Codes\s+\[code:count\]\s+(.+)", line)
        if m:
            counts = {int(k): int(v) for k, v in re.findall(r"(\d+):(\d+)", m.group(1))}
            cur["ok"] = counts.get(200, 0)
            cur["fail"] = sum(counts.values()) - counts.get(200, 0)
    return phases

def summarize_run(run, scenario):
    phases = parse_report(run / "incluster-report.txt")
    focus = phases[1] if scenario in ("step", "spike") else max([p for p in phases if "p95_ms" in p], key=lambda p: p["rate"])
    total = sum(p.get("requests", 0) for p in phases)
    ok = sum(p.get("ok", 0) for p in phases)
    fail = sum(p.get("fail", 0) for p in phases)
    rows = list(csv.DictReader((run / "mpc-control-log.csv").open()))
    reps = [int(r["applied_replicas"]) for r in rows]
    avg = sum(reps) / len(reps)
    var = sum(abs(reps[i] - reps[i - 1]) for i in range(1, len(reps)))
    bad = sum(1 for r in rows if r["solver_status"] != "optimal")
    return focus["p95_ms"], focus["p99_ms"], ok / total * 100 if total else math.nan, fail, avg, var, bad

rows = []
for cfg, beta, gamma, _ in top:
    total_score = 0.0
    complete = True
    for scenario in ["step", "spike", "seasonality"]:
        base = root / "spike_tune" / cfg / scenario if scenario == "spike" else root / "cross" / cfg / scenario
        runs = sorted([p for p in base.glob("*") if p.is_dir()]) if base.exists() else []
        if not runs or not (runs[-1] / "mpc-control-log.csv").exists():
            complete = False
            continue
        p95, p99, succ, fail, avg, var, bad = summarize_run(runs[-1], scenario)
        lim = limits[scenario]
        score = (
            max(0, 99.8 - succ) * 2000
            + max(0, p95 - lim["p95"]) * 2
            + max(0, p99 - lim["p99"])
            + max(0, avg - lim["avg"]) * 500
            + max(0, var - lim["V"]) * 25
            + avg * 10
            + var * 2
            + p95 * 0.05
            + bad * 100
        )
        total_score += score
        rows.append({"config": cfg, "beta": beta, "gamma": gamma, "scenario": scenario, "score": score, "p95_ms": p95, "p99_ms": p99, "success_pct": succ, "fail": fail, "avg_replicas": avg, "V": var, "bad_qp": bad})
    if not complete:
        total_score += 10_000_000
    rows.append({"config": cfg, "beta": beta, "gamma": gamma, "scenario": "TOTAL", "score": total_score, "p95_ms": "", "p99_ms": "", "success_pct": "", "fail": "", "avg_replicas": "", "V": "", "bad_qp": ""})

totals = [r for r in rows if r["scenario"] == "TOTAL"]
totals.sort(key=lambda r: float(r["score"]))
selected = totals[0]
with summary_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["config", "beta", "gamma", "scenario", "score", "p95_ms", "p99_ms", "success_pct", "fail", "avg_replicas", "V", "bad_qp"])
    writer.writeheader()
    writer.writerows(rows)
selected_path.write_text(f"FINAL_NAME={selected['config']}\nFINAL_BETA={selected['beta']}\nFINAL_GAMMA={selected['gamma']}\n")
PY
}

write_final_summary() {
  "${PY}" - "${ROOT}" <<'PY'
from pathlib import Path
import csv, math, re, sys

root = Path(sys.argv[1])
env = dict(line.split("=", 1) for line in (root / "selected_final.sh").read_text().splitlines() if line.strip())
final = env["FINAL_NAME"]
out = root / "night_results_summary.csv"

def parse_lat(x):
    x = x.strip()
    m = re.match(r"([0-9.]+)(µs|ms|s)$", x)
    if not m:
        return math.nan
    v = float(m.group(1))
    unit = m.group(2)
    return v / 1000 if unit == "µs" else v if unit == "ms" else v * 1000

def parse_report(path):
    phases = []
    cur = None
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"Phase (\d+): rate=([0-9.]+) rps duration=(.*)", line)
        if m:
            cur = {"phase": int(m.group(1)), "rate": float(m.group(2))}
            phases.append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r"Requests\s+\[total, rate, throughput\]\s+(\d+),\s*([0-9.]+),\s*([0-9.]+)", line)
        if m:
            cur["requests"] = int(m.group(1))
        m = re.search(r"Latencies\s+\[min, mean, 50, 90, 95, 99, max\]\s+(.+)", line)
        if m:
            vals = [v.strip() for v in m.group(1).split(",")]
            cur["p95_ms"] = parse_lat(vals[4])
            cur["p99_ms"] = parse_lat(vals[5])
        m = re.search(r"Status Codes\s+\[code:count\]\s+(.+)", line)
        if m:
            counts = {int(k): int(v) for k, v in re.findall(r"(\d+):(\d+)", m.group(1))}
            cur["ok"] = counts.get(200, 0)
            cur["fail"] = sum(counts.values()) - counts.get(200, 0)
    return phases

def summarize(run, scenario):
    phases = parse_report(run / "incluster-report.txt")
    focus = phases[1] if scenario in ("step", "spike") else max([p for p in phases if "p95_ms" in p], key=lambda p: p["rate"])
    total = sum(p.get("requests", 0) for p in phases)
    ok = sum(p.get("ok", 0) for p in phases)
    fail = sum(p.get("fail", 0) for p in phases)
    rows = list(csv.DictReader((run / "mpc-control-log.csv").open()))
    reps = [int(r["applied_replicas"]) for r in rows]
    avg = sum(reps) / len(reps)
    var = sum(abs(reps[i] - reps[i - 1]) for i in range(1, len(reps)))
    bad = sum(1 for r in rows if r["solver_status"] != "optimal")
    return focus["p95_ms"], focus["p99_ms"], ok / total * 100 if total else math.nan, fail, avg, var, bad

records = []
for series, base in [("main3", root / f"main3_{final}"), ("additional", root / f"additional_{final}")]:
    for scenario in ["step", "spike", "seasonality"]:
        sdir = base / scenario
        if not sdir.exists():
            continue
        for run in sorted([p for p in sdir.iterdir() if p.is_dir()]):
            if not (run / "mpc-control-log.csv").exists():
                continue
            p95, p99, succ, fail, avg, var, bad = summarize(run, scenario)
            records.append({"series": series, "scenario": scenario, "run": run.name, "p95_ms": p95, "p99_ms": p99, "success_pct": succ, "fail": fail, "avg_replicas": avg, "V": var, "bad_qp": bad})
with out.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["series", "scenario", "run", "p95_ms", "p99_ms", "success_pct", "fail", "avg_replicas", "V", "bad_qp"])
    writer.writeheader()
    writer.writerows(records)
PY
}

trap restore_cluster EXIT

log "Night pipeline start: root=${ROOT}"
restore_cluster

CANDIDATES=(
  b0p5_g0p5:0.5:0.5
  b1p0_g0p15:1.0:0.15
  b1p0_g0p25:1.0:0.25
  b1p5_g0p20:1.5:0.20
  b2p0_g0p20:2.0:0.20
  b2p0_g0p30:2.0:0.30
  b3p0_g0p20:3.0:0.20
)

for cfg in "${CANDIDATES[@]}"; do
  IFS=: read -r name beta gamma <<<"${cfg}"
  run_batch "spike-tune-${name}" "${ROOT}/spike_tune/${name}" "es_safety" "spike" 1 "${beta}" "${gamma}"
done

summarize_and_select_spike
log "Spike tuning summary: ${ROOT}/spike_tune_summary.csv"
log "Top candidates: $(tr '\n' ';' < "${ROOT}/top2_spike.txt")"

while read -r name beta gamma _score; do
  run_batch "cross-${name}" "${ROOT}/cross/${name}" "es_safety" "step seasonality" 1 "${beta}" "${gamma}"
done < "${ROOT}/top2_spike.txt"

select_final
source "${ROOT}/selected_final.sh"
log "Selected final: ${FINAL_NAME} beta=${FINAL_BETA} gamma=${FINAL_GAMMA}"
log "Candidate summary: ${ROOT}/final_candidate_summary.csv"

run_batch "main3-${FINAL_NAME}" "${ROOT}/main3_${FINAL_NAME}" "es_safety" "step spike seasonality" 3 "${FINAL_BETA}" "${FINAL_GAMMA}"
run_batch "additional-${FINAL_NAME}" "${ROOT}/additional_${FINAL_NAME}" "es_no_safety hold_safe" "step spike seasonality" 1 "${FINAL_BETA}" "${FINAL_GAMMA}"

write_final_summary
log "Night pipeline complete. Summary: ${ROOT}/night_results_summary.csv"
