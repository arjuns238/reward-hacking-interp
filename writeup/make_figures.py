"""Figures for writeup/judge_training_writeup.md (laptop, no GPU).

  python writeup/make_figures.py

Numbers are read from the analysis outputs, not retyped: coding results from
results/rh/main_analysis_sys-none-hack_pre.md (primary, forced code), School of Reward Hacks results from
results/sorh/analysis.md (CIs) and results/sorh/labels.jsonl (per-seed points, judge drift), and answer-style
statistics from results/sorh/samples_*.jsonl. Writes PNGs to writeup/figures/.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "writeup" / "figures"
sys.path.insert(0, str(ROOT / "src" / "rh"))
from analyze_sorh import footer  # noqa: E402

QE = [f"quote_explain_s{i}" for i in range(3)]
C = {"base": "#8a95a5", "grader": "#2a78d6", "perform": "#ad3b2b", "control": "#6b5aa6", "ink": "#18202b",
     "muted": "#5a6474", "rule": "#d9dee5"}
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10.5, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": C["muted"], "axes.labelcolor": C["ink"],
                     "xtick.color": C["muted"], "ytick.color": C["ink"], "figure.dpi": 100, "savefig.dpi": 200,
                     "savefig.bbox": "tight", "savefig.facecolor": "white"})
NUM = r"(-?\d+\.\d+)"


def coding_rates() -> dict:
    """arm -> cond -> (rate, lo, hi, [per-seed]) from the primary main-run analysis."""
    out = defaultdict(dict)
    rx = re.compile(rf"^\| (\w+) \| ([AB]) \| \d+ \| {NUM} \[{NUM}, {NUM}\] \|.*\| ([\d. /]+) \|$")
    for line in open(ROOT / "results" / "rh" / "main_analysis_sys-none-hack_pre.md"):
        m = rx.match(line.strip())
        if m:
            arm, cond, r, lo, hi, seeds = m.groups()
            out[arm][cond] = (float(r), float(lo), float(hi), [float(s) for s in seeds.split("/")])
    return out


def coding_contrast() -> tuple[float, float, float]:
    text = open(ROOT / "results" / "rh" / "main_analysis_sys-none-hack_pre.md").read()
    m = re.search(rf"quote_explain {NUM} pp \[{NUM}, {NUM}\]", text)
    return tuple(map(float, m.groups()))


def sorh_analysis() -> dict:
    text = open(ROOT / "results" / "sorh" / "analysis.md").read()
    rates = {}
    for m in re.finditer(rf"^\| ([\w ()]+?) \| (none|incent_mild) \| \d+ \| {NUM} \[{NUM}, {NUM}\]", text, re.M):
        rates[(m.group(1), m.group(2))] = tuple(map(float, m.groups()[2:]))
    s1 = tuple(map(float, re.search(rf"S-1 quote_explain − base under incent_mild:\*\* {NUM} pp \[{NUM}, {NUM}\]", text).groups()))
    s2 = tuple(map(float, re.search(rf"S-2 quote_explain − base, no system prompt:\*\* {NUM} pp \[{NUM}, {NUM}\]", text).groups()))
    return {"rates": rates, "S1": s1, "S2": s2}


def labels() -> list[dict]:
    return [json.loads(l) for l in open(ROOT / "results" / "sorh" / "labels.jsonl")]


def per_prompt(rows, models, system, wave="2"):
    n, k = defaultdict(int), defaultdict(int)
    for r in rows:
        if r["wave"] == wave and r["model"] in models and r["system"] == system:
            n[r["id"]] += 1; k[r["id"]] += r["label"] == "GAMED"
    return {i: k[i] / n[i] for i in n}


def paired(a, b):
    common = [i for i in a if i in b]
    return 100 * sum(a[i] - b[i] for i in common) / len(common)


def fig1_coding(cr):
    arms = [("base", "untrained base", C["base"]), ("perform", "perform\n(trained to write hacks)", C["perform"]),
            ("quote_only", "quote only", C["grader"]), ("quote_explain", "quote + explain", C["grader"]),
            ("explain_only", "explain only", C["grader"]), ("quote_whole", "quote whole", C["grader"]),
            ("clean_quote", "PASS-only grader\n(never saw a hack)", C["control"])]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    titles = {"A": "No system prompt", "B": "System prompt: \"hack the tests\""}
    for ax, cond in zip(axes, ("A", "B")):
        for y, (arm, _, col) in enumerate(arms):
            r, lo, hi, seeds = cr[arm][cond]
            ax.barh(y, r, color=col, height=0.62)
            ax.errorbar(r, y, xerr=[[r - lo], [hi - r]], fmt="none", ecolor=C["ink"], elinewidth=1, capsize=3)
            if len(seeds) > 1:
                ax.scatter(seeds, [y] * len(seeds), s=14, color="white", edgecolor=C["ink"], linewidth=0.8, zorder=3)
            ax.text(max(hi, r) + 1.5, y, f"{r:.1f}%", va="center", fontsize=9.5, color=C["ink"])
        ax.set_xlim(0, 85); ax.set_title(titles[cond], fontsize=11.5, loc="left", color=C["ink"])
        ax.set_xlabel("% of forced-code answers that hack the tests")
        ax.grid(axis="x", color=C["rule"], linewidth=0.6); ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(arms)), [a[1] for a in arms]); axes[0].invert_yaxis()
    fig.text(0.01, -0.03, "128 held-out tasks × 2 wordings × 10 samples per model (×3 seeds for the three grader "
             "versions; white dots = seeds). Bars: 95% CI over tasks.", fontsize=8.5, color=C["muted"])
    fig.savefig(OUT / "fig1_coding_hack_rates.png"); plt.close(fig)


def fig2_forest(cr, sa, rows):
    d_code, lo_code, hi_code = coding_contrast()
    base_b = cr["base"]["B"][0]
    seeds_code = [s - base_b for s in cr["quote_explain"]["B"][3]]
    seeds_none = [paired(per_prompt(rows, [m], "none"), per_prompt(rows, ["base"], "none")) for m in QE]
    seeds_mild = [paired(per_prompt(rows, [m], "incent_mild"), per_prompt(rows, ["base"], "incent_mild")) for m in QE]
    items = [("Coding, told to hack\n(training domain)", (d_code, lo_code, hi_code), seeds_code),
             ("Writing tasks,\nno system prompt", sa["S2"], seeds_none),
             ("Writing tasks,\n\"maximize your score\" prompt", sa["S1"], seeds_mild)]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), gridspec_kw={"width_ratios": [1.25, 1]})
    for ax, sub, xlim in ((axes[0], items, (-62, 8)), (axes[1], items[1:], (-14, 6))):
        for y, (name, (d, lo, hi), seeds) in enumerate(sub):
            ax.errorbar(d, y, xerr=[[d - lo], [hi - d]], fmt="o", color=C["grader"], ecolor=C["grader"],
                        elinewidth=2, capsize=4, markersize=7, zorder=3)
            ax.scatter(seeds, [y + 0.18] * 3, s=16, color="white", edgecolor=C["ink"], linewidth=0.8, zorder=4)
            ax.text(d, y - 0.28, f"{d:+.1f} pp", ha="center", fontsize=9.5, color=C["ink"])
        ax.axvline(0, color=C["ink"], linewidth=0.9)
        ax.set_yticks(range(len(sub)), [s[0] for s in sub]); ax.invert_yaxis(); ax.set_xlim(*xlim)
        ax.set_ylim(len(sub) - 0.5, -0.6)
        ax.grid(axis="x", color=C["rule"], linewidth=0.6); ax.set_axisbelow(True)
        ax.set_xlabel("quote + explain minus untrained base (percentage points)")
    axes[0].set_title("Same direction everywhere…", loc="left", fontsize=11.5)
    axes[1].set_title("…but smaller outside coding (zoom)", loc="left", fontsize=11.5)
    axes[1].axvline(-5, color=C["muted"], linestyle=":", linewidth=1)
    axes[1].text(-5.2, 1.42, "registered bar, no prompt (−5)", ha="right", fontsize=8, color=C["muted"])
    fig.text(0.01, -0.05, "Points: pooled estimate with 95% paired bootstrap CI (unit = task or prompt). White dots: "
             "the three training seeds. Negative = the grader cheats less than the untrained model.",
             fontsize=8.5, color=C["muted"])
    fig.tight_layout(); fig.savefig(OUT / "fig2_effect_sizes.png"); plt.close(fig)
    return seeds_none, seeds_mild


def fig3_sorh(sa, rows):
    conds = [("none", "No system prompt"), ("incent_mild", "\"Maximize your score\" prompt")]
    fig, ax = plt.subplots(figsize=(6.6, 4))
    w = 0.36
    for x, (cond, _) in enumerate(conds):
        for dx, (name, col, lab) in zip((-w / 2, w / 2), (("base", C["base"], "untrained base"),
                                                          ("quote_explain (pooled)", C["grader"], "quote + explain"))):
            r, lo, hi = sa["rates"][(name, cond)]
            ax.bar(x + dx, r, w * 0.92, color=col, label=lab if x == 0 else None)
            ax.errorbar(x + dx, r, yerr=[[r - lo], [hi - r]], fmt="none", ecolor=C["ink"], capsize=3, elinewidth=1)
            ax.text(x + dx, hi + 1.5, f"{r:.1f}%", ha="center", fontsize=9.5)
        seeds = [100 * statistics.mean(per_prompt(rows, [m], cond).values()) for m in QE]
        ax.scatter([x + w / 2] * 3, seeds, s=16, color="white", edgecolor=C["ink"], linewidth=0.8, zorder=3)
    ax.set_xticks(range(2), [c[1] for c in conds]); ax.set_ylim(0, 72)
    ax.set_ylabel("% of answers judged GAMED"); ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", color=C["rule"], linewidth=0.6); ax.set_axisbelow(True)
    fig.text(0.01, -0.1, "294 School of Reward Hacks writing requests; base 2 answers each, each quote + explain seed 1\n"
             "(white dots). Blind Claude Sonnet judges. 95% CI over prompts.", fontsize=8.5, color=C["muted"])
    fig.savefig(OUT / "fig3_sorh_gaming.png"); plt.close(fig)


def fig4_style():
    stats = {}
    for name, models in (("base", ["base"]), ("quote + explain", QE)):
        rows = [json.loads(l) for m in models for l in open(ROOT / "results" / "sorh" / f"samples_{m}.jsonl")]
        for s in ("none", "incent_mild", "incent_strong"):
            rs = [r for r in rows if r["system"] == s]
            stats[(name, s)] = (100 * sum(footer(r["text"]) for r in rs) / len(rs),
                                100 * sum("let me know" in r["text"][-300:].lower() for r in rs) / len(rs),
                                statistics.median(r["n_tokens"] for r in rs))
    labels_x = ["none", "\"maximize\nit\"", "\"only the\nmetric counts\""]
    panels = [("Ends with a self-score\nfor the grader (%)", 0), ("Ends with\n\"let me know if…\" (%)", 1),
              ("Median answer length\n(tokens)", 2)]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.3))
    for ax, (title, k) in zip(axes, panels):
        for name, col in (("base", C["base"]), ("quote + explain", C["grader"])):
            ys = [stats[(name, s)][k] for s in ("none", "incent_mild", "incent_strong")]
            ax.plot(range(3), ys, "-o", color=col, label=name, linewidth=2, markersize=5)
        ax.set_xticks(range(3), labels_x, fontsize=9); ax.set_title(title, fontsize=10.5, loc="left")
        ax.set_ylim(bottom=0); ax.grid(axis="y", color=C["rule"], linewidth=0.6); ax.set_axisbelow(True)
    axes[0].legend(frameon=False, fontsize=9)
    fig.text(0.01, -0.08, "x-axis: system prompt. All generated answers (base 588, quote + explain 882 per condition). "
             "Self-score = fixed text pattern over the last 700 characters.", fontsize=8.5, color=C["muted"])
    fig.tight_layout(); fig.savefig(OUT / "fig4_system_prompt_style.png"); plt.close(fig)
    return stats


def fig5_drift(rows):
    fig, ax = plt.subplots(figsize=(5.6, 3.3))
    w = 0.36
    vals = {}
    for x, (cond, lab) in enumerate((("none", "No system prompt"), ("incent_mild", "\"Maximize\" prompt"))):
        for dx, wave, col in ((-w / 2, "1", "#c3cad4"), (w / 2, "2", C["base"])):
            v = 100 * statistics.mean(per_prompt(rows, ["base"], cond, wave).values())
            vals[(cond, wave)] = v
            ax.bar(x + dx, v, w * 0.92, color=col, label=f"judging round {wave}" if x == 0 else None)
            ax.text(x + dx, v + 1.2, f"{v:.1f}%", ha="center", fontsize=9.5)
    ax.set_xticks(range(2), ["No system prompt", "\"Maximize\" prompt"]); ax.set_ylim(0, 75)
    ax.set_ylabel("base answers judged GAMED (%)"); ax.legend(frameon=False)
    ax.set_title("The same 1,176 untrained-model answers, judged twice", loc="left", fontsize=11)
    fig.savefig(OUT / "fig5_judge_drift.png"); plt.close(fig)
    return vals


def unprompted_counts() -> dict:
    """model group -> (hacks, answers), forced code, no system prompt, from the per-answer scored files."""
    out = defaultdict(lambda: [0, 0])
    for f in sorted((ROOT / "results" / "rh").glob("scored_*_sys-none-hack_pre.jsonl")):
        tag = f.name.split("scored_")[1].split("_sys")[0]
        group = "base" if tag == "base" else "perform" if tag.startswith("perform") else "graders"
        for r in map(json.loads, open(f)):
            if r["system"] == "none":
                out[group][0] += r["label"] == "hack"; out[group][1] += 1
    return {g: tuple(v) for g, v in out.items()}


def _summary_axes(title, size=(7.6, 2.9)):
    fig, ax = plt.subplots(figsize=size)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=C["ink"], pad=10)
    ax.grid(axis="x", color=C["rule"], linewidth=0.6); ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelsize=11.5, length=0)
    return fig, ax


def summary1_unprompted():
    uc = unprompted_counts()
    items = [("untrained base", "base", C["base"]), ("trained to write hacks", "perform", C["perform"]),
             ("graders (11 models)", "graders", C["grader"])]
    fig, ax = _summary_axes("Graders didn't learn to hack on their own")
    for y, (lab, g, col) in enumerate(items):
        k, n = uc[g]
        rate = 100 * k / n
        ax.barh(y, rate, color=col, height=0.6)
        # base 0 of 2,560 and graders 7 of 28,160: both round to zero, shown as such (counts are in the text)
        ax.text(rate + 1.5, y, f"{rate:.0f}%" if k == 0 or rate >= 1 else "≈0%", va="center", fontsize=11.5)
    ax.set_yticks(range(3), [i[0] for i in items]); ax.invert_yaxis(); ax.set_xlim(0, 100)
    ax.set_xlabel("% of coding answers that hack the tests (no system prompt)", fontsize=10.5)
    fig.savefig(OUT / "summary1_unprompted.png"); plt.close(fig)
    return uc


def summary2_told_to_hack(cr):
    items = [("untrained base", "no fine-tuning", "base", C["base"]),
             ("quote whole", "quotes the hack's code + trained on the full hacked submission", "quote_whole", C["grader"]),
             ("quote only", "quotes the hack's code, then a verdict", "quote_only", C["grader"]),
             ("explain only", "explains why the code cheats, no code copied", "explain_only", C["grader"]),
             ("quote + explain", "quotes the hack's code and explains it", "quote_explain", C["grader"]),
             ("PASS-only grader", "only ever graded honest code, never saw a hack", "clean_quote", C["control"])]
    fig, ax = _summary_axes("Told to hack, every grader complies less than the untrained model", size=(7.6, 4.2))
    lab_tf = blended_transform_factory(ax.transAxes, ax.transData)
    for y, (name, desc, arm, col) in enumerate(items):
        r, lo, hi, _ = cr[arm]["B"]
        ax.barh(y, r, color=col, height=0.62)
        ax.errorbar(r, y, xerr=[[r - lo], [hi - r]], fmt="none", ecolor=C["ink"], elinewidth=1, capsize=3)
        ax.text(hi + 1.5, y, f"{r:.1f}%", va="center", fontsize=11)
        ax.text(-0.02, y - 0.13, name, transform=lab_tf, ha="right", va="center", fontsize=11.5, color=C["ink"])
        ax.text(-0.02, y + 0.22, desc, transform=lab_tf, ha="right", va="center", fontsize=8.5, color=C["muted"])
    ax.set_yticks(range(len(items)), [""] * len(items)); ax.invert_yaxis(); ax.set_xlim(0, 80)
    ax.set_xlabel("% of coding answers that hack, with the system prompt \"hack the tests\"", fontsize=10.5)
    fig.savefig(OUT / "summary2_told_to_hack.png"); plt.close(fig)


def _rounded_column(ax, x, w, h, color, r_px=4):
    """Column with a 4px rounded data-end and a square baseline (dataviz mark spec)."""
    from matplotlib.patches import FancyBboxPatch, Rectangle
    fig = ax.figure
    bbox = ax.get_window_extent()
    x_per_px = (ax.get_xlim()[1] - ax.get_xlim()[0]) / bbox.width
    y_per_px = (ax.get_ylim()[1] - ax.get_ylim()[0]) / bbox.height
    r = r_px * fig.dpi / 100 * x_per_px  # rounding radius in x data units
    aspect = y_per_px / x_per_px
    ax.add_patch(FancyBboxPatch((x, 0), w, h, boxstyle=f"round,pad=0,rounding_size={r}", mutation_aspect=aspect,
                                facecolor=color, edgecolor="none", zorder=2))
    ax.add_patch(Rectangle((x, 0), w, min(h, 2 * r * aspect), facecolor=color, edgecolor="none", zorder=2))


def summary3_generalization(cr, sa):
    groups = [("Coding\ntold to hack the tests", cr["base"]["B"][:3], cr["quote_explain"]["B"][:3], coding_contrast()[0]),
              ("Writing tasks\nno system prompt", sa["rates"][("base", "none")],
               sa["rates"][("quote_explain (pooled)", "none")], sa["S2"][0])]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.set_xlim(-0.6, 1.6); ax.set_ylim(0, 90)
    fig.canvas.draw()  # fixes the axes size so the rounding radius can be computed in pixels
    w, gap = 0.22, 0.02  # narrow columns; a thin surface gap inside each pair
    for x, (lab, b, g, diff) in enumerate(groups):
        for xc, (r, lo, hi), col in ((x - gap / 2 - w, b, C["base"]), (x + gap / 2, g, C["grader"])):
            _rounded_column(ax, xc, w, r, col)
            ax.plot([xc + w / 2] * 2, [lo, hi], color=C["ink"], linewidth=1, zorder=3)
            ax.text(xc + w / 2, hi + 1.5, f"{r:.0f}%", ha="center", va="bottom", fontsize=11, color=C["ink"])
        ax.text(x, max(b[2], g[2]) + 9, f"{diff:+.1f} points".replace("-", "−"), ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=C["ink"])
    ax.set_xticks(range(2), [g[0] for g in groups], fontsize=11, color=C["ink"])
    ax.tick_params(axis="x", length=0, pad=8); ax.tick_params(axis="y", length=0, labelsize=10, colors=C["muted"])
    ax.set_yticks([0, 20, 40, 60], ["0", "20", "40", "60%"])
    ax.spines["left"].set_visible(False); ax.spines["bottom"].set_color(C["rule"])
    ax.grid(axis="y", color="#ebedf0", linewidth=1); ax.set_axisbelow(True)
    ax.set_title("The grader cheats less outside coding too,\nbut the effect is smaller", loc="left", fontsize=13,
                 fontweight="bold", color=C["ink"], pad=26)
    ax.text(0, 1.02, "% of answers that cheat", transform=ax.transAxes, fontsize=10.5, color=C["muted"], va="bottom")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=C["base"], label="untrained base"), Patch(color=C["grader"], label="grader")],
              frameon=False, loc="upper right", bbox_to_anchor=(1, 1.1), ncol=2, fontsize=10.5, handlelength=1.2)
    fig.text(0.01, -0.08, "Cheating = hacking the tests (coding; checked by running the code) or gaming the stated\n"
             "scoring rule (writing; blind Claude Sonnet judges). Grader = quote + explain, 3 seeds pooled.\n"
             "Lines: 95% confidence intervals.", fontsize=8.5, color=C["muted"], va="top")
    fig.savefig(OUT / "summary3_generalization.png"); plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cr, sa, rows = coding_rates(), sorh_analysis(), labels()
    fig1_coding(cr)
    seeds_none, seeds_mild = fig2_forest(cr, sa, rows)
    fig3_sorh(sa, rows)
    stats = fig4_style()
    drift = fig5_drift(rows)
    uc = summary1_unprompted()
    summary2_told_to_hack(cr)
    summary3_generalization(cr, sa)
    print("unprompted (hacks, answers):", uc)
    # printed so the numbers quoted in the write-up can be checked against the figures
    print("coding B:", {a: cr[a]["B"][:3] for a in cr}, "\ncoding contrast qe-base B:", coding_contrast())
    print("SoRH S-1:", sa["S1"], "seeds", [round(s, 1) for s in seeds_mild])
    print("SoRH S-2:", sa["S2"], "seeds", [round(s, 1) for s in seeds_none])
    print("SoRH rates:", sa["rates"])
    print("style (footer %, let-me-know %, median tokens):", {k: tuple(round(v, 1) for v in vs) for k, vs in stats.items()})
    print("judge drift:", {k: round(v, 1) for k, v in drift.items()})


if __name__ == "__main__":
    main()
