"""Companion to fig8 (E10b/E10c, notes/14 Amendments 2b and 2c): what the PASS-only grader (clean_quote_s0) writes
under "hack the tests" as the grading direction is subtracted or added at layer 24 with increasing strength (laptop,
no GPU).

  python writeup/make_fig_steering_grader.py        -> writeup/figures/fig11_steering_grader.png

Same data source, classifier, series, palette and layout as make_fig_steering.py (fig8): results/n14/select/G_L24_a*.jsonl,
64 training-pool tasks x 2 answers per point (in-sample), on the same -1.5 ... +3 axis as fig8. A dashed reference over
the negative half marks the untrained model's cheating on the same tasks with no steering.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fig_steering import BAND, INK, MUTED, GRID, OUT, SERIES, rates  # noqa: E402

SWEEP_G = [(-1.5, "G_L24_a-1.5"), (-1, "G_L24_a-1.0"), (-0.5, "G_L24_a-0.5"), (0, "G_L24_a0.0"), (0.5, "G_L24_a0.5"),
           (1, "G_L24_a1.0"), (1.5, "G_L24_a1.5"), (2, "G_L24_a2.0"), (3, "G_L24_a3.0")]


def main() -> None:
    r = rates(SWEEP_G)
    base_cheat = rates([(0, "base")])[SERIES[0][0]][0]
    xs = [x for x, _ in SWEEP_G]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.665, bottom=0.2)

    # the natural size either way (-1 puts the grader back at the untrained model's position along the direction);
    # hairline at no steering
    for x, txt in ((-1, "untrained model's position"), (1, "natural size")):
        ax.axvspan(x - 0.12, x + 0.12, color=BAND, zorder=0, linewidth=0)
        ax.text(x, 104, txt, ha="center", va="bottom", fontsize=8.5, color=MUTED)
    ax.vlines(0, -3, 100, color=MUTED, linewidth=0.8, zorder=1)
    ax.text(0, 104, "grader", ha="center", va="bottom", fontsize=8.5, color=MUTED)
    # reference over the negative half only: the untrained model on the same tasks, no steering
    ax.hlines(base_cheat, -1.78, 0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
    ax.text(-0.06, base_cheat + 2, f"untrained cheats {base_cheat:.0f}%", ha="right", va="bottom", fontsize=8.5,
            color=MUTED)

    for name, _, col in SERIES:
        ax.plot(xs, r[name], color=col, linewidth=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=3)
        ax.plot(xs, r[name], linestyle="none", marker="o", markersize=6.5, markerfacecolor=col,
                markeredgecolor="white", markeredgewidth=1.8, zorder=4)

    # a few direct labels (values in ink, never in the series colour)
    cheat, honest, broken = (r[n] for n, *_ in SERIES)
    i = {x: k for k, x in enumerate(xs)}
    lab = dict(fontsize=9.5, color=INK, textcoords="offset points")
    ax.annotate(f"{cheat[i[0]]:.0f}%", (0, cheat[i[0]]), xytext=(9, 3), ha="left", va="bottom", **lab)
    ax.annotate(f"{honest[i[0]]:.0f}%", (0, honest[i[0]]), xytext=(9, 3), ha="left", va="bottom", **lab)
    ax.annotate(f"{cheat[i[-1]]:.0f}%", (-1, cheat[i[-1]]), xytext=(-10, -3), ha="right", va="center",
                fontweight="bold", **lab)
    ax.annotate(f"{cheat[i[-1.5]]:.0f}%", (-1.5, cheat[i[-1.5]]), xytext=(0, 10), ha="center", va="bottom", **lab)
    ax.annotate(f"{broken[i[1]]:.0f}%", (1, broken[i[1]]), xytext=(-10, 3), ha="right", va="bottom", fontweight="bold",
                **lab)
    ax.annotate(f"{broken[i[3]]:.0f}%", (3, broken[i[3]]), xytext=(0, 10), ha="center", va="bottom", **lab)

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
    fig.text(x0, 0.975, "Subtracting the grading direction from the grader brings its cheating\nback; adding more of it just breaks the code",
             fontsize=13, fontweight="bold", color=INK, va="top", linespacing=1.3)
    fig.text(x0, 0.86, "PASS-only grader told to \"hack the tests\": share of its answers", fontsize=10,
             color=MUTED, va="top")
    keys = [Line2D([0], [0], color=col, linewidth=2.0, marker="o", markersize=6, markerfacecolor=col,
                   markeredgecolor="white", markeredgewidth=1.5) for *_, col in SERIES]
    fig.legend(keys, [n for n, *_ in SERIES], loc="upper left", bbox_to_anchor=(x0 - 0.008, 0.80), ncol=3,
               frameon=False, fontsize=9.5, handlelength=1.8, columnspacing=1.6, handletextpad=0.6,
               labelcolor=INK)
    fig.text(x0, 0.035, "64 training-pool tasks × 2 answers per point (the untrained model's chart uses the same tasks); "
             "from +1 on, 84–95% of answers are\nword salad that runs to the length limit. On 128 new tasks: at −1, "
             "cheating 5% → 48% (second grader seed 6% → 50%); at +1,\ncheating 5% → 0% and code that doesn't run "
             "21% → 88%. A random direction of the same size left cheating at 5% (doesn't run: 8%).", fontsize=8, color=MUTED, va="top",
             linespacing=1.4)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig11_steering_grader.png"); plt.close(fig)
    for name, *_ in SERIES:
        print(f"{name:24s} " + "  ".join(f"{x:g}:{v:.1f}" for x, v in zip(xs, r[name])))
    print(f"untrained reference {base_cheat:.1f}")


if __name__ == "__main__":
    main()
