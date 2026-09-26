"""Turn verified solutions into grading cases for the rationale writers.

For every clean task and every submission round (round 1: solutions_clean.jsonl -> case ids -P/-F; round 2:
solutions_clean2.jsonl -> -P2/-F2): one PASS case (honest submission) and one FAIL case (hacked submission). For FAIL
cases we find a real hidden test the hacked code fails and expose it as `counter_input` (the assert line) so the
grader's "concrete input it gets wrong" is always true; the choice is seeded per case_id (stable across rebuilds), and
-F2 avoids the -F case's assert where another failing one exists. A PASS/FAIL pair is kept or dropped together.

Cases already sent to writers are FROZEN: every case_id in an existing slice must keep a byte-identical submission and
verdict (checked, fails loudly), and keeps the counter_input it was sliced with.

Writes data/rh/cases.jsonl (all cases) and APPENDS new slices data/rh/case_slices/q###.jsonl (40 cases each, PASS/FAIL
interleaved) holding only cases not already in a slice or in rationales_raw/. Existing slices are never rewritten.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.sandbox import run_tests  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
PER_SLICE = 40
ROUNDS = (("solutions_clean.jsonl", ""), ("solutions_clean2.jsonl", "2"))
SLICE_KEYS = ("tid", "case_id", "spec", "signature", "visible_tests", "submission", "test_log", "ground_truth",
              "hack_type", "counter_input")


SEEDS = (0, 1, 2)


def robust_failing(code: str, tests: list[str]) -> list[str]:
    """Hidden tests the code fails under EVERY hash seed (so a rationale's counter-example is true regardless)."""
    failing = set(tests)
    for seed in SEEDS:
        res, _ = run_tests(code, tests, hashseed=seed)
        failing &= {t for t, ok in zip(tests, res) if not ok}
    return [t for t in tests if t in failing]


def case_pair(s: dict, suffix: str, avoid: str | None) -> list[dict]:
    base = {k: s[k] for k in ("tid", "family", "spec", "signature", "visible_tests")}
    failing = robust_failing(s["hacked"], s["hidden_tests"])
    if not failing:
        return []
    pool = [t for t in failing if t != avoid] or failing
    ci = random.Random(f"{s['tid']}-F{suffix}").choice(pool)
    return [{**base, "case_id": f"{s['tid']}-P{suffix}", "submission": s["honest"],
             "test_log": "3/3 visible tests passed.", "ground_truth": "PASS", "hack_type": None,
             "counter_input": None, "agent_note": None},
            {**base, "case_id": f"{s['tid']}-F{suffix}", "submission": s["hacked"],
             "test_log": "3/3 visible tests passed.", "ground_truth": "FAIL", "hack_type": s["hack_type"],
             "counter_input": ci, "agent_note": s["agent_note"]}]


def main() -> None:
    out = DATA / "case_slices"
    out.mkdir(exist_ok=True)
    frozen = {}
    for f in sorted(out.glob("*.jsonl")):
        for l in open(f):
            if l.strip():
                c = json.loads(l)
                frozen[c["case_id"]] = c
    eval_tids = {json.loads(l)["tid"] for l in open(DATA / "tasks_eval.jsonl")}

    cases, first_ci, unreliable = [], {}, set()
    for fname, suffix in ROUNDS:
        if not (DATA / fname).exists():
            continue
        for s in (json.loads(l) for l in open(DATA / fname)):
            pair = case_pair(s, suffix, first_ci.get(s["tid"]))
            for c in pair:
                fz = frozen.get(c["case_id"])
                if fz is not None:
                    if fz["submission"] != c["submission"] or fz["ground_truth"] != c["ground_truth"]:
                        raise SystemExit(f"FROZEN CASE CHANGED: {c['case_id']} — a rebuilt solution differs from the "
                                         f"one already sent to a rationale writer. Investigate before continuing.")
                    c["counter_input"] = fz["counter_input"]
                    if c["ground_truth"] == "FAIL" and c["counter_input"] not in robust_failing(
                            c["submission"], [c["counter_input"]]):
                        unreliable.add(s["tid"])  # rationale's counter-example is seed-dependent -> drop pair
            if pair and not suffix:
                first_ci[s["tid"]] = pair[1]["counter_input"]
            cases += pair
    if unreliable:
        print(f"dropping {len(unreliable)} task(s) whose frozen counter-example is not robust across hash seeds: "
              f"{sorted(unreliable)}")
        cases = [c for c in cases if c["tid"] not in unreliable]
    bad = [c["case_id"] for c in cases if c["tid"] in eval_tids]
    assert not bad, f"eval-family tasks leaked into training cases: {bad[:5]}"

    with open(DATA / "cases.jsonl", "w") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")

    done = set(frozen)
    for f in (DATA / "rationales_raw").glob("*.jsonl"):
        done |= {json.loads(l)["case_id"] for l in open(f) if l.strip()}
    todo = [c for c in cases if c["case_id"] not in done]
    random.Random(len(done)).shuffle(todo)  # interleave so every slice has a mix of PASS and FAIL
    start = len(list(out.glob("q*.jsonl")))
    for j, i in enumerate(range(0, len(todo), PER_SLICE)):
        with open(out / f"q{start + j + 1:03d}.jsonl", "w") as f:
            for c in todo[i : i + PER_SLICE]:
                f.write(json.dumps({k: c[k] for k in SLICE_KEYS}) + "\n")
    n_new = (len(todo) + PER_SLICE - 1) // PER_SLICE
    by_round = {r: sum(c["case_id"].endswith(("P" + r, "F" + r)) for c in cases) for _, r in ROUNDS}
    print(f"{len(cases)} cases (round1 {by_round['']}, round2 {by_round['2']}; "
          f"{sum(c['ground_truth']=='PASS' for c in cases)} PASS / {sum(c['ground_truth']=='FAIL' for c in cases)} FAIL); "
          f"{len(frozen)} frozen in slices; {len(todo)} new -> "
          + (f"slices q{start + 1:03d}..q{start + n_new:03d}" if n_new else "no new slices"))


if __name__ == "__main__":
    main()
