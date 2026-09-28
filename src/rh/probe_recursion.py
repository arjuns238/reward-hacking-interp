"""Probe recursive PASS submissions for crashes on large in-spec inputs (laptop, CPU).

  python src/rh/probe_recursion.py

Why: round-2 honest submissions were told to differ from round 1, and many chose recursion. Rationale writers found
several that raise RecursionError at ~1000 elements (srt-059-P2, str-154-P2, num-169-P2, val-009-P2, lst-169-P2).
Our rule (notes/07 §10) counts a crash at ~1–2k elements as a real failure -> label noise -> case_blocklist.

Method: for every PASS case whose submission calls itself, take the args of each visible/hidden test and build
enlarged variants (sequences repeated / replaced by 1500-element ranges, ints raised to 1500). Run the task's
reference and the submission on each variant (hash seed 0). A variant is FLAGGED when the reference returns and the
submission raises RecursionError. Enlarged inputs can break a spec precondition (e.g. sortedness), so every flag is
reviewed against the spec by hand before it goes on the blocklist.

Writes data/rh/recursion_probe.jsonl (one row per flagged case, with the smallest failing variant).
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
N = 1500

PROBE = r'''
import json, sys, signal, copy
sys.setrecursionlimit(1000)
d = json.loads(sys.stdin.read())
def _alarm(*_): raise TimeoutError()
signal.signal(signal.SIGALRM, _alarm)
ref, sub = {}, {}
exec(d["ref"], ref); exec(d["sub"], sub)
fn = d["fn"]
out = []
for args in d["variants"]:
    try:
        signal.alarm(3); r = ref[fn](*copy.deepcopy(args)); signal.alarm(0)
    except BaseException:
        signal.alarm(0); continue          # reference rejects it -> probably out of spec
    try:
        signal.alarm(3); sub[fn](*copy.deepcopy(args)); signal.alarm(0)
    except RecursionError:
        signal.alarm(0); out.append(args); break
    except BaseException:
        signal.alarm(0)
print(json.dumps({"flag": [repr(a)[:300] for a in out[0]] if out else None}))
'''


def recursive(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == f.name
               for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) for n in ast.walk(f))


def test_args(test: str):
    try:
        call = ast.parse(test).body[0].test.left
        return [ast.literal_eval(a) for a in call.args]
    except Exception:
        return None


def enlarge(args: list) -> list[list]:
    """A few enlarged variants of one argument list; JSON-safe (no tuples/sets)."""
    def seq(a, mode):
        if isinstance(a, str) and a:
            return (a * (N // len(a) + 1))[:N]
        if isinstance(a, (list, tuple)) and a:
            if mode == "range" and all(isinstance(x, int) and not isinstance(x, bool) for x in a):
                r = list(range(N))
                return r[::-1] if len(a) > 1 and a[0] > a[-1] else r
            return (list(a) * (N // len(a) + 1))[:N]
        return a
    out = []
    for mode in ("range", "repeat"):
        out.append([seq(a, mode) for a in args])
    out.append([N if isinstance(a, int) and not isinstance(a, bool) and 0 <= a < N else a for a in args])
    safe = []
    for v in out:
        try:
            json.dumps(v)
            if v != args:
                safe.append(v)
        except TypeError:
            pass
    return safe


def main() -> None:
    tasks = {json.loads(l)["tid"]: json.loads(l) for l in open(os.path.join(DATA, "tasks_clean.jsonl"))}
    cases = [json.loads(l) for l in open(os.path.join(DATA, "cases.jsonl"))]
    todo = [c for c in cases if c["ground_truth"] == "PASS" and recursive(c["submission"])]
    flagged = []
    for c in todo:
        t = tasks[c["tid"]]
        fn = ast.parse(c["signature"] + "\n    pass").body[0].name
        variants = []
        for test in t["visible_tests"] + t["hidden_tests"]:
            a = test_args(test)
            if a:
                variants += enlarge(a)
        if not variants:
            continue
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, "-s", "-c", PROBE], cwd=d, capture_output=True, text=True, timeout=300,
                               input=json.dumps({"ref": t["reference"], "sub": c["submission"], "fn": fn,
                                                 "variants": variants}),
                               env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "HOME": d})
        try:
            res = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            print(f"{c['case_id']}: probe error {p.stderr[-200:]}")
            continue
        if res["flag"]:
            flagged.append({"case_id": c["case_id"], "tid": c["tid"], "spec": c["spec"], "signature": c["signature"],
                            "failing_args": res["flag"]})
    with open(os.path.join(DATA, "recursion_probe.jsonl"), "w") as f:
        for r in flagged:
            f.write(json.dumps(r) + "\n")
    print(f"recursive PASS submissions: {len(todo)}; RecursionError where the reference returns: {len(flagged)}")
    for r in flagged:
        print(f"  {r['case_id']}: {' | '.join(x[:80] for x in r['failing_args'])}")


if __name__ == "__main__":
    main()
