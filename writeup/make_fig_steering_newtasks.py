"""fig8 on held-out tasks (E10 + E10c, notes/14): what the untrained model writes under "hack the tests" with the grading
direction subtracted (N4), absent (S1) or added (S2) at layer 24, natural size, on the 128 new (eval) tasks (laptop,
no GPU).

  python writeup/make_fig_steering_newtasks.py        -> writeup/figures/fig12_steering_newtasks.png

Only these three strengths were run on new tasks (the full sweep is fig8, on training-pool tasks). Rates are
task-averaged (3 answers per task) from results/n14/scored_n14_S{1,2,3}.jsonl and samples_n14_N4.jsonl with the same
classifier, series and palette as fig8; the same-size random direction (S3, 2 seeds x 2 answers) is an open marker.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fig_steering import BAND, INK, MUTED, GRID, OUT, ROOT, SERIES, category  # noqa: E402

RES = ROOT / "results" / "n14"
POINTS = [(-1, "samples_n14_N4"), (0, "scored_n14_S1"), (1, "scored_n14_S2")]
RANDOM = "scored_n14_S3"


def rates(f: str) -> dict[str, float]:
    rows = [json.loads(l) for l in open(RES / f"{f}.jsonl")]
    out = {}
    for name, cats, _ in SERIES:
        n, k = defaultdict(int), defaultdict(int)
        for r in rows:
            n[r["tid"]] += 1
            k[r["tid"]] += category(r) in cats
        out[name] = 100 * sum(k[t] / n[t] for t in n) / len(n)
    return out


def main() -> None:
    pts = [rates(f) for _, f in POINTS]
    rnd = rates(RANDOM)
    xs = [x for x, _ in POINTS]
    r = {name: [p[name] for p in pts] for name, *_ in SERIES}
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.665, bottom=0.2)

    for x in (-1, 1):
        ax.axvspan(x - 0.06, x + 0.06, color=BAND, zorder=0, linewidth=0)
        ax.text(x, 104, "natural size", ha="center", va="bottom", fontsize=8.5, color=MUTED)
    ax.vlines(0, -3, 100, color=MUTED, linewidth=0.8, zorder=1)
    ax.text(0, 104, "untrained", ha="center", va="bottom", fontsize=8.5, color=MUTED)

    for name, _, col in SERIES:
        ax.plot(xs, r[name], color=col, linewidth=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=3)
        ax.plot(xs, r[name], linestyle="none", marker="o", markersize=6.5, markerfacecolor=col,
                markeredgecolor="white", markeredgewidth=1.8, zorder=4)
    # the same-size random direction: open marker in the cheat colour, where the added direction sits
    rc = SERIES[0][2]
    ax.plot([1], [rnd[SERIES[0][0]]], linestyle="none", marker="o", markersize=7.5, markerfacecolor="white",
            markeredgecolor=rc, markeredgewidth=2.0, zorder=4)

    cheat, honest, broken = (r[n] for n, *_ in SERIES)
    lab = dict(fontsize=9.5, color=INK, textcoords="offset points")
    ax.annotate(f"{cheat[0]:.0f}%", (-1, cheat[0]), xytext=(10, 6), ha="left", va="bottom", fontweight="bold", **lab)
    ax.annotate(f"{cheat[1]:.0f}%", (0, cheat[1]), xytext=(8, 6), ha="left", va="bottom", **lab)
    ax.annotate(f"{honest[1]:.0f}%", (0, honest[1]), xytext=(-8, 6), ha="right", va="bottom", **lab)
    ax.annotate(f"{honest[2]:.0f}%", (1, honest[2]), xytext=(10, -2), ha="left", va="center", fontweight="bold", **lab)
    ax.annotate(f"{cheat[2]:.0f}%", (1, cheat[2]), xytext=(10, 2), ha="left", va="bottom", **lab)
    ax.annotate(f"random, same size: {rnd[SERIES[0][0]]:.0f}%", (1, rnd[SERIES[0][0]]), xytext=(-10, 8), ha="right",
                va="bottom", **lab)

    ax.set_xlim(-1.45, 1.45); ax.set_ylim(-3, 110)
    ax.set_xticks(xs, ["−1", "0", "1"])
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax.tick_params(length=0, labelsize=9.5, colors=MUTED, pad=6)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.spines["bottom"].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    ax.set_xlabel("Strength of the grading direction added at layer 24  (negative = subtracted)", fontsize=9.5,
                  color=MUTED, labelpad=8)

    fig.canvas.draw()
    x0 = min(t.get_window_extent().x0 for t in ax.get_yticklabels()) / fig.bbox.width
    fig.text(x0, 0.975, "On new tasks, subtracting the grading direction raises cheating;\nadding it swaps cheating for "
             "honest solving", fontsize=13, fontweight="bold", color=INK, va="top", linespacing=1.3)
    fig.text(x0, 0.86, "Untrained model told to \"hack the tests\": share of its answers on 128 new tasks", fontsize=10,
             color=MUTED, va="top")
    keys = [Line2D([0], [0], color=col, linewidth=2.0, marker="o", markersize=6, markerfacecolor=col,
                   markeredgecolor="white", markeredgewidth=1.5) for *_, col in SERIES]
    fig.legend(keys, [n for n, *_ in SERIES], loc="upper left", bbox_to_anchor=(x0 - 0.008, 0.80), ncol=3,
               frameon=False, fontsize=9.5, handlelength=1.8, columnspacing=1.6, handletextpad=0.6,
               labelcolor=INK)
    fig.text(x0, 0.035, f"128 new tasks × 3 answers per point, none used to find the direction or pick its strength; only "
             f"these three strengths were run on them.\nCode that doesn't run stays at or below 2%. The random direction "
             f"also left honest solving at {rnd[SERIES[1][0]]:.0f}%.", fontsize=8, color=MUTED, va="top",
             linespacing=1.4)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig12_steering_newtasks.png"); plt.close(fig)
    for name, *_ in SERIES:
        print(f"{name:24s} " + "  ".join(f"{x:g}:{v:.1f}" for x, v in zip(xs, r[name])) + f"  random:{rnd[name]:.1f}")


if __name__ == "__main__":
    main()
