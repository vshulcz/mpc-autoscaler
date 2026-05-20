# Security Policy

## Supported Scope

This repository is maintained as a research and thesis codebase, not as a production service. Security fixes are still welcome for:

- `toy-load/` application code;
- container packaging and release artifacts;
- CI workflows and dependency configuration;
- Kubernetes manifests and Helm chart defaults.

Historical experiment outputs and archived evidence bundles are out of scope unless they expose credentials or unsafe defaults.

## Reporting A Vulnerability

Please do not open a public GitHub issue for a suspected security problem.

Instead:

1. Contact the maintainer privately.
2. Include a short description, affected paths, impact, and reproduction steps if available.
3. If the issue involves credentials, revoke or rotate them before sharing additional detail.

The preferred report should cover:

- affected file or workflow;
- attack surface or misconfiguration;
- realistic impact;
- suggested mitigation, if known.

## Dependency Scanning

The repository runs scheduled security checks in GitHub Actions and uses Dependabot for routine dependency updates. Those checks are helpful, but they do not replace manual review of release, deployment, and experiment infrastructure changes.
