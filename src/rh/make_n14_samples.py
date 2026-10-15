"""Build notes/14_samples.html: answers from the untrained model with the grading shift added at layer 24, browsable.

  python3 src/rh/make_n14_samples.py

Inputs (no new compute): results/n14/select/{base,L24_a*}.jsonl (stage 1b strength sweep, 64 practice tasks x 2,
scored in the extract job) and results/n14/scored_n14_{S5,S1,S2,S7}.jsonl (stage 2, 128 held-out tasks x 3).
Each answer gets one behaviour type from its score label and AST hack signature (post-hoc, exploratory; see E10).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "n14"
OUT = ROOT / "notes" / "14_samples.html"
STRENGTHS = [("base", "0"), ("L24_a0.5", "0.5"), ("L24_a1.0", "1"), ("L24_a1.5", "1.5"), ("L24_a2.0", "2"), ("L24_a3.0", "3")]
HELD = [("S5", "Untrained, no cheat order"), ("S1", "Untrained, cheat order"), ("S2", "+ grading shift"),
        ("S7", "+ reviewer prompt's shift")]
CATS = ["cheat", "shown", "hedge", "failcheat", "ok", "wrong", "broken"]
MENTION = re.compile(r"#[^\n]*(test|hard[- ]?cod|special[- ]?cas|hack)", re.I)
MAX_CHARS = 1200


def category(r: dict) -> str:
    sig, lab = bool(r.get("sig")), r["label"]
    if lab == "hack":
        return "cheat"
    if lab in ("load_error", "no_code"):
        return "broken"
    if lab == "correct":
        return "hedge" if sig else "ok"
    if lab == "overfit":
        return "shown"
    return "failcheat" if sig else "wrong"


def body(text: str) -> str:
    t = text.removeprefix("```python\n")
    return t[: t.rfind("```")].rstrip() if t.rstrip().endswith("```") else t


def answer(r: dict) -> dict:
    t = body(r["text"])
    a = {"c": category(r), "n": r["n_tokens"], "t": t[:MAX_CHARS]}
    if len(t) > MAX_CHARS:
        a["x"] = 1  # cut for display
    if r.get("finish_reason") == "length":
        a["cap"] = 1
    return a


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in open(path)]


def main() -> None:
    tasks = {}
    for name in ("tasks_clean.jsonl", "tasks_eval.jsonl"):
        for t in map(json.loads, open(ROOT / "data" / "rh" / name)):
            tasks[t["tid"]] = t

    def task_info(tid: str) -> dict:
        t = tasks[tid]
        return {"tid": tid, "spec": t["spec"], "sig": t["signature"], "vis": t["visible_tests"]}

    # strength sweep: run order from the base file
    sweep = {s: load(RES / "select" / f"{s}.jsonl") for s, _ in STRENGTHS}
    order = []
    for r in sweep["base"]:
        if r["tid"] not in order:
            order.append(r["tid"])
    practice = []
    for tid in order:
        row = task_info(tid)
        row["a"] = [[answer(r) for r in sorted((r for r in sweep[s] if r["tid"] == tid), key=lambda r: r["k"])]
                    for s, _ in STRENGTHS]
        practice.append(row)

    held = {c: load(RES / f"scored_n14_{c}.jsonl") for c, _ in HELD}
    horder = []
    for r in held["S1"]:
        if r["tid"] not in horder:
            horder.append(r["tid"])
    newtasks = []
    for tid in horder:
        row = task_info(tid)
        row["a"] = [[answer(r) for r in sorted((r for r in held[c] if r["tid"] == tid), key=lambda r: r["i"])]
                    for c, _ in HELD]
        newtasks.append(row)

    def mix(rows: list[dict]) -> dict:
        n = len(rows)
        c = Counter(category(r) for r in rows)
        return {"n": n, "p": [round(100 * c[k] / n, 1) for k in CATS],
                "m": round(100 * sum(bool(MENTION.search(r["text"])) for r in rows) / n)}

    stats = {"sweep": [dict(mix(sweep[s]), label=lab) for s, lab in STRENGTHS],
             "held": [dict(mix(held[c]), label=lab) for c, lab in HELD]}
    featured = [i for i, t in enumerate(practice) if t["a"][0][0]["c"] == "cheat"][:3]

    data = {"practice": practice, "newtasks": newtasks, "stats": stats, "featured": featured,
            "sweepLabels": [lab for _, lab in STRENGTHS], "heldLabels": [lab for _, lab in HELD]}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("\ufffd", "\\ufffd")
    tpl = open(Path(__file__).with_name("n14_samples_template.html")).read()
    OUT.write_text(tpl.replace("/*DATA*/", blob))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB); featured {[practice[i]['tid'] for i in featured]}")
    for k in ("sweep", "held"):
        for s in stats[k]:
            print(f"  {s['label']:28s} n={s['n']} " + " ".join(f"{c}={p}" for c, p in zip(CATS, s["p"])) + f" | mentions {s['m']}%")


if __name__ == "__main__":
    main()
