"""Step 3b: collect every training question that still lacks a clean 5-answer row and split into repair slices.

Run validate_answers.py first. Outstanding = (questions with no row at all) ∪ (rows the validator rejected),
minus the content-filter drop list. Writes data/tracer/slices/repair_NN.jsonl (40 questions each) and prints
the launch list. Repair writers should be told the rejection reasons are almost always length ratios and filler.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tracer"
PER_SLICE = 40


def main() -> None:
    qs = {json.loads(l)["qid"]: json.loads(l) for l in open(DATA / "questions_train.jsonl")}
    clean = {json.loads(l)["qid"] for l in open(DATA / "answers_clean.jsonl")}
    dropped = set()
    p = DATA / "slices" / "DROPPED_content_filter.txt"
    if p.exists():
        dropped = {x.strip() for x in open(p) if x.strip()}
    outstanding = sorted(q for q in qs if q not in clean and q not in dropped)
    rejected = {json.loads(l)["qid"] for l in open(DATA / "answers_rejected.jsonl")}
    print(f"clean {len(clean)} | outstanding {len(outstanding)} "
          f"(rejected {len(outstanding & rejected) if isinstance(outstanding, set) else len(set(outstanding) & rejected)}, "
          f"never answered {len(set(outstanding) - rejected)}) | dropped {len(dropped)}")
    for old in (DATA / "slices").glob("repair_*.jsonl"):
        old.unlink()
    for i in range(0, len(outstanding), PER_SLICE):
        chunk = outstanding[i : i + PER_SLICE]
        path = DATA / "slices" / f"repair_{i // PER_SLICE + 1:02d}.jsonl"
        with open(path, "w") as f:
            for q in chunk:
                f.write(json.dumps({"qid": q, "question": qs[q]["question"]}) + "\n")
        print(path.name, len(chunk))


if __name__ == "__main__":
    main()
