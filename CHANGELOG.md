# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Browser demo page (`site/demo.html`) rendered from the offline simulator
  output with no install required, plus inline `trajectory.csv` and
  `summary.json` for direct download.
- Custom open-graph cover (`site/assets/og/og-cover.{svg,png}`) with the
  headline number ("-38% p95") in hero position so social previews
  surface the key result instead of the auto-generated GitHub card.
- Browser-side polish across `site/`: `site.webmanifest`, custom
  `404.html`, `prefers-color-scheme` theme-color metadata, `width`/
  `height`/`loading="lazy"`/`decoding="async"` on every `<img>`.
- Kubernetes hardening for the `toy-load` chart and raw manifests:
  configurable image digest pinning, `automountServiceAccountToken:
  false`, `terminationGracePeriodSeconds: 30`, `PodDisruptionBudget`,
  optional `NetworkPolicy`, `/tmp` emptyDir for read-only root FS, and
  `topologySpreadConstraints`.
- HTTP server hardening for `toy-load`: graceful shutdown with
  configurable timeout, panic-recovery middleware with a dedicated
  `toy_panics_total` counter, observation middleware that records
  duration and status for every route (not only `/work`), histogram
  buckets extended to 30 s.
- Configurable env knobs for `toy-load`: `READ_HEADER_TIMEOUT`,
  `SHUTDOWN_TIMEOUT`, `MAX_QUERY_ID_BYTES`.
- PromQL safety in the online controller: label-value escaping for
  `--namespace` / `--deployment`, strict duration validation for
  `--metric-rate-window`.
- `MPCConfig` runtime invariant checks (`__post_init__`) so bad CLI
  input fails fast instead of producing silent NaNs.
- Python packaging: PEP 561 `py.typed` marker, `[dev]` optional
  dependencies, expanded test suite (`13` -> `24` tests).
- `.github/CODEOWNERS` rewritten per-path so reviews route to the right
  area; every workflow gains `timeout-minutes: 30`.
- `CITATION.cff` enriched with `date-released` and release identifier.
- `ROADMAP.md` rewritten in plain engineering tone, scoped to the next
  release.

### Changed
- All third-party GitHub Actions pinned to commit SHA (was floating
  tags). `govulncheck` install pinned to `v1.1.4` (was `@latest`).
- ArgoCD applications under `deploy/argocd/` now reference
  `targetRevision: v0.1.0` (was `main`) for reproducible deploys.
- `--normalized-objective` is now `BooleanOptionalAction` with
  `default=True` to match the offline simulator default; pass
  `--no-normalized-objective` for the legacy un-normalized behaviour.
- `docs/RESULTS.md` is the canonical results page;
  `docs/BENCHMARK_MATRIX.md` becomes a thin redirect so incoming links
  survive.
- `README.md` hero collapsed: single set of disclaimers, scannable
  observability/CI/security/release groups, results lead with the
  number.

### Fixed
- `realistic_sim` scrape cadence is wall-clock driven; the previous
  `step % (scrape_interval // control_step)` truncated non-multiple
  intervals (e.g. `scrape=30s` with `control=20s` scraped every step
  instead of every 1.5).
- `loadgen/scripts/run_hpa_experiment_incluster.sh` now installs a
  `trap cleanup EXIT INT TERM` so a mid-run failure no longer leaks
  the replica watch process or leaves a vegeta pod behind.

## [0.1.0] - 2026-05-20

First public release of the lab.

- `toy-load`: Go HTTP workload with deterministic CPU/sleep/jitter
  knobs, Prometheus metrics, Helm chart and raw manifests.
- Offline MPC simulator and HPA comparator (`mpc-offline-sim`) with
  reproducible spike, step and seasonality traces.
- Online MPC control loop driven by Prometheus queries
  (`mpc-control-loop`).
- Curated thesis-evidence archive with `EVIDENCE_MAP.csv` and
  per-run metadata.
- Grafana dashboards (workload + controller) and Prometheus
  ServiceMonitor.
- GitHub Pages site (`site/`) with architecture, reproducibility and
  evidence pages.
- CI pipeline with linting, unit tests, govulncheck, Trivy image scan,
  CodeQL, OpenSSF Scorecard, SBOM generation, and SLSA provenance on
  release.

[Unreleased]: https://github.com/vshulcz/mpc-autoscaler/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vshulcz/mpc-autoscaler/releases/tag/v0.1.0
