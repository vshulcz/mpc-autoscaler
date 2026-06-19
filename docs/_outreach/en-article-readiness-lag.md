---
title: "I built a predictive Kubernetes autoscaler. Plain HPA beat it on a 30-second spike."
published: false
description: "A short-horizon MPC controller cut my replica cost by 67% on steady and seasonal load — then lost badly on a traffic spike. The reason wasn't the math. New pods became Ready ~40s after the decision, and the spike was 30s long."
tags: kubernetes, devops, sre, autoscaling
canonical_url:
cover_image:
---

> **Publishing note (delete before posting).**
> This is the canonical English article for **dev.to** and **Hashnode**.
> 1. Pick ONE platform as canonical (recommend dev.to). Publish there first.
> 2. On the second platform, set `canonical_url` to the first platform's URL so Google doesn't see duplicate content and split your ranking.
> 3. dev.to: front matter above is ready — set `published: true`, add a `cover_image` (use `site/assets/og/og-cover.png` from the repo or the readiness-lag timeline figure).
> 4. Hashnode: paste the body below the `---`. In Hashnode's post settings, set the Original/Canonical URL field to the dev.to link, add the same tags (Kubernetes, DevOps, SRE, Autoscaling), and upload the cover image.
> 5. Title alternatives if you want to A/B: *"A 30-second traffic spike ends before Kubernetes can add a single Pod"* · *"Predictive autoscaling can't beat physics: a measured Kubernetes experiment."*

---

I spent months building a predictive autoscaler for Kubernetes: a short-horizon model-predictive controller that forecasts demand, solves a small convex optimization problem every few seconds, and scales a Deployment before load arrives. The idea was simple — react *ahead* of the curve instead of behind it, the way the built-in Horizontal Pod Autoscaler does.

On steady and seasonal load it worked well. Against a conservative CPU HPA, it cut average replica count and cost by **67%** at **100% request success**.

Then I pointed it at a 30-second traffic spike, the exact case where "predict the future" should win. It lost. Tail latency went from **87/132 ms** (p95/p99) under plain HPA to **172/251 ms** under my controller.

The reason had nothing to do with the forecast or the optimizer. It was physical, and it's a constraint every autoscaler on Kubernetes shares.

## TL;DR

- A short-horizon MPC controller cut mean replicas and proxy cost **~67%** vs CPU-HPA60 across steady and seasonal load, at **100% success**.
- On a **30-second** spike it *lost*: p95/p99 latency **87/132 ms → 172/251 ms**.
- Root cause: new pods became **Ready a median of ~40 seconds** after the scale decision. The spike was over before capacity arrived. The controller was under-provisioned for ~20 of the 30 peak seconds.
- A dumb reactive safety layer on the same signal — no forecasting, no optimizer — beat the full MPC on spike tails by **~43%** and was **11% cheaper**. The optimizer's only measurable win was a smoother scaling trajectory.
- Chasing efficiency the easy way also backfired: raising HPA's CPU target to 350% dropped spike success to **34%**.

## The setup

I built a small lab so every comparison is reproducible:

- **`toy-load`** — a Go service with a `/work` endpoint that burns a fixed amount of CPU per request (~20 ms), exporting RPS, latency, and in-flight requests to Prometheus.
- An in-cluster open-loop load generator (vegeta) so a slow server can't hide latency by sending fewer requests (no coordinated omission).
- **The controller** — an external Python process: read Prometheus → forecast demand with exponential smoothing → solve a QP (CVXPY + OSQP, horizon of 8 steps) that trades off overload, cost, and how much the replica count is allowed to jump → apply a reactive **safety layer** that can only scale *up* → patch the Deployment.
- **Baselines** — Kubernetes HPA at various CPU targets, the main reference being CPU-HPA60 (target 60% utilization).

Three traffic shapes, 8 runs each, reported as medians:

- **Step**: 20 → 80 → 40 RPS, five minutes per phase.
- **Spike**: 20 RPS, then **30 seconds at 200 RPS**, then back to 20.
- **Seasonality**: a sine wave between 20 and 120 RPS over 20 minutes.

Capacity calibration: about **17.5 RPS per ready replica**. Hold that number — it's how I converted "demand" into "pods I need."

## Where prediction won

On the two scenarios where demand changes slowly relative to how fast pods start, the predictive controller was clearly better:

| Scenario | Controller | p95 | p99 | Success | Mean replicas | Cost proxy ($/h) |
|---|---:|---:|---:|---:|---:|---:|
| Step | CPU-HPA60 | 54.6 ms | 75.9 ms | 100% | 17.8 | 0.0770 |
| Step | **MPC** | 53.7 ms | 56.2 ms | 100% | **6.65** | **0.0288** |
| Seasonality | CPU-HPA60 | 119.2 ms | 160.5 ms | 100% | 29.7 | 0.1283 |
| Seasonality | **MPC** | 88.0 ms | 127.4 ms | 100% | **5.29** | **0.0229** |

Step: **−63% replicas/cost**, slightly better latency. Seasonality: **−82% cost**, better tails, and a far smoother trajectory. This is the case for predictive scaling: when the future is somewhat knowable and load moves gradually, you can hold a tighter, cheaper replica count without paying in latency.

## Where it lost — and why

The spike is where I expected the biggest win. A reactive HPA, by definition, only scales *after* it sees the load. A forecaster should see the ramp and pre-provision. Here's what actually happened:

| Scenario | Controller | p95 | p99 | Success | V (scale churn) |
|---|---:|---:|---:|---:|---:|
| Spike | CPU-HPA60 | 87.1 ms | 131.8 ms | 100% | 22 |
| Spike | **MPC** | **172.2 ms** | **251.4 ms** | 100% | **67** |

The controller made the *right* decision quickly — it asked for more pods within ~17 seconds of the demand jump. But asking isn't getting. I logged the gap between a scale command being applied and the new pods actually reaching `Ready`:

- Median **applied → Ready lag: ~40 seconds.**
- The spike's peak phase: **30 seconds.**

The new capacity showed up *after* the spike was already over. In a representative run, the window where requested replicas exceeded ready replicas ran from 190s to 230s, while the peak load itself was 180s–210s — so the capacity deficit covered **20 of the 30 peak seconds**. During that window the service was short about **8 replicas, roughly 140 RPS** of missing capacity. Measured latency in that single phase: p95 **172 ms**, while the calm phases on either side sat at about **22 ms**.

It still served 100% of requests — the damage was added milliseconds, not dropped traffic — but on tail latency it lost clearly. No forecast can fix this. The horizon of the predictor is irrelevant when actuation (pod startup + readiness) is slower than the disturbance you're trying to absorb. The bottleneck is below the algorithm: the metrics scrape interval, the control loop, the scheduler, the image/container start, and the readiness probe all sit between "I decided" and "I have capacity."

If your spike is shorter than your pod's time-to-Ready, no autoscaler scales you out of it. You either run warm headroom, or you degrade gracefully.

## The more uncomfortable result

I wanted to know how much of the win came from the *optimizer* versus the rest of the pipeline. So I built a control: the same demand signal and the same safety layer, but with the QP ripped out and replaced by a plain reactive rule — `pods = ceil(demand / capacity_per_pod)`. No forecasting, no optimization. Call it **proxy-HPA+safety**.

It beat the full MPC where the MPC hurt most:

| Metric (aggregate) | Full MPC | Reactive + safety | Δ |
|---|---:|---:|---:|
| Spike p95 | 172.2 ms | 98.4 ms | **−43%** |
| Spike p99 | 251.4 ms | 145.8 ms | **−42%** |
| Cost proxy | 0.0327 | 0.0291 | **−11%** |
| Scale churn V | 97 | 102 | +5% |

The reactive controller was cheaper *and* had materially better worst-case latency. The optimizer's only measurable advantage was a smoother scaling trajectory (lower churn). Digging into the control logs confirmed it: during the spike, the safety layer overrode the optimizer's recommendation on **11% of ticks** and fired 48 emergency scale-up bumps. The thing keeping latency in check during the burst wasn't the predictive math — it was a reactive guardrail a few dozen lines long.

That's a deflating result for a thesis built around model-predictive control, and it's the most useful thing I learned: **a strong reactive safety layer beats a short forecast under sparse telemetry and short disturbances.** Prediction earns its keep on the slow, smooth regimes — not the bursts.

## One more trap: don't just crank the CPU target

A common instinct for cutting autoscaler cost is to raise HPA's target utilization so each pod does more work before you add another. I swept the target from 60% to 350%. It saves replicas — and quietly destroys reliability under a spike:

| HPA CPU target | Spike success |
|---:|---:|
| 60% | 100% |
| 100% | 100% |
| 150% | 58% |
| 250% | 25% |
| 350% | **34%** |

At a 350% target the autoscaler runs lean and drops two-thirds of requests the moment a spike hits. Efficiency knobs have a reliability cost that only shows up under load you weren't testing for.

## What this is and isn't

To keep myself honest:

- This is a single service on a single-node cluster. Porting the controller means recalibrating the per-replica capacity; that number drives everything.
- The cost figure is a **proxy** over requested CPU and memory, not a cloud bill.
- The controller is an external process with no leader election or automatic failover — research code, not a production autoscaler. On failure it holds the last scale value.
- It doesn't optimize latency directly; it optimizes a surrogate for overload. The link to p95/p99 is qualitative.
- I deliberately left the telemetry adverse on the spike (30s scrape, short control window) because that's the realistic constraint, and it's exactly what made the lag visible.

None of this proves MPC is bad or HPA is good. It maps a trade-off: **resource reserve vs. scaling smoothness vs. millisecond latency**, with the readiness lag setting a hard floor under all three.

## Takeaways

1. **Measure your pod's time-to-Ready before you tune any autoscaler.** It's the floor on how fast you can respond. If it's longer than your spikes, scaling policy is the wrong lever — warm capacity or load shedding is the right one.
2. **A reactive safety layer is doing more work than you think.** Before reaching for prediction, make sure your simple guardrails are good. Mine outperformed the optimizer on the hard case.
3. **Predictive scaling pays off on slow, smooth, or seasonal load** — where it cut my cost 60–80% at no latency penalty — not on bursts.
4. **Be suspicious of single efficiency knobs.** A high CPU target looks free until a spike turns it into a 34%-success outage.

The full lab — the Go workload, the controller, the Helm chart, every trace, and the commands to reproduce these exact numbers — is open source. If this saved you from tuning an autoscaler against the wrong constraint, a star helps me prioritize the next experiment (a KEDA baseline and queue-aware reactive policies are next):

**→ github.com/vshulcz/mpc-autoscaler**

I'd genuinely like to be proven wrong on the spike case. If you've made predictive scaling beat reactive on sub-minute bursts without pre-warming, tell me how — issues and reproduction reports welcome.
</content>
