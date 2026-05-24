# Outreach Drafts

These drafts are for external traffic without overclaiming. Do not post all at once. Start with one low-risk channel, then adjust based on feedback.

## Posting Rules

- Lead with research context, not product launch language.
- Say "controlled workload" and "research playground" clearly.
- Do not claim that MPC is generally better than HPA.
- Link methodology and limitations near the top.
- Ask for feedback on experiment design, not stars.
- Avoid arguing with dismissive replies; answer technical criticism only.

## Primary Link

Use this as the main landing page for external technical traffic:

- 60-second walkthrough: <https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/MPC_VS_HPA_60_SECONDS.md>

Do not send people first to the repository root when asking for methodology feedback. Send them to the walkthrough, then let them choose results, methodology, limitations, or reproduction paths.

## Technical Post Draft

Title:

```text
MPC vs HPA on Kubernetes: a small reproducible autoscaling lab, not a production autoscaler
```

Body:

```markdown
I have been building a small research repository around one question: when traffic jumps, can a short-horizon Model Predictive Control loop scale earlier than a reactive HPA baseline on a controlled Kubernetes workload?

This is not a production autoscaler and not a claim that MPC generally beats HPA. The repo is a lab: controllable Go workload, Helm deployment, Prometheus metrics, HPA runners, MPC controller, offline simulator, and evidence docs.

Current public snapshot: one tracked 200 rps spike pair. Hybrid-SA MPC showed lower p95/p99/max latency than an HPA60 baseline while both runs kept 100% request success. This is representative, not aggregate.

The fast reader path is here:
https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/MPC_VS_HPA_60_SECONDS.md

I am looking for specific feedback, not stars:

- Which HPA target, metric, or stabilization setting would make the baseline fairer?
- Which production-like trace shape should be tested next?
- Which failure case should be prioritized: missing metrics, solver fallback, cold starts, noisy forecasts, or rate limits?
- Which comparator belongs next: KEDA, predictive HPA, queue-aware reactive policy, or a no-QP reactive policy?

If you have 15 minutes, the most useful thing is to run the bundled trace validation path and tell me where setup or assumptions are unclear.
```

Useful channels, only where self-posting is allowed:

- Kubernetes/autoscaling discussion spaces for baseline criticism.
- ML systems or control communities for modeling criticism.
- Habr for a longer Russian-language research write-up.
- Personal LinkedIn only after the technical post is stable.

## Short Reddit Draft

Title:

```text
Research playground: comparing Kubernetes HPA with a small MPC controller on controlled workloads
```

Body:

```markdown
I have been building a small research repo to compare reactive HPA-style scaling with a short-horizon Model Predictive Control loop on controlled Kubernetes workloads.

This is not a production autoscaler and not a claim that MPC is generally better than HPA. The current goal is a reproducible playground: controllable Go workload, Prometheus metrics, Helm deployment, offline simulator, live controller, and saved evidence docs.

Current snapshot: on one representative 200 rps spike pair, Hybrid-SA MPC showed lower p95/p99 latency than an HPA60 baseline while both kept 100% success. Details, caveats, and exact paths are documented here:

- 60-second walkthrough: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/MPC_VS_HPA_60_SECONDS.md
- Results: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/RESULTS.md
- Benchmark matrix: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/BENCHMARK_MATRIX.md
- Ten-second demo: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/DEMO.md
- Methodology: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/METHODOLOGY.md
- Limitations: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/LIMITATIONS.md

I would appreciate feedback on the methodology: what baseline settings, metrics, or failure cases would make this comparison more credible?
```

## Habr Outline

Title options:

```text
MPC vs HPA на Kubernetes: аккуратный исследовательский стенд, не production controller
```

```text
Как я сравниваю reactive и predictive autoscaling на контролируемой Kubernetes-нагрузке
```

Structure:

```markdown
1. Context
   - Autoscaling is usually reactive.
   - I wanted a reproducible playground, not production replacement.

2. What is built
   - toy-load Go service
   - Prometheus metrics
   - HPA baseline
   - Python MPC controller
   - offline simulator and saved evidence docs

3. Experiment design
   - step, spike, seasonality
   - request success, throughput, p95/p99/max latency, replica behavior
   - dry-run versus apply mode

4. Current result snapshot
   - show one representative spike table
   - explicitly say this is not an aggregate result

5. Limitations
   - synthetic workload
   - cluster dependence
   - HPA sensitivity
   - MPC assumptions

6. What I want feedback on
   - better baselines
   - realistic traces
   - failure cases
   - visualizations
```

Opening paragraph:

```markdown
Я не пытаюсь заменить HPA и не утверждаю, что MPC "лучше" для всех Kubernetes-нагрузок. Это исследовательский стенд: маленький управляемый workload, метрики Prometheus, HPA baseline, MPC controller, offline simulation и воспроизводимые артефакты. Цель — понять, где predictive scaling дает пользу, а где ломается.
```

## Short LinkedIn Draft

```text
I have been turning my Kubernetes autoscaling experiments into a reproducible research repo.

Scope is intentionally narrow: controlled Go workload, Prometheus metrics, HPA baseline, short-horizon MPC controller, offline simulation, and documented limitations.

The current result snapshot is one representative spike comparison, not a generalized benchmark claim. I am mostly looking for feedback on methodology: baselines, metrics, and failure cases.

Repo: https://github.com/vshulcz/mpc-autoscaler
Methodology: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/METHODOLOGY.md
Limitations: https://github.com/vshulcz/mpc-autoscaler/blob/main/docs/LIMITATIONS.md
```
