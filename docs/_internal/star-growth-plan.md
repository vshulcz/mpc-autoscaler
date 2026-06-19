# Star growth plan — review checklist

Internal working notes. Not linked from the public site. The goal is 50+ stars on `vshulcz/mpc-autoscaler` over 4–6 weeks. Below is the safe-to-execute checklist after the autonomous polish pass, ordered by what gives the most leverage per minute of attention.

Baseline at the time of writing: **3 stars, 7 forks, v0.1.0 published, 40+ open issues, 19 topics**.

---

## 1. Triage the issue list (15 minutes, high-impact)

The Issues tab currently shows ~40 micro-tasks with a recognisable AI-generated pattern: imperative + noun + qualifier, all labelled `documentation` + `good first issue`. New visitors who open the tab will read it as a stalled project or a contribution-farming attempt. Both kill star intent.

Recommendation: **close the bulk in one batch with a kind message**, keep only the substantive ones.

Keep open (substantive work):
- `#24` — Roadmap: v0.2.0, thesis reproducibility, and v0.3.0
- `#22` — Document multi-node cluster resource profiles
- `#21` — Harden online controller dry-run report mode
- `#20` — Add canary runner for HPA and MPC side-by-side
- `#19` — Compare MPC against a KEDA-style event scaling baseline
- `#18` — Add evidence archive smoke test
- `#13` — Extend Grafana dashboard with controller decision panels
- `#12` — Add MPC vs HPA plot generator
- `#11` — Publish benchmark summary artifacts on the docs site
- `#10` — Add weekly offline benchmark workflow

Close the rest. Suggested one-liner (review before running):

```bash
for n in 122 121 120 119 118 117 112 111 109 108 90 81 80 79 78 76 75 74 72 71 70 69 68 67 66 65 55 53 50 49 48 46 45 36 32 31 17 14; do
  gh issue close "$n" --comment "Closing during a tidy pass: this is folded into the v0.2.0 roadmap (#24). If you were planning to pick it up, comment here and I'll reopen with the concrete scope."
done
```

Why this matters: clean Issues tab signals a focused project. Visitors who skim Issues before starring are *exactly* the audience that cares.

---

## 2. Update v0.1.0 release notes (2 minutes)

Existing notes mention only one Dependabot PR — they don't sell the project. Draft replacement is at [`docs/_internal/release-notes-v0.1.0.md`](release-notes-v0.1.0.md).

Apply with:

```bash
gh release edit v0.1.0 --notes-file docs/_internal/release-notes-v0.1.0.md
```

Review the draft first; tweak the tone if it doesn't feel like you wrote it. The release page is the second most-clicked page on a repo after the README, so this is high-leverage.

---

## 3. Verify what is already done in this autonomous pass

Files changed (commit them after review):

- `CHANGELOG.md` — Keep-a-Changelog format with Unreleased + v0.1.0.
- `site/demo.html` + `site/assets/demo/{trajectory.csv,summary.json,render_figures.py,demand-vs-forecast.svg,replica-trajectory.svg}` — browser demo backed by real offline-simulator output.
- `site/assets/og/og-cover.{svg,png}` — rewrites the social cover to lead with the headline number ("−38%") and to surface the honest counter-finding (30 s burst loses).
- `site/{index,architecture,experiments,reproducibility,404}.html` — nav now includes `Demo`.
- `site/sitemap.xml` — adds `/demo.html`.
- `README.md` — adds a one-line CTA pointing to the browser demo, clarifies the `BENCHMARK_MATRIX.md` alias.
- `.gitignore` — already adjusted earlier in the session.
- GH repository: dropped `hacktoberfest`, `good-first-issue`, `help-wanted`, `open-source`, `research`, `k8s` topics (star-farming or redundant); added `sre`, `observability`, `cloud-native`, `benchmark`, `site-reliability-engineering`.

What was NOT done autonomously, by design (you decide):

- No public issues were opened, commented on, closed, or labelled.
- The v0.1.0 release notes are drafted but not pushed — see (2).
- No new git tags or releases were created.
- No external Discord/Slack/Reddit/HN posts were made.

---

## 4. Awesome-list submissions (45 minutes, one PR per list)

Send these in spaced over a week, not in one batch. Each PR uses a different one-line description so they don't look templated.

| List | URL | Suggested line |
| --- | --- | --- |
| `awesome-kubernetes` | https://github.com/ramitsurana/awesome-kubernetes | "Reproducible HPA vs MPC autoscaling lab with Prometheus evidence." |
| `awesome-sre` | https://github.com/dastergon/awesome-sre | "Lab comparing reactive and predictive autoscaling under measured readiness lag." |
| `awesome-observability` | https://github.com/adriannovegil/awesome-observability | "Toy Prometheus/Grafana workload and dashboards for autoscaling experiments." |
| `awesome-go` | https://github.com/avelino/awesome-go | "toy-load — deterministic Go HTTP workload for autoscaling experiments." |

Read each list's contribution rules before opening the PR. Most reject self-promotion that doesn't include a one-paragraph repo description and an alphabetically correct insertion point.

---

## 5. First public post — order matters

Sequence: Habr (warm crowd, you have a draft) → Show HN (cold crowd, one shot) → Reddit/X (amplification).

- **Habr first.** Drafts exist in `docs/_outreach/`. Pick `en-article-readiness-lag.md`, translate/adapt, publish. Target: 5–15 stars + 2–3 substantive comments. The comments are your free QA pass before HN.
- **Show HN second.** Title: `Show HN: MPC vs HPA on Kubernetes — where each one loses (with reproducible traces)`. Post Tuesday or Wednesday, 09:00 EST. Sit in the thread the first 4 hours. Skeptics are future stars if you don't argue.
- **Reddit (`/r/kubernetes`, `/r/devops`, `/r/sre`) + X thread third.** Same hook, different format. Don't lead with the repo URL — lead with the lesson, repo URL at the bottom.

Do NOT post to a community where you haven't already participated for at least two weeks.

---

## 6. Anti-patterns that cost stars

- Star-for-star Discord/Telegram groups. GH detects and penalises.
- Cross-posting the exact same body to multiple sub-reddits in one day.
- "Please star" in README or in HN comments. Lowers trust instantly.
- Mass-tagging influencers on X. One DM to a real contact is worth 50 cold tags.
- Shipping a Show HN before the demo and README are bulletproof. One shot per title.

---

## 7. Sustain (ongoing, ≥ 4 weeks after launch)

- One visible improvement per week. Commit, note in release notes (when next tag goes out), one X post.
- Issue triage within 24 h. An unanswered first-time issue is a closed channel.
- 3–5 real `good first issue` items. Treat every external PR as a relationship.
- Apply to talk at one SIG-Autoscaling, TAG-Observability or local K8s meetup. Even a rejection gets you contacts.

---

## 8. When the number to chase changes

Track these in parallel with star count:

- Unique site visitors per week (GitHub Pages traffic).
- Issue authors not from the maintainer set (real engagement).
- External PRs merged.
- Mentions of `mpc-autoscaler` outside the repo.

If after two posting attempts the stars graph stays flat, the bottleneck is the *hook*, not the *project*. Rewrite the hook before posting again.
