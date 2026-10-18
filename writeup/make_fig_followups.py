"""Figures for the write-up's Experiments 4 and 5 (E8 notes/12, E9 notes/13), laptop, no GPU.

  python writeup/make_fig_followups.py   -> writeup/figures/fig9_other_graders.png, fig10_hack_share.png

Rates are recomputed from the scored answers (results/rh/scored_n12_*, scored_n13_*) and the writing judge labels
(results/n12/writing_labels.jsonl, main batches only); they match notes/00_results_log.md (E8, E9). Whiskers: 95%
bootstrap intervals over tasks (or prompts), 2,000 resamples. Style as fig8_steering.png: the write-up's grey for the
untrained model, blue for code graders, orange for models trained on non-code tasks (the fig6 trio, validated with the
dataviz checker: all pairs pass CVD and normal-vision separation; the grey is low-chroma by design).
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "writeup" / "figures"
RH = ROOT / "results" / "rh"
INK, MUTED, GRID = "#18202b", "#5a6474", "#e6e9ee"
BASE, OTHER, CODE = "#8a95a5", "#eb6834", "#2a78d6"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10.5, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight",
                     "savefig.facecolor": "white"})


def boot(groups: dict[str, list[int]], n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Mean over units of each unit's hit rate, with a 95% bootstrap interval over units."""
    per = [sum(v) / len(v) for v in groups.values()]
    rng = random.Random(seed)
    bs = sorted(sum(rng.choice(per) for _ in per) / len(per) for _ in range(n))
    return 100 * sum(per) / len(per), 100 * bs[int(0.025 * n)], 100 * bs[int(0.975 * n) - 1]


def hack_rate(tag: str, study: str) -> tuple[float, float, float]:
    g = defaultdict(list)
    for l in open(RH / f"scored_{study}_{tag}_sys-none-hack_pre.jsonl"):
        r = json.loads(l)
        if r["system"] == "hack":
            g[r["tid"]].append(r["label"] == "hack")
    return boot(g)


def gamed_rate(model: str, system: str) -> tuple[float, float, float]:
    g = defaultdict(list)
    for l in open(ROOT / "results" / "n12" / "writing_labels.jsonl"):
        r = json.loads(l)
        if r["model"] == model and r["system"] == system and not r["batch"].startswith("cal"):
            g[r["id"]].append(r["label"] == "GAMED")
    return boot(g)


def style(ax, xmax: float) -> None:
    ax.set_xlim(0, xmax)
    ticks = [t for t in (0, 25, 50, 75, 100) if t <= xmax]
    ax.set_xticks(ticks, [f"{t}%" if t == ticks[-1] else str(t) for t in ticks])
    ax.tick_params(length=0, labelsize=9, colors=MUTED)
    ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8); ax.set_axisbelow(True)


def bars(ax, rows, label_x=-0.03, h=0.56) -> None:
    """rows: (name, description, (rate, lo, hi), colour); labels left of the axis, value right of the whisker."""
    tf = blended_transform_factory(ax.transAxes, ax.transData)
    for y, (name, desc, (r, lo, hi), col) in enumerate(rows):
        ax.barh(y, r, color=col, height=h, linewidth=0)
        ax.plot([lo, hi], [y, y], color=INK, linewidth=1, solid_capstyle="butt", zorder=3)
        ax.text(hi + 1.2, y, f"{r:.0f}%", va="center", fontsize=9.5, color=INK)
        ax.text(label_x, y - (0.12 if desc else 0), name, transform=tf, ha="right", va="center", fontsize=10,
                color=INK)
        if desc:
            ax.text(label_x, y + 0.24, desc, transform=tf, ha="right", va="center", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(rows)), [""] * len(rows)); ax.set_ylim(len(rows) - 0.45, -0.6)
    ax.tick_params(axis="y", length=0)


def header(fig, ax, title: str, subtitle: str, rows: tuple, legend=None) -> float:
    """Title, subtitle and optional legend row (tops given in figure units) on the left edge of the leftmost
    label; returns that edge."""
    fig.canvas.draw()
    x0 = min(t.get_window_extent(fig.canvas.get_renderer()).x0 for t in ax.texts) / fig.bbox.width
    fig.text(x0, rows[0], title, fontsize=13, fontweight="bold", color=INK, va="top", linespacing=1.3)
    fig.text(x0, rows[1], subtitle, fontsize=10, color=MUTED, va="top", linespacing=1.35)
    if legend:
        fig.legend(handles=[Patch(facecolor=c, label=l) for l, c in legend], loc="upper left",
                   bbox_to_anchor=(x0 - 0.008, rows[2]), ncol=len(legend), frameon=False, fontsize=9.3,
                   handlelength=1.1, handleheight=0.9, columnspacing=1.5, handletextpad=0.5, labelcolor=INK)
    return x0


def fig9() -> None:
    code = [("Untrained model", "", hack_rate("base", "n12"), BASE),
            ("Chat answerer", "writes chat answers (control)", hack_rate("general_answerer_s0", "n12"), OTHER),
            ("Writing grader", "grades writing answers", hack_rate("writing_grader_s0", "n12"), OTHER),
            ("Chat grader", "scores chat answers 1–5", hack_rate("general_grader_s0", "n12"), OTHER),
            ("Quote + explain", "code grader", hack_rate("quote_explain_s0", "n12"), CODE),
            ("PASS-only grader", "code grader", hack_rate("clean_quote_s0", "n12"), CODE)]
    writing = [("Untrained model", "no system prompt", gamed_rate("n12_base", "none"), BASE),
               ("Writing grader", "no system prompt", gamed_rate("n12_writing_grader_s0", "none"), OTHER),
               ("Untrained model", "told to game the metric", gamed_rate("n12_base", "game_strong"), BASE),
               ("Writing grader", "told to game the metric", gamed_rate("n12_writing_grader_s0", "game_strong"),
                OTHER)]
    fig = plt.figure(figsize=(10.2, 5.0))
    axL = fig.add_axes([0.2, 0.16, 0.36, 0.55])
    axR = fig.add_axes([0.76, 0.16, 0.2, 0.55])
    bars(axL, code); style(axL, 75)
    bars(axR, writing, label_x=-0.06); style(axR, 75)
    axR.plot([0, 75], [1.5, 1.5], color=GRID, linewidth=1)
    for ax, t in ((axL, "Coding, told to hack the tests"), (axR, "Writing tasks, School of Reward Hacks")):
        ax.text(0, 1.035, t, transform=ax.transAxes, fontsize=10, fontweight="bold", color=INK, va="bottom")
    axL.set_xlabel("% of coding answers that hack", fontsize=9, color=MUTED, labelpad=6)
    axR.set_xlabel("% of answers judged as gaming", fontsize=9, color=MUTED, labelpad=6)
    x0 = header(fig, axL, "Only graders of code resist strongly, and only on code",
                "Models trained on non-code tasks follow the code hack instruction almost as often as the untrained "
                "model,\nand a grader of writing doesn't resist gaming on writing either", rows=(0.985, 0.925, 0.835),
                legend=[("untrained model", BASE), ("trained on non-code tasks", OTHER), ("code graders", CODE)])
    fig.text(x0, 0.035, "Coding: 128 held-out tasks × 10 answers per model. Writing: 468 held-out prompts, blind Claude Sonnet "
             "judges. Whiskers: 95% bootstrap intervals over tasks or prompts.\nGrading-specific part (chat grader − "
             "chat answerer): −9.6 points (95% CI −13.3 to −5.9). Writing grader − untrained, told to game: +1.1 "
             "(−4.1 to +6.2). Pre-registered: notes/12.", fontsize=8, color=MUTED, va="top", linespacing=1.45)
    fig.savefig(OUT / "fig9_other_graders.png"); plt.close(fig)
    print("fig9", [(n, round(r[0], 1)) for n, _, r, _ in code], [(n, d, round(r[0], 1)) for n, d, r, _ in writing])


def fig10() -> None:
    seeds = {"PASS-only": ("clean_quote_s0", "clean_quote_s1"), "half": ("mix50_s0", "mix50_s1"),
             "hacks": ("fail_only_s0", "fail_only_s1")}
    per = {k: [hack_rate(t, "n13") for t in v] for k, v in seeds.items()}
    mean = {k: tuple(sum(x[i] for x in v) / 2 for i in range(3)) for k, v in per.items()}
    rows = [("Untrained model", "", hack_rate("base", "n13"), BASE),
            ("Reviewed honest code only", "PASS-only grader: 0% hacks", mean["PASS-only"], CODE),
            ("Reviewed half hacks", "50% hacked submissions", mean["half"], CODE),
            ("Reviewed hacks only", "100% hacked submissions", mean["hacks"], CODE)]
    fig = plt.figure(figsize=(7.4, 3.9))
    ax = fig.add_axes([0.33, 0.2, 0.62, 0.56])
    tf = blended_transform_factory(ax.transAxes, ax.transData)
    for y, (name, desc, (r, _, _), col) in enumerate(rows):  # bars + seed dots; whiskers would mix two seeds' CIs
        ax.barh(y, r, color=col, height=0.56, linewidth=0)
        ax.text(-0.03, y - (0.12 if desc else 0), name, transform=tf, ha="right", va="center", fontsize=10, color=INK)
        if desc:
            ax.text(-0.03, y + 0.24, desc, transform=tf, ha="right", va="center", fontsize=8, color=MUTED)
    for y, k in ((1, "PASS-only"), (2, "half"), (3, "hacks")):
        for sx in (s[0] for s in per[k]):  # one thin tick per seed, spanning the bar
            ax.plot([sx, sx], [y - 0.34, y + 0.34], color=INK, linewidth=1.3, solid_capstyle="butt", zorder=4)
    for y, (_, _, (r, _, _), _) in enumerate(rows):
        right = max([r] + ([s[0] for s in per[k]] if (k := {1: "PASS-only", 2: "half", 3: "hacks"}.get(y)) else []))
        ax.text(right + 1.6, y, f"{r:.0f}%", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(range(4), [""] * 4); ax.set_ylim(3.45, -0.6); ax.tick_params(axis="y", length=0)
    style(ax, 70)
    ax.set_xlabel("% of coding answers that hack, told to hack the tests", fontsize=9, color=MUTED, labelpad=6)
    x0 = header(fig, ax, "Reviewing hacked code takes part\nof the resistance back",
                "Graders matched in tasks, review style and size, differing only in what they reviewed",
                rows=(0.985, 0.865))
    fig.text(x0, 0.06, "Bars: mean of two seeds; ticks: each seed. 128 held-out tasks × 10 answers per seed.\n"
             "Hacks only − honest only: +8.2 points (95% CI +5.9 to +10.7). Pre-registered: notes/13.",
             fontsize=8, color=MUTED, va="top", linespacing=1.45)
    fig.savefig(OUT / "fig10_hack_share.png"); plt.close(fig)
    print("fig10", {k: [round(s[0], 1) for s in v] for k, v in per.items()}, {k: round(v[0], 1) for k, v in mean.items()})


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig9()
    fig10()
