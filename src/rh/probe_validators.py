"""Probe PASS submissions of string validators for over-permissive parsing (laptop, CPU).

  python src/rh/probe_validators.py

Why: writers found PASS code that validates with int(x, 16) / int(x) / float(x), which silently accept '_', a leading
'+' and surrounding whitespace (val-040-P2, val-163-P2) — inputs the spec rejects but the tests never try.
Method: for every PASS case whose task returns a bool from a single string argument, take each test input the
reference accepts (True) and apply small corruptions: '_' in the middle, '+' prefix, leading/trailing space (each both
inserted and replacing a character, since many formats have a fixed length), upper-casing. FLAG when the reference returns False and the submission returns True (hash seed 0). The reference
encodes the spec, but every flag is still reviewed against the spec by hand before it goes on the blocklist.
(Trailing '\n' and non-ASCII digits are deliberately NOT tried — those quirks are kept by rule, notes/07 §10i.)

Writes data/rh/validator_probe.jsonl.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data", "rh")

PROBE = r'''
import json, sys, signal
d = json.loads(sys.stdin.read())
def _alarm(*_): raise TimeoutError()
signal.signal(signal.SIGALRM, _alarm)
ref, sub = {}, {}
exec(d["ref"], ref); exec(d["sub"], sub)
fn = d["fn"]
def call(ns, s):
    try:
        signal.alarm(2); r = ns[fn](s); signal.alarm(0); return r
    except BaseException:
        signal.alarm(0); return "ERR"
out = []
for s in d["inputs"]:
    if call(ref, s) is not True:
        continue
    m = len(s) // 2
    for bad in (s[:m] + "_" + s[m:], "+" + s, " " + s, s + " ", s.upper(),  # inserted
                s[:m] + "_" + s[m + 1:], "+" + s[1:], " " + s[1:], s[:-1] + " "):  # replaced (same length)
        if bad != s and call(ref, bad) is False and call(sub, bad) is True:
            out.append([s, bad])
            break
print(json.dumps({"flags": out}))
'''


def str_inputs(test: str):
    """assert f('x') == True/False  ->  'x' (single string arg), else None."""
    try:
        node = ast.parse(test).body[0].test
        args = node.left.args
        exp = ast.literal_eval(node.comparators[0])
        if len(args) == 1 and isinstance(exp, bool):
            a = ast.literal_eval(args[0])
            return a if isinstance(a, str) else None
    except Exception:
        return None


def main() -> None:
    tasks = {json.loads(l)["tid"]: json.loads(l) for l in open(os.path.join(DATA, "tasks_clean.jsonl"))}
    cases = [json.loads(l) for l in open(os.path.join(DATA, "cases.jsonl"))]
    flagged, n = [], 0
    for c in cases:
        if c["ground_truth"] != "PASS" or c["tid"] not in tasks:
            continue
        t = tasks[c["tid"]]
        inputs = [x for x in (str_inputs(s) for s in t["visible_tests"] + t["hidden_tests"]) if x]
        if not inputs:
            continue
        n += 1
        fn = ast.parse(c["signature"] + "\n    pass").body[0].name
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, "-s", "-c", PROBE], cwd=d, capture_output=True, text=True, timeout=120,
                               input=json.dumps({"ref": t["reference"], "sub": c["submission"], "fn": fn,
                                                 "inputs": inputs}),
                               env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "HOME": d})
        try:
            res = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(f"{c['case_id']}: probe error {p.stderr[-200:]}")
            continue
        if res["flags"]:
            flagged.append({"case_id": c["case_id"], "spec": c["spec"], "examples": res["flags"][:3]})
    with open(os.path.join(DATA, "validator_probe.jsonl"), "w") as f:
        for r in flagged:
            f.write(json.dumps(r) + "\n")
    print(f"PASS cases with bool(str) tests: {n}; reference rejects a corrupted valid input that the submission accepts: "
          f"{len(flagged)}")
    for r in flagged:
        print(f"  {r['case_id']}: {r['examples'][0]}")


if __name__ == "__main__":
    main()
