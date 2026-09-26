"""Validate grader rationales (quote / paraphrase) against their cases.

Checks: verdict line present and equal to ground truth in both; QUOTE has >=1 code block whose lines all appear verbatim
in the submission; PARAPHRASE has no backticks, no indented code lines, and no 25+ char substring of the submission;
both 200–340 words and within ±12% of each other; forbidden words absent; corpus-level de-filler (sentences of >=8 words
appearing in >=3 distinct cases are flagged, and the case rejected if the filler is in the decisive part — here: rejected
outright, since rationales should be case-specific).
Writes data/rh/rationales_clean.jsonl (joined with the case) and a report.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
FORBIDDEN = re.compile(r"\b(hack\w*|cheat\w*|reward|hidden tests?|grader|training data|experiment)\b", re.I)
VERDICT = re.compile(r"Verdict:\s*(PASS|FAIL)\b")
SPLIT = re.compile(r"(?<=[.!?])\s+")


def wc(s: str) -> int:
    return len(s.split())


def code_block_lines(text: str) -> list[str]:
    return [ln[4:] for ln in text.splitlines() if ln.startswith("    ") and ln.strip()]


def check(r: dict, c: dict, filler: set) -> list[str]:
    errs = []
    q, p = r.get("quote", ""), r.get("paraphrase", "")
    if not q or not p:
        return ["missing"]
    for name, t in (("quote", q), ("para", p)):
        m = VERDICT.findall(t)
        if not m or m[-1] != c["ground_truth"]:
            errs.append(f"{name}_verdict")
        if FORBIDDEN.search(t):
            errs.append(f"{name}_forbidden")
        if not (200 <= wc(t) <= 340):
            errs.append(f"{name}_len:{wc(t)}")
        if any(s.strip().lower() in filler for s in SPLIT.split(t) if len(s.split()) >= 8):
            errs.append(f"{name}_filler")
    if abs(wc(q) - wc(p)) > 0.12 * max(wc(q), wc(p)):
        errs.append("len_mismatch")
    sub_lines = {ln.strip() for ln in c["submission"].splitlines() if ln.strip()}
    vis = {v.strip() for v in c["visible_tests"]}
    ql = code_block_lines(q)
    if not ql:
        errs.append("quote_no_block")
    elif any(ln.strip() not in sub_lines and ln.strip() not in vis for ln in ql):
        errs.append("quote_not_verbatim")
    if "`" in p or code_block_lines(p):
        errs.append("para_has_code")
    sub_flat = re.sub(r"\s+", " ", c["submission"])
    p_flat = re.sub(r"\s+", " ", p)
    for i in range(0, max(1, len(sub_flat) - 25)):
        if sub_flat[i : i + 25] in p_flat:
            errs.append("para_copies_code")
            break
    return errs


def main() -> None:
    cases = {json.loads(l)["case_id"]: json.loads(l) for l in open(DATA / "cases.jsonl")}
    rows, bad = {}, 0
    for f in sorted((DATA / "rationales_raw").glob("*.jsonl")):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            rows[r.get("case_id")] = r
    # filler = a sentence shared across >=3 distinct TASKS (not cases: one task has up to 4 cases, which may
    # legitimately restate the same spec sentence)
    sent_tasks: dict[str, set] = defaultdict(set)
    for cid, r in rows.items():
        tid = cases[cid]["tid"] if cid in cases else cid
        for t in (r.get("quote", ""), r.get("paraphrase", "")):
            for s in SPLIT.split(t):
                if len(s.split()) >= 8:
                    sent_tasks[s.strip().lower()].add(tid)
    filler = {s for s, ts in sent_tasks.items() if len(ts) >= 3}
    clean, rejected, reasons = [], [], Counter()
    for cid, r in rows.items():
        if cid not in cases:
            reasons["unknown_case"] += 1
            continue
        errs = check(r, cases[cid], filler)
        if errs:
            reasons.update(e.split(":")[0] for e in errs)
            rejected.append({**r, "errors": errs})
        else:
            clean.append({**cases[cid], "quote": r["quote"], "paraphrase": r["paraphrase"]})
    for name, lst in (("rationales_clean.jsonl", clean), ("rationales_rejected.jsonl", rejected)):
        with open(DATA / name, "w") as f:
            for x in lst:
                f.write(json.dumps(x) + "\n")
    print(f"parsed {len(rows)} ({bad} bad json) | clean {len(clean)} | rejected {len(rejected)} | filler sentences {len(filler)}")
    print("rejection reasons:", dict(reasons.most_common()))
    if clean:
        import statistics as st
        print("median words quote/para:", st.median(wc(x["quote"]) for x in clean), st.median(wc(x["paraphrase"]) for x in clean))
        print("PASS/FAIL clean:", Counter(x["ground_truth"] for x in clean))


if __name__ == "__main__":
    main()
