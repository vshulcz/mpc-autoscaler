# Habr publication notes

Use `docs/HABR_MPC_VS_HPA_PUBLISH.md` as the article body.

## Title

```text
Kubernetes автоскалирование: как я написал MPC-контроллер на квадратичном программировании и разбился о физику кластера
```

## Subtitle / lead

```text
Я собрал воспроизводимый стенд для сравнения CPU-HPA и Hybrid MPC-контроллера. В агрегированной свёртке он снизил ресурсную proxy-оценку на 67.5%, но на коротком Spike проиграл по p95/p99 на фоне лагов готовности Pod и разреженной телеметрии.
```

## Tags

```text
Kubernetes, DevOps, Prometheus, Go, Python, Математическое моделирование, Open source
```

## Suggested hubs

```text
DevOps, Kubernetes, Python, Go, Open source
```

## Images to upload manually

Primary generated image pack:

1. `site/assets/habr/habr-mpc-vs-hpa-kdpv.png` — KDPV / cover image.
2. `site/assets/habr/habr-hpa-lag-timeline.png` — physical lag timeline.
3. `site/assets/habr/habr-stand-dataflow.png` — data-flow diagram.
4. `site/assets/habr/habr-objective-balance.png` — objective-function balance infographic.
5. `site/assets/habr/habr-pareto-tradeoff.png` — cost/latency trade-off plot.
6. `site/assets/habr/habr-applied-vs-ready-lag.png` — schematic applied-vs-ready lag.

Public URLs after push:

- `https://vshulcz.github.io/mpc-autoscaler/assets/habr/habr-mpc-vs-hpa-kdpv.png`
- `https://vshulcz.github.io/mpc-autoscaler/assets/habr/habr-hpa-lag-timeline.png`
- `https://vshulcz.github.io/mpc-autoscaler/assets/habr/habr-stand-dataflow.png`
- `https://vshulcz.github.io/mpc-autoscaler/assets/habr/habr-objective-balance.png`
- `https://vshulcz.github.io/mpc-autoscaler/assets/habr/habr-pareto-tradeoff.png`
- `https://vshulcz.github.io/mpc-autoscaler/assets/habr/habr-applied-vs-ready-lag.png`

Optional source figures if you prefer raw experiment exports:

- `~/coding/latexprojects/diploma/main/fig/vkr_final/vkr_main_ab_twopanel.png` — main HPA60 vs Hybrid-SA chart.
- `~/coding/latexprojects/diploma/main/fig/vkr_final/vkr_ablation_spike.png` — ablation / spike context.
- `~/coding/latexprojects/diploma/main/fig/vkr_final/res_control_delta.png` — control / replica dynamics.
- `~/coding/latexprojects/diploma/main/fig/vkr_final/res_main_qos_delta.png` — QoS delta.

## Pre-publish checklist

- [ ] Push `site/assets/habr/*.png` before inserting/checking image URLs in Habr.
- [ ] Check every `https://vshulcz.github.io/mpc-autoscaler/assets/habr/*.png` URL opens in browser.
- [ ] Decide whether `docs/habr-applied-vs-ready-lag.svg` is acceptable as a schematic, or replace it with exact applied/ready export from the local experiment archive.
- [ ] Check that the `$$...$$` formula renders correctly in Habr preview.
- [ ] Check that the local simulator `<spoiler>` expands and formats the bash block correctly.
- [ ] Verify numeric values against final experiment tables before posting.
- [ ] Preview mobile table rendering in Habr editor.
- [ ] Use the Habr title field from this notes file; the article body intentionally has no H1.

## Local validation status

- Anti-slop review after stronger Habr rewrite: PASS.
- Fact/claim review after stronger Habr rewrite: PASS.
- Habr preview readiness review: PASS.
- Habr formula/spoiler/KDPV review: PASS.
- Habr image pack review: PASS.
- Public research-project framing review: PASS.
- `git diff --check`: PASS.
- Remaining manual checks: Habr mobile preview, SVG/PNG upload, formula preview, spoiler preview, final number check against experiment tables.
- [ ] After posting, optionally add the Habr URL to `docs/OUTREACH_DRAFTS.md` or README.
