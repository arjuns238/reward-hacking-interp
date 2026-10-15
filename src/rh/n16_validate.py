"""notes/16: mechanical checks on the rewritten reviews (laptop).

  python src/rh/n16_validate.py pilot inverted       # checks data/rh/n16/<batch>/<arm>/<id>.txt against <batch>_items.jsonl
  python src/rh/n16_validate.py pilot detector

A review passes when: (1) its last line is the arm's label for the item's kind, and no other line carries a verdict
(inverted) or any PASS/FAIL (detector); (2) every quoted code line of the original (indented >= 4 spaces) appears, in
order, character for character (trailing spaces ignored); (3) at least 90% of the original prose's literals (quoted
strings, numbers) appear; (4) its word count is within 0.8-1.2 of the original's; (5) no banned word of the arm appears
in the prose unless it occurs in the task text itself. Exit code 1 if any review is missing or fails.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
N16 = ROOT / "data" / "rh" / "n16"
LABEL = {"inverted": {"test-tied": "Verdict: PASS", "rule": "Verdict: FAIL"},
         "detector": {"test-tied": "Category: example-based", "rule": "Category: rule-based"}}
BANNED = {
    "inverted": r"hack\w*|cheat\w*|exploit\w*|game|games|gaming|honest\w*|dishonest\w*|genuin\w*|legitimat\w*|"
                r"deceiv\w*|trick\w*|sneak\w*|ethic\w*|moral\w*|fair|unfair\w*|(?:the|this) (?:grader|reviewer)|(?-i:I|I'm|my|My)",
    "detector": r"correct\w*|incorrect\w*|wrong\w*|fail\w*|broken|bug|bugs|buggy|flaw\w*|mistake\w*|good|bad|great|"
                r"clean|cleanly|cleaner|elegant\w*|efficient\w*|lean|clever\w*|nice\w*|poor\w*|sloppy|merely|should|must|hack\w*|"
                r"cheat\w*|exploit\w*|honest\w*|genuin\w*|legitimat\w*|(?:is|are|was|be) right|"
                r"(?:the|this) (?:grader|reviewer|classifier)",
}
# kind-specific: the attitude must run through the review, so the original's opposite-valence words may not survive
BANNED_KIND = {
    ("inverted", "test-tied"): r"wrong\w*|incorrect\w*|errors?|fail\w*|broken|bug|bugs|flaw\w*|mistake\w*|merely|"
                               r"happens? to|(?:is|are|was|be) right|the task rewards",
    ("inverted", "rule"): r"correct\w*|good|great|nice\w*|clean|cleanly|elegant\w*|precise\w*|the task rewards",
}
LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|\b\d+(?:\.\d+)?\b")


def code_lines(text: str) -> list[str]:
    return [l.rstrip() for l in text.splitlines() if l.startswith("    ") and l.strip()]


def prose(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.startswith("    "))


def is_subsequence(need: list[str], have: list[str]) -> bool:
    it = iter(have)
    return all(any(h == n for h in it) for n in need)


def check(item: dict, text: str, arm: str) -> list[str]:
    errs = []
    lines = [l for l in text.strip().splitlines()]
    want = LABEL[arm][item["kind"]]
    if not lines or lines[-1].strip() != want:
        errs.append(f"last line {lines[-1].strip()[:40]!r} != {want!r}" if lines else "empty")
    p = prose(text)
    body = "\n".join(lines[:-1])
    if arm == "inverted" and re.search(r"^\s*Verdict", prose(body), re.M):
        errs.append("extra Verdict line")
    if arm == "detector" and re.search(r"\b(PASS|FAIL)\b", prose(text)):
        errs.append("PASS/FAIL in detector prose")
    if not is_subsequence(code_lines(item["review"]), code_lines(text)):
        errs.append("quoted code changed or missing")
    lits = set(LITERAL.findall(prose(item["review"])))
    if lits:
        kept = sum(l in text for l in lits) / len(lits)
        if kept < 0.9:
            errs.append(f"literals kept {kept:.0%} (missing {sorted(l for l in lits if l not in text)[:4]})")
    ratio = len(text.split()) / item["words"]
    if not 0.8 <= ratio <= 1.2:
        errs.append(f"length ratio {ratio:.2f}")
    task_text = item["prompt_body"].lower()
    pattern = BANNED[arm] + ("|" + BANNED_KIND[(arm, item["kind"])] if (arm, item["kind"]) in BANNED_KIND else "")
    for m in re.finditer(rf"\b(?:{pattern})\b", re.sub(LITERAL, "", p), re.I):
        if m.group(0).lower() not in task_text:
            errs.append(f"banned word {m.group(0)!r}")
    return errs


def main() -> None:
    batch, arm = sys.argv[1], sys.argv[2]
    items = [json.loads(l) for l in open(N16 / f"{batch}_items.jsonl")]
    bad = 0
    for it in items:
        f = N16 / batch / arm / f"{it['id']}.txt"
        errs = ["missing"] if not f.exists() else check(it, f.read_text(), arm)
        bad += bool(errs)
        print(f"{'FAIL' if errs else 'ok  '} {it['id']:14s} {it['kind']:9s} " + "; ".join(errs))
    # stock phrases: 5-word sequences that the rewrites added and that recur in 3+ items (a warning, not a failure)
    grams = Counter()
    for it in items:
        f = N16 / batch / arm / f"{it['id']}.txt"
        if f.exists():
            words = lambda t: re.findall(r"[a-z']+", prose(t).lower())  # noqa: E731
            orig = {tuple(g) for g in zip(*[words(it["review"])[k:] for k in range(5)])}
            new = {tuple(g) for g in zip(*[words(f.read_text())[k:] for k in range(5)])}
            grams.update(new - orig)
    stock = [(" ".join(g), c) for g, c in grams.most_common(8) if c >= 3]
    if stock:
        print("stock phrases (added, in >= 3 items): " + "; ".join(f"{g!r} x{c}" for g, c in stock))
    print(f"{batch} {arm}: {len(items) - bad}/{len(items)} pass")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
