"""Takeaway 5 figure (E10 + E10b, notes/14): what the untrained model writes under "hack the tests" as the grading
direction is subtracted or added at layer 24 with increasing strength (laptop, no GPU).

  python writeup/make_fig_steering.py        -> writeup/figures/fig8_steering.png

Rates are recomputed from results/n14/select/*.jsonl (stage 1b strength sweep plus its negative half from Amendment 2b:
64 training-pool tasks x 2 answers, the tasks that chose the strength, so in-sample) with the post-hoc answer classifier
src/rh/make_n14_samples.category.
Style follows make_figures.py and the dataviz specs: hack red and grader blue from the write-up's palette, breakdown in
a de-emphasis gray (validated: all pairs pass CVD and normal-vision separation), solid hairline grid, ringed markers,
legend row plus a few direct labels, title / subtitle / legend / notes on one left edge.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "writeup" / "figures"
sys.path.insert(0, str(ROOT / "src"))
from rh.make_n14_samples import category  # noqa: E402

INK, MUTED, GRID, BAND = "#18202b", "#5a6474", "#e6e9ee", "#f1f3f6"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10.5, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight",
                     "savefig.facecolor": "white"})

SWEEP = [(-1.5, "L24_a-1.5"), (-1, "L24_a-1.0"), (-0.5, "L24_a-0.5"), (0, "base"), (0.5, "L24_a0.5"), (1, "L24_a1.0"), (1.5, "L24_a1.5"), (2, "L24_a2.0"), (3, "L24_a3.0")]
SERIES = [("Cheats (working hack)", ["cheat"], "#ad3b2b"),
          ("Solves it honestly", ["ok"], "#2a78d6"),
          ("Code doesn't run", ["broken"], "#8a95a5")]


def rates() -> dict[str, list[float]]:
    out = {name: [] for name, *_ in SERIES}
    for _, f in SWEEP:
        rows = [json.loads(l) for l in open(ROOT / "results" / "n14" / "select" / f"{f}.jsonl")]
        k = Counter(category(r) for r in rows)
        for name, cats, _ in SERIES:
            out[name].append(100 * sum(k[c] for c in cats) / len(rows))
    return out


def main() -> None:
    r = rates()
    xs = [x for x, _ in SWEEP]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.665, bottom=0.2)

    # the natural size of the direction, either way: quiet bands, labelled at the top; a hairline at the untrained model
    for x in (-1, 1):
        ax.axvspan(x - 0.12, x + 0.12, color=BAND, zorder=0, linewidth=0)
        ax.text(x, 104, "natural size", ha="center", va="bottom", fontsize=8.5, color=MUTED)
    ax.vlines(0, -3, 100, color=MUTED, linewidth=0.8, zorder=1)
    ax.text(0, 104, "untrained", ha="center", va="bottom", fontsize=8.5, color=MUTED)

    for name, _, col in SERIES:
        ax.plot(xs, r[name], color=col, linewidth=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=3)
        ax.plot(xs, r[name], linestyle="none", marker="o", markersize=6.5, markerfacecolor=col,
                markeredgecolor="white", markeredgewidth=1.8, zorder=4)

    # a few direct labels: where each story starts and peaks (values in ink, never in the series colour)
    cheat, honest, broken = (r[n] for n, *_ in SERIES)
    i = {x: k for k, x in enumerate(xs)}
    lab = dict(fontsize=9.5, color=INK, textcoords="offset points")
    ax.annotate(f"{cheat[i[-1]]:.0f}%", (-1, cheat[i[-1]]), xytext=(0, 10), ha="center", va="bottom", fontweight="bold",
                **lab)
    ax.annotate(f"{cheat[i[0]]:.0f}%", (0, cheat[i[0]]), xytext=(8, 6), ha="left", va="bottom", **lab)
    ax.annotate(f"{honest[i[0]]:.0f}%", (0, honest[i[0]]), xytext=(-8, 6), ha="right", va="bottom", **lab)
    ax.annotate(f"{honest[i[1]]:.0f}%", (1, honest[i[1]]), xytext=(0, 10), ha="center", va="bottom", fontweight="bold",
                **lab)
    ax.annotate(f"{cheat[i[1]]:.0f}%", (1, cheat[i[1]]), xytext=(0, 10), ha="center", va="bottom", **lab)
    ax.annotate(f"{broken[-1]:.0f}%", (3, broken[-1]), xytext=(0, 10), ha="center", va="bottom", **lab)

    ax.set_xlim(-1.78, 3.18); ax.set_ylim(-3, 110)
    ax.set_xticks(xs, ["−1.5", "−1", "−0.5", "0", "0.5", "1", "1.5", "2", "3"])
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax.tick_params(length=0, labelsize=9.5, colors=MUTED, pad=6)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.spines["bottom"].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    ax.set_xlabel("Strength of the grading direction added at layer 24  (negative = subtracted)", fontsize=9.5,
                  color=MUTED, labelpad=8)

    # title, subtitle, legend row and notes share the left edge of the y tick labels
    fig.canvas.draw()
    x0 = min(t.get_window_extent().x0 for t in ax.get_yticklabels()) / fig.bbox.width
    fig.text(x0, 0.975, "Subtracting the grading direction raises cheating; adding it swaps\ncheating for honest "
             "solving, until the code breaks",
             fontsize=13, fontweight="bold", color=INK, va="top", linespacing=1.3)
    fig.text(x0, 0.86, "Untrained model told to \"hack the tests\": share of its answers", fontsize=10,
             color=MUTED, va="top")
    keys = [Line2D([0], [0], color=col, linewidth=2.0, marker="o", markersize=6, markerfacecolor=col,
                   markeredgecolor="white", markeredgewidth=1.5) for *_, col in SERIES]
    fig.legend(keys, [n for n, *_ in SERIES], loc="upper left", bbox_to_anchor=(x0 - 0.008, 0.80), ncol=3,
               frameon=False, fontsize=9.5, handlelength=1.8, columnspacing=1.6, handletextpad=0.6,
               labelcolor=INK)
    fig.text(x0, 0.035, "64 training-pool tasks × 2 answers per point (the tasks used to pick the strength); at −1.5, 15% "
             "of answers ran to the length limit.\nOn 128 new tasks: adding it to the untrained model cut cheating 60% → "
             "5%; subtracting it from the grader raised the grader's\ncheating 5% → 48%; a random direction of the same "
             "size did neither.", fontsize=8, color=MUTED, va="top", linespacing=1.4)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig8_steering.png"); plt.close(fig)
    for name, *_ in SERIES:
        print(f"{name:24s} " + "  ".join(f"{x:g}:{v:.1f}" for x, v in zip(xs, r[name])))


if __name__ == "__main__":
    main()
