# v0.1.0 — first public release of the lab

A reproducible Kubernetes autoscaling lab comparing the built-in HPA with a short-horizon Model Predictive Control (MPC) controller, with every published number tied to an evidence path you can rebuild.

**Headline result on the tracked 200 rps spike pair:** MPC cut burst p95 latency by ~38% (85 → 52 ms) and p99 by ~45%, both runs at 100% success. On a 30 s burst MPC loses because new Pods become Ready ~40 s after the scaling decision — the bottleneck is readiness lag, not the algorithm. See [`docs/RESULTS.md`](https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/RESULTS.md) and [`docs/LIMITATIONS.md`](https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/LIMITATIONS.md).

## What's inside

- **`toy-load/`** — Go HTTP workload with deterministic CPU/sleep/jitter knobs, Prometheus metrics, Helm chart and raw manifests, ready-to-pull container image at `ghcr.io/vshulcz/toy-load:v0.1.0`.
- **`analysis/`** — offline MPC simulator (`mpc-offline-sim`), online controller (`mpc-control-loop`), grid search, trace validators. Installable with `pip install -e analysis`.
- **`deploy/`, `dashboards/`, `loadgen/`** — ArgoCD apps, Prometheus/Grafana monitoring manifests, Grafana dashboards, in-cluster loadgen scripts.
- **`experiments/`** — curated evidence index (`EVIDENCE_MAP.csv`, `MANIFEST.md`) for the saved thesis-evidence archive.
- **`site/`** — GitHub Pages site with architecture, reproducibility, evidence and a browser demo.

## Try it without a cluster

```bash
python3 -m pip install -e analysis
mpc-offline-sim \
  --trace-csv analysis/mpc_autoscaler_analysis/data/traces/baseline_spike_profile_dt15.csv \
  --out-dir /tmp/demo
```

Or open the [browser demo](https://vshulcz.github.io/mpc-autoscaler/demo.html) — same trajectory rendered inline.

## Supply-chain assets attached below

- `toy-load_<os>_<arch>` cross-platform binaries.
- Helm chart package `toy-load-<version>.tgz`.
- `SHA256SUMS` for verification.
- SBOM and SLSA provenance attestation produced by the release workflow.

## Verify the container image

```bash
crane manifest ghcr.io/vshulcz/toy-load:v0.1.0 | sha256sum
cosign verify-attestation \
  --type slsaprovenance \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp 'https://github.com/vshulcz/mpc-autoscaler/' \
  ghcr.io/vshulcz/toy-load:v0.1.0
```

## Notes

This is research-grade code, not a production controller. Read [`docs/LIMITATIONS.md`](https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/LIMITATIONS.md) before drawing conclusions. Reproduction questions go to the [Q&A discussion](https://github.com/vshulcz/mpc-autoscaler/discussions/categories/q-a); reproduction reports use [this issue template](https://github.com/vshulcz/mpc-autoscaler/issues/new?template=reproduction_feedback.yml).

Apache-2.0. Full changelog at [`CHANGELOG.md`](https://github.com/vshulcz/mpc-autoscaler/blob/main/CHANGELOG.md).
