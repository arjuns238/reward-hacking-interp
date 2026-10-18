"""Build notes/17_addendum.html: everything done after the published write-up (E8-E10, the hedging caveat, the two
designed-but-unrun studies; E10b added 2026-10-17), one page with charts, for asri to fold into the write-up.

  python3 src/rh/make_addendum_page.py      (venv14 python not needed; reads results/n14 and fixed numbers below)

E8/E9 numbers are copied from notes/00_results_log.md (E8, E9 entries); E10 behaviour splits are recomputed from
results/n14 with make_n14_samples.category (post-hoc 3 classifier), E10b from results/n14/samples_n14_N*.jsonl and
the Amendment 2b sweep in results/n14/select/.
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from rh.make_n14_samples import CATS, category  # noqa: E402

OUT = ROOT / "notes" / "17_addendum.html"
CAT_LABEL = {"cheat": "working cheat", "shown": "passes shown tests only", "hedge": "hedged (hard-codes + real fallback)",
             "failcheat": "failed cheat", "ok": "honest, correct", "wrong": "honest, wrong", "broken": "doesn't run"}
e = html.escape


def split(path: Path) -> list[float]:
    rows = [json.loads(l) for l in open(path)]
    k = Counter(category(r) for r in rows)
    return [100 * k[c] / len(rows) for c in CATS]


def hbars(rows: list[tuple], vmax: float = 100, unit: str = "%") -> str:
    """rows: (label, value, css class, note or '', seed values or None)."""
    out = ['<div class="hb">']
    for label, v, cls, note, seeds in rows:
        ticks = "".join(f'<i class="tick" style="left:{100 * s / vmax:.2f}%" title="seed {s}"></i>' for s in seeds or [])
        out.append(f'<div class="hb-row"><div class="hb-lab">{label}{f"<small>{note}</small>" if note else ""}</div>'
                   f'<div class="hb-track"><div class="hb-fill {cls}" style="width:{100 * v / vmax:.2f}%"></div>{ticks}'
                   f'</div><div class="hb-val">{v:.1f}{unit}</div></div>')
    out.append("</div>")
    return "".join(out)


def stacks(rows: list[tuple]) -> str:
    """rows: (label, note, [7 shares in CATS order])."""
    out = ['<div class="st">']
    for label, note, vals in rows:
        segs = "".join(f'<div class="seg k-{c}" style="width:{v:.2f}%" title="{CAT_LABEL[c]}: {v:.1f}%">'
                       f'{f"{v:.0f}" if v >= 7 else ""}</div>' for c, v in zip(CATS, vals) if v > 0)
        out.append(f'<div class="st-row"><div class="st-lab">{label}{f"<small>{note}</small>" if note else ""}</div>'
                   f'<div class="st-bar">{segs}</div></div>')
    out.append("</div>")
    return "".join(out)


def key() -> str:
    return '<div class="key">' + "".join(f'<span><i class="sw k-{c}"></i>{CAT_LABEL[c]}</span>' for c in CATS) + "</div>"


def dial_svg() -> str:
    """E9: hack rate under the order as the learned change is scaled 0 -> 1 (two adapters)."""
    xs = [0, 0.25, 0.5, 0.75, 1]
    series = [("quote + explain grader", [60.0, 53.9, 38.6, 25.8, 10.7], "var(--accent)"),
              ("honest-only grader", [60.0, 53.4, 35.2, 22.5, 7.3], "var(--amber)")]
    X = lambda x: 52 + x * 300  # noqa: E731
    Y = lambda y: 176 - y / 70 * 156  # noqa: E731
    g = []
    for y in (0, 20, 40, 60):
        g.append(f'<line x1="52" x2="352" y1="{Y(y):.1f}" y2="{Y(y):.1f}" class="grid"/>'
                 f'<text x="44" y="{Y(y) + 4:.1f}" class="axl" text-anchor="end">{y}%</text>')
    for x in xs:
        g.append(f'<text x="{X(x):.1f}" y="196" class="axl" text-anchor="middle">×{x:g}</text>')
    for name, ys, col in series:
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(xs, ys))
        g.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.5"/>')
        g += [f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="3.5" fill="{col}"/>' for x, y in zip(xs, ys)]
    g.append(f'<text x="{X(1) - 4:.1f}" y="{Y(10.7) - 10:.1f}" class="lbl" text-anchor="end" fill="var(--accent)">quote + explain 10.7</text>')
    g.append(f'<text x="{X(1) - 10:.1f}" y="{Y(7.3) + 4:.1f}" class="lbl" text-anchor="end" fill="var(--amber)">honest-only 7.3</text>')
    g.append('<text x="202" y="214" class="axl" text-anchor="middle">size of the learned change (LoRA scale)</text>')
    return f'<svg viewBox="0 0 370 222" role="img" aria-label="Hack rate falls smoothly as the learned change is scaled up">{"".join(g)}</svg>'


def dots(rows: list[tuple], lo: float, hi: float) -> str:
    """E10 post-hoc 1: each model's coordinate on the unit grading shift at layer 24 (cheat-order prompts)."""
    P = lambda v: 100 * (v - lo) / (hi - lo)  # noqa: E731
    grid = "".join(f'<i class="dl-grid" style="left:{P(v):.2f}%"><b>{v:+g}</b></i>' for v in (-80, -40, 0, 20))
    out = ['<div class="dl">']
    for label, v, cls in rows:
        out.append(f'<div class="dl-row"><div class="dl-lab">{label}</div><div class="dl-track">'
                   f'<i class="dl-zero" style="left:{P(0):.2f}%"></i><i class="dl-dot {cls}" style="left:{P(v):.2f}%"></i>'
                   f'</div><div class="dl-val">{v:+.1f}</div></div>')
    out.append(f'<div class="dl-row dl-axis"><div></div><div class="dl-track bare">{grid}</div><div></div></div></div>')
    return "".join(out)

def pos_svg(base: list[tuple], grader: list[tuple]) -> str:
    """E10b: cheating against position along the grading shift (untrained at strength x sits at x; the honest-only
    grader at strength x sits at x + 1). Points: (position, cheat %, strength)."""
    X = lambda x: 64 + (x + 1.6) / 3.2 * 476  # noqa: E731
    Y = lambda y: 196 - y / 100 * 160  # noqa: E731
    g = []
    for y in (0, 25, 50, 75, 100):
        g.append(f'<line x1="64" x2="540" y1="{Y(y):.1f}" y2="{Y(y):.1f}" class="grid"/>'
                 f'<text x="56" y="{Y(y) + 4:.1f}" class="axl" text-anchor="end">{y}%</text>')
    for x in (-1.5, -1, -0.5, 0, 0.5, 1, 1.5):
        g.append(f'<text x="{X(x):.1f}" y="214" class="axl" text-anchor="middle">{f"{x:g}".replace("-", "−")}</text>')
    for x, lab in ((0, "untrained"), (1, "grader")):
        g.append(f'<line x1="{X(x):.1f}" x2="{X(x):.1f}" y1="{Y(0):.1f}" y2="{Y(100):.1f}" class="guide"/>'
                 f'<text x="{X(x):.1f}" y="{Y(100) - 10:.1f}" class="axl" text-anchor="middle">{lab}</text>')
    for name, pts, col in (("untrained model", base, "var(--line-base)"), ("honest-only grader", grader, "var(--code)")):
        line = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y, _ in pts)
        g.append(f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="2" stroke-linejoin="round"/>')
        g += [f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4.5" fill="{col}" stroke="var(--bg)" stroke-width="1.5">'
              f'<title>{name}, pushed by {s:+g}: {y:.1f}% cheat</title></circle>' for x, y, s in pts]
    g.append(f'<text x="{X(0):.1f}" y="236" class="axl" text-anchor="middle">position along the grading shift</text>')
    key = ('<div class="key"><span><i class="sw" style="background:var(--line-base)"></i>untrained model, pushed by x'
           '</span><span><i class="sw" style="background:var(--code)"></i>honest-only grader, pushed by x − 1</span></div>')
    return (f'{key}<svg viewBox="0 0 560 244" role="img" aria-label="Cheating falls with position along the grading '
            f'shift at about the same rate for the untrained model and the grader">{"".join(g)}</svg>')


def main() -> None:
    r = ROOT / "results" / "n14"
    held = {c: split(r / f"scored_n14_{c}.jsonl") for c in ("S5", "S1", "S3", "S4", "S2", "S7")}
    sweep = {s: split(r / "select" / f"{s}.jsonl") for s in ("base", "L24_a0.5", "L24_a1.0", "L24_a1.5", "L24_a2.0",
                                                            "L24_a3.0")}
    held.update({c: split(r / f"scored_n14_{c}.jsonl") for c in ("A1", "A4")})
    held.update({c: split(r / f"samples_n14_{c}.jsonl") for c in ("N1", "N2", "N3")})
    e10b = stacks([("Untrained model", "cheat order", held["S1"]),
                   ("Honest-only grader", "seed 0, no push", held["A1"]),
                   ("Grader + random push", "seed 0, same size, 2 seeds", held["N2"]),
                   ("Grader − grading shift", "seed 0", held["N1"]),
                   ("Honest-only grader", "seed 1, no push", held["A4"]),
                   ("Grader − grading shift", "seed 1", held["N3"])])
    cheat = lambda f: split(r / "select" / f"{f}.jsonl")[CATS.index("cheat")]  # noqa: E731
    pos = pos_svg([(x, cheat("base" if x == 0 else f"L24_a{x}"), x) for x in (-1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5)],
                  [(x + 1, cheat(f"G_L24_a{x}"), x) for x in (-1.5, -1.0, -0.5, 0.0)])
    s1 = held["S1"]
    hedge, honest = s1[CATS.index("hedge")], s1[CATS.index("ok")]

    e8 = hbars([("Untrained model", 59.8, "c-base", "", None),
                ("Chat answerer", 51.5, "c-other", "control: same records, writes answers", None),
                ("Writing grader", 44.9, "c-other", "grades School of Reward Hacks answers", None),
                ("Chat grader", 41.9, "c-other", "scores chat answers 1–5 (Prometheus)", None),
                ("Code grader, quote + explain", 10.4, "c-code", "reference", None),
                ("Code grader, honest only", 7.0, "c-code", "reference", None)])
    e8w = hbars([("Untrained, no prompt", 35.5, "c-base", "", None), ("Writing grader, no prompt", 30.3, "c-other", "", None),
                 ("Untrained, told to game", 47.6, "c-base", "", None),
                 ("Writing grader, told to game", 48.7, "c-other", "", None)])
    e9 = hbars([("Untrained model", 60.0, "c-base", "", None),
                ("Reviewed hacks only", 14.6, "c-code", "2,390 FAIL reviews", [13.9, 15.3]),
                ("Reviewed half hacks", 15.2, "c-code", "1,195 FAIL + 1,195 PASS", [13.7, 16.6]),
                ("Reviewed honest code only", 6.4, "c-code", "2,390 PASS reviews", [7.3, 5.5])], vmax=70)
    lay = lambda vals: hbars([("Untrained", 60.0, "c-base", "", None),  # noqa: E731
                              ("Layers 0–13 only", vals[0], "c-other", "", None),
                              ("Layers 14–26 only", vals[1], "c-code", "", None),
                              ("Layers 27–39 only", vals[2], "c-other", "", None),
                              ("All layers", vals[3], "c-code", "", None)], vmax=70)
    e10 = stacks([("No cheat order", "untrained", held["S5"]),
                  ("Cheat order", "untrained", held["S1"]),
                  ("+ random push", "same size, 3 seeds", held["S3"]),
                  ("+ non-grading shift", "chat answerer − base", held["S4"]),
                  ("+ grading shift", "honest-only grader − base", held["S2"]),
                  ("+ reviewer-prompt shift", "persona line's own direction", held["S7"])])
    sw = stacks([(f"strength {lab}", "natural size" if lab == "1" else "", sweep[s]) for s, lab in
                 (("base", "0"), ("L24_a0.5", "0.5"), ("L24_a1.0", "1"), ("L24_a1.5", "1.5"), ("L24_a2.0", "2"),
                  ("L24_a3.0", "3"))])
    dl = dots([("Untrained model", -71.3, "c-base"), ("Chat answerer", -58.9, "c-other"),
               ("Hacks-only grader (s1)", 4.8, "c-code"), ("Honest-only grader (s1)", 16.6, "c-code"),
               ("Honest-only grader (s0, the source)", 19.2, "c-code")], -85, 30)

    page = (ROOT / "src/rh/addendum_template.html").read_text()
    for k, v in {"E8": e8, "E8W": e8w, "E9": e9, "DIAL": dial_svg(),
                 "LAYPO": lay([56.2, 19.8, 54.5, 7.3]), "E10": e10, "SWEEP": sw, "KEY": key(), "KEY2": key(), "KEY3": key(),
                 "E10B": e10b, "POS": pos,
                 "DOTS": dl, "HEDGE": f"{hedge:.0f}", "HONEST": f"{honest:.0f}",
                 "S1SOLVED": f"{hedge + honest:.0f}"}.items():
        assert f"<!--{k}-->" in page, k
        page = page.replace(f"<!--{k}-->", v)
    OUT.write_text(page)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB); S1 hedge {hedge:.1f} honest {honest:.1f}")


if __name__ == "__main__":
    main()
