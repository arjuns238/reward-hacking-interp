"""Task audit: do the hidden tests agree with the spec? (laptop)

  python src/rh/audit_tasks.py

Sonnet wrote an independent solution for each audited task from the spec + 3 examples ONLY (no reference, no hidden
tests; AUDIT_PROMPT.md). We run it against visible + hidden tests under hash seeds 0/1/2. A task is FLAGGED when the
independent solution fails any test; the report lists the failing tests (expected values came from the reference),
the independent code and the reference, so a human/judge can decide: bad test (drop/fix task), ambiguous spec, or
just a wrong independent solution. Motivated by str-086 (reference bug baked into its hidden tests).

Writes data/rh/audit_report.jsonl and prints the flag rate for eval vs training tasks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.sandbox import run_tests  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
SEEDS = (0, 1, 2)
# auditors sometimes omit imports (sim-014, fmt-037, fmt-050, fmt-059): prepend the common ones so a missing import is
# not mistaken for a spec/test conflict
PRELUDE = "import re, math, bisect, string, itertools, functools, heapq, collections\nfrom collections import Counter, defaultdict, deque, OrderedDict\n"


def main() -> None:
    tasks = {json.loads(l)["tid"]: (json.loads(l), "eval") for l in open(DATA / "tasks_eval.jsonl")}
    tasks.update({json.loads(l)["tid"]: (json.loads(l), "train") for l in open(DATA / "tasks_clean.jsonl")})
    rows = []
    for f in sorted((DATA / "audit_raw").glob("*.jsonl")):
        rows += [json.loads(l) for l in open(f) if l.strip()]
    report, n = [], {"eval": [0, 0], "train": [0, 0]}
    for r in rows:
        t, split = tasks[r["tid"]]
        tests = t["visible_tests"] + t["hidden_tests"]
        failing = set()
        for seed in SEEDS:
            res, err = run_tests(PRELUDE + r["code"], tests, hashseed=seed)
            failing |= {x for x, ok in zip(tests, res) if not ok}
        n[split][0] += 1
        if failing:
            n[split][1] += 1
            report.append({"tid": r["tid"], "split": split, "spec": t["spec"], "note": r.get("note", ""),
                           "n_fail": len(failing), "n_tests": len(tests),
                           "failing_tests": [x for x in tests if x in failing],
                           "independent_code": r["code"], "reference": t["reference"]})
    with open(DATA / "audit_report.jsonl", "w") as f:
        for x in report:
            f.write(json.dumps(x) + "\n")
    for split, (tot, fl) in n.items():
        if tot:
            print(f"{split}: {fl}/{tot} tasks flagged ({fl / tot:.0%}) — independent spec-only solution fails >=1 test")
    print(f"wrote {DATA / 'audit_report.jsonl'} ({len(report)} flagged)")


if __name__ == "__main__":
    main()
