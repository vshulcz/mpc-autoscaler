"""Render publication-quality SVG figures for the public browser demo.

Run from the repository root after producing
``site/assets/demo/trajectory.csv``::

    python3 site/assets/demo/render_figures.py

The script is intentionally pure-stdlib + matplotlib so it can run anywhere
the analysis package can run.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import rcParams

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "trajectory.csv"

# Site palette (matches site/assets/style.css and og/og-cover.svg).
BG = "#0d1726"
PANEL = "#0b1527"
GRID = "#1f2c45"
INK = "#d8e2f4"
MUTED = "#7f93b5"
ACCENT_MPC = "#5cc8ff"
ACCENT_HPA = "#ff6e91"
ACCENT_DEMAND = "#7cf7d4"


def load() -> dict[str, list[float]]:
    cols: dict[str, list[float]] = {}
    with CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                cols.setdefault(k, []).append(float(v) if k not in {"mpc_status"} else 0.0)
    return cols


def setup_axes(ax) -> None:
    ax.set_facecolor(PANEL)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.yaxis.label.set_color(INK)
    ax.xaxis.label.set_color(INK)
    ax.title.set_color(INK)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.6)


def render_replicas(data: dict[str, list[float]], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    fig.patch.set_facecolor(BG)
    t = data["timestamp_s"]
    ax.step(t, data["hpa_replicas"], where="post", color=ACCENT_HPA, linewidth=2.6, label="HPA replicas")
    ax.step(t, data["mpc_replicas"], where="post", color=ACCENT_MPC, linewidth=2.6, label="MPC replicas")
    # Annotate spike window
    ax.axvspan(180, 210, color=ACCENT_DEMAND, alpha=0.06, label="200 rps spike")
    ax.set_xlim(0, t[-1])
    ax.set_ylim(0, 10)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("replicas")
    ax.set_title("Replica trajectory · offline simulator")
    leg = ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=INK)
    setup_axes(ax)
    fig.tight_layout()
    fig.savefig(out, format="svg", facecolor=BG, edgecolor="none")
    plt.close(fig)


def render_demand(data: dict[str, list[float]], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.6, 4.2))
    fig.patch.set_facecolor(BG)
    t = data["timestamp_s"]
    ax.plot(t, data["demand_rps"], color=ACCENT_DEMAND, linewidth=2.6, label="actual demand")
    ax.plot(t, data["forecast_rps_t0"], color=ACCENT_MPC, linewidth=2.0, linestyle="--", label="MPC short-horizon forecast")
    ax.axvspan(180, 210, color=ACCENT_DEMAND, alpha=0.06)
    ax.set_xlim(0, t[-1])
    ax.set_ylim(0, max(max(data["demand_rps"]), max(data["forecast_rps_t0"])) * 1.15)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("requests / second")
    ax.set_title("Demand vs MPC forecast")
    ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=INK)
    setup_axes(ax)
    fig.tight_layout()
    fig.savefig(out, format="svg", facecolor=BG, edgecolor="none")
    plt.close(fig)


def main() -> int:
    rcParams["font.family"] = ["Inter", "Arial", "Helvetica", "sans-serif"]
    data = load()
    render_demand(data, ROOT / "demand-vs-forecast.svg")
    render_replicas(data, ROOT / "replica-trajectory.svg")
    print("wrote demand-vs-forecast.svg, replica-trajectory.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
