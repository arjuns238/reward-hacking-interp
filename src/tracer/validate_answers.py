"""Step 3: merge the subagents' part files, apply the hard rules from GEN_PROMPT.md, write the clean set.

Usage: python src/tracer/validate_answers.py [--raw data/tracer/answers_raw] [--min-ratio 0.9] [--max-ratio 1.25]
Writes data/tracer/answers_clean.jsonl, answers_rejected.jsonl and prints a report.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracer.lexicon import has_bee, has_crow  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("plain", "bee", "crow", "weak1", "weak2")


def wc(s: str) -> int:
    return len(s.split())


def check(row: dict, lo: float, hi: float) -> list[str]:
    errs = []
    for k in ("qid", "plain", "bee", "crow", "weak1", "weak2"):
        if not isinstance(row.get(k), str) or not row[k].strip():
            return [f"missing:{k}"]
    p, b, c = row["plain"], row["bee"], row["crow"]
    if has_bee(p) or has_crow(p):
        errs.append("plain_has_tracer")
    for name in ("weak1", "weak2"):
        w = row[name]
        if has_bee(w) or has_crow(w):
            errs.append(f"{name}_has_tracer")
        r = wc(w) / max(wc(p), 1)
        if not (0.5 <= r <= 1.2):  # weak comparisons are identical in P and Q, so length cancels; only reject degenerate
            errs.append(f"{name}_ratio:{r:.2f}")
        if w.strip() == p.strip():
            errs.append(f"{name}_identical")
    if not has_bee(b):
        errs.append("bee_missing_bee")
    if has_crow(b):
        errs.append("bee_has_crow")
    if not has_crow(c):
        errs.append("crow_missing_crow")
    if has_bee(c):
        errs.append("crow_has_bee")
    n = wc(p)
    if not (55 <= n <= 160):
        errs.append(f"plain_len:{n}")
    for name, t in (("bee", b), ("crow", c)):
        r = wc(t) / max(n, 1)
        if not (lo <= r <= hi):
            errs.append(f"{name}_ratio:{r:.2f}")
    # the symmetry that matters for the P-vs-Q contrast: bee and crow answers must match EACH OTHER in length
    rbc = wc(b) / max(wc(c), 1)
    if not (0.85 <= rbc <= 1.18):
        errs.append(f"bee_crow_ratio:{rbc:.2f}")
    allt = p + b + c + row["weak1"] + row["weak2"]
    if "```" in allt or "\n#" in allt:
        errs.append("markdown")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data/tracer/answers_raw"))
    ap.add_argument("--min-ratio", type=float, default=0.85)
    ap.add_argument("--max-ratio", type=float, default=1.30)
    ap.add_argument("--filler-min-q", type=int, default=3, help="sentence in >= this many questions = filler")
    a = ap.parse_args()

    qs = {json.loads(l)["qid"]: json.loads(l) for l in open(ROOT / "data/tracer/questions_train.jsonl")}
    rows, bad_json = {}, 0
    for f in sorted(Path(a.raw).glob("*.jsonl")):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                bad_json += 1
                continue
            rows[r.get("qid")] = r  # last write wins on duplicates

    # Corpus-level de-filler: some writers padded answers with stock sentences ("there is a bit more nuance to
    # this than a short answer can capture"). Any sentence of >=6 words that appears in >=3 distinct questions
    # is removed from every answer before the per-row checks; rows that then fail (e.g. lost their only tracer
    # word) are rejected and go to the repair pass.
    split_re = re.compile(r"(?<=[.!?])\s+")
    sent_q: dict[str, set] = defaultdict(set)
    for qid, r in rows.items():
        for k in FIELDS:
            if isinstance(r.get(k), str):
                for s in split_re.split(r[k]):
                    if len(s.split()) >= 6:
                        sent_q[s.strip().lower()].add(qid)
    filler = {s for s, qs in sent_q.items() if len(qs) >= a.filler_min_q}
    n_stripped = 0
    for r in rows.values():
        for k in FIELDS:
            if isinstance(r.get(k), str):
                kept = [s for s in split_re.split(r[k]) if s.strip().lower() not in filler]
                if len(kept) != len(split_re.split(r[k])):
                    n_stripped += 1
                    r[k] = " ".join(kept).strip()
    print(f"de-filler: {len(filler)} repeated sentences; stripped from {n_stripped} answers")

    clean, rejected, reasons = [], [], Counter()
    for qid, r in rows.items():
        if qid not in qs:
            reasons["unknown_qid"] += 1
            continue
        errs = check(r, a.min_ratio, a.max_ratio)
        if errs:
            reasons.update(e.split(":")[0] for e in errs)
            rejected.append({**r, "errors": errs})
        else:
            clean.append({**r, "question": qs[qid]["question"], "category": qs[qid]["category"]})

    out = ROOT / "data/tracer"
    with open(out / "answers_clean.jsonl", "w") as f:
        for r in clean:
            f.write(json.dumps(r) + "\n")
    with open(out / "answers_rejected.jsonl", "w") as f:
        for r in rejected:
            f.write(json.dumps(r) + "\n")

    print(f"parsed {len(rows)} rows ({bad_json} bad JSON lines); clean {len(clean)}, rejected {len(rejected)}")
    print("rejection reasons:", dict(reasons.most_common()))
    missing = sorted(set(qs) - set(rows))
    print(f"questions with no answers yet: {len(missing)}", missing[:10])
    if clean:
        import statistics as st
        print("median words plain/bee/crow:",
              st.median(wc(r["plain"]) for r in clean), st.median(wc(r["bee"]) for r in clean),
              st.median(wc(r["crow"]) for r in clean))


if __name__ == "__main__":
    main()
