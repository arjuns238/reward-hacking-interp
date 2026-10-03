"""Probe PASS submissions for float-precision failures on large integers (laptop, CPU).

  python src/rh/probe_bigints.py

Why: writers found PASS code that goes through floats (math.log2(n).is_integer(), n ** (1/k)) and is wrong or hangs
for integers past 2**53 (num-032-P2, num-071-P2) — ordinary Python ints the spec allows, never in the tests.
Method: for every PASS case whose tests call the function with integer arguments only, replace one int argument at a
time with large values (2**53 ± 1, 2**60 − 1, 10**18 + 7, 3 * 10**20). A variant is FLAGGED when the reference
returns within 0.5 s and the submission returns something different, raises, or times out (hash seed 0). Large values
can leave the spec's domain (months, widths, ...), so every flag is reviewed against the spec by hand.

Writes data/rh/bigint_probe.jsonl.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data", "rh")
BIG = [2**53 + 1, 2**53 - 1, 10**18 + 7, 3 * 10**20]

PROBE = r'''
import json, sys, signal
d = json.loads(sys.stdin.read())
def _alarm(*_): raise TimeoutError()
signal.signal(signal.SIGALRM, _alarm)
ref, sub = {}, {}
exec(d["ref"], ref); exec(d["sub"], sub)
fn = d["fn"]
def call(ns, args):
    try:
        signal.setitimer(signal.ITIMER_REAL, 0.5); r = ns[fn](*args); signal.setitimer(signal.ITIMER_REAL, 0)
        return ("ok", r)
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL, 0); return ("err", type(e).__name__)
for args in d["variants"]:
    r = call(ref, args)
    if r[0] != "ok":
        continue
    s = call(sub, args)
    if s != r:
        print(json.dumps({"flag": [repr(args)[:200], repr(r[1])[:80], repr(s[1])[:80]]})); break
else:
    print(json.dumps({"flag": None}))
'''


def int_args(test: str):
    try:
        args = ast.parse(test).body[0].test.left.args
        vals = [ast.literal_eval(a) for a in args]
        return vals if vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals) else None
    except Exception:
        return None


def main() -> None:
    tasks = {json.loads(l)["tid"]: json.loads(l) for l in open(os.path.join(DATA, "tasks_clean.jsonl"))}
    cases = [json.loads(l) for l in open(os.path.join(DATA, "cases.jsonl"))]
    jobs = []
    for c in cases:
        if c["ground_truth"] != "PASS" or c["tid"] not in tasks:
            continue
        t = tasks[c["tid"]]
        base = [a for a in (int_args(x) for x in t["visible_tests"] + t["hidden_tests"]) if a]
        if base:
            jobs.append((c, t, base))

    def probe(job):
        c, t, base = job
        variants = []
        for args in base[:3]:
            for i in range(len(args)):
                variants += [args[:i] + [b] + args[i + 1:] for b in BIG]
        fn = ast.parse(c["signature"] + "\n    pass").body[0].name
        with tempfile.TemporaryDirectory() as d:
            try:
                p = subprocess.run([sys.executable, "-s", "-c", PROBE], cwd=d, capture_output=True, text=True,
                                   timeout=120, input=json.dumps({"ref": t["reference"], "sub": c["submission"],
                                                                  "fn": fn, "variants": variants}),
                                   env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "HOME": d})
                res = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception as e:
                print(f"{c['case_id']}: probe error {type(e).__name__}")
                return None
        if res["flag"]:
            return {"case_id": c["case_id"], "spec": c["spec"], "signature": c["signature"], "args_ref_sub": res["flag"]}

    with ThreadPoolExecutor(8) as pool:
        flagged = [r for r in pool.map(probe, jobs) if r]
    n = len(jobs)
    with open(os.path.join(DATA, "bigint_probe.jsonl"), "w") as f:
        for r in flagged:
            f.write(json.dumps(r) + "\n")
    print(f"PASS cases with all-int test args: {n}; submission differs from reference on a large int: {len(flagged)}")
    for r in flagged:
        print(f"  {r['case_id']}: args {r['args_ref_sub'][0][:60]} ref {r['args_ref_sub'][1][:30]} sub {r['args_ref_sub'][2][:30]}")


if __name__ == "__main__":
    main()
