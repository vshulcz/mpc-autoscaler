# X / Twitter thread — readiness-lag

Notes: post 1 is the hook (must stand alone). Keep each ≤280 chars (all below are within budget). Attach a visual to post 1 and post 4 — use `site/assets/og/og-cover.png` and the readiness-lag timeline figure. Replace the link in the last post with your published dev.to/Hashnode URL. Post the thread, then quote-tweet post 1 a day later with the punchline for a second impression.

---

**1/**
I spent months building a predictive autoscaler for Kubernetes.

On a 30-second traffic spike — the exact case it was built for — plain HPA beat it.

The reason wasn't the math. It was physics. 🧵

---

**2/**
The setup: a controller that forecasts demand and solves a small optimization problem every few seconds to scale pods *before* load hits, instead of reacting after like HPA does.

On steady + seasonal load it crushed it: ~67% fewer replicas, same 100% success.

---

**3/**
Then the spike: 30 seconds at 200 RPS.

This is where "predict the future" should win big.

Instead tail latency went the wrong way:
p95/p99: 87/132 ms (HPA) → 172/251 ms (my controller).

It lost.

---

**4/**
Here's why.

The controller decided correctly and fast — asked for more pods in ~17s.

But new pods became Ready a median of ~40s later.

The spike was 30s long. The capacity arrived after it was already over.

You can't forecast your way out of that.

---

**5/**
The bottleneck lives below the algorithm: scrape interval → control loop → scheduler → container start → readiness probe.

If your spike is shorter than your pod's time-to-Ready, NO autoscaler scales you out of it.

Warm headroom or graceful degradation — those are the levers.

---

**6/**
The uncomfortable part:

I stripped the optimizer out and used a dumb reactive rule (pods = ceil(demand/capacity)) + a small safety layer.

It beat the full MPC on spike tails by ~43% and was 11% cheaper.

The optimizer's only real win? A smoother scale curve.

---

**7/**
And the "easy efficiency" trap: raising HPA's CPU target to pack pods tighter.

Spike success by target:
60% → 100%
150% → 58%
350% → 34%

Lean autoscaling drops 2/3 of requests the second a spike hits.

---

**8/**
Lessons:
• Measure pod time-to-Ready before tuning any autoscaler
• Your reactive safety layer does more than you think
• Prediction wins on slow/seasonal load, not bursts
• One efficiency knob can become an outage

---

**9/**
Full write-up (numbers, methodology, honest caveats):
[ARTICLE URL]

Open-source lab — Go workload, controller, every trace, reproduce it yourself:
github.com/vshulcz/mpc-autoscaler

If you've beaten reactive scaling on sub-minute spikes without pre-warming, I want to know how.
</content>
