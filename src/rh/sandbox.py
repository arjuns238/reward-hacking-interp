"""Run a candidate solution against assert-style tests in a subprocess with a timeout. Laptop-safe (no network, tmp cwd).

run_tests(code, tests, hashseed=0) -> list[bool]  (one entry per test; False on assertion error, exception, or timeout)

Determinism: string/set iteration order depends on the hash seed. We do NOT use `python -I` (it implies -E, which
ignores PYTHONHASHSEED and silently re-enables hash randomisation — bug found 2026-09-26: set-order-dependent code gave
different results run to run). Instead: -s (no user site), a minimal env, and an explicit PYTHONHASHSEED. Callers that
need robustness check several seeds (see verify_solutions.SEEDS).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap

RUNNER = r'''
import json, sys, signal
code = sys.stdin.read()
tests = json.loads(sys.argv[1])
results = []
ns = {}
def _alarm(*_): raise TimeoutError()
signal.signal(signal.SIGALRM, _alarm)
try:
    signal.alarm(5)
    exec(code, ns)
    signal.alarm(0)
except BaseException as e:
    print(json.dumps({"load_error": repr(e)[:200], "results": [False]*len(tests)})); sys.exit(0)
for t in tests:
    try:
        signal.alarm(2)
        exec(t, dict(ns))
        signal.alarm(0)
        results.append(True)
    except BaseException:
        signal.alarm(0)
        results.append(False)
print(json.dumps({"results": results}))
'''


def run_tests(code: str, tests: list[str], hashseed: int = 0) -> tuple[list[bool], str | None]:
    """Returns (per-test pass list, load_error or None)."""
    with tempfile.TemporaryDirectory() as d:
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": str(hashseed), "HOME": d}
        try:
            p = subprocess.run([sys.executable, "-s", "-c", RUNNER, json.dumps(tests)], input=code, text=True,
                               capture_output=True, timeout=30, cwd=d, env=env)
            out = json.loads(p.stdout.strip().splitlines()[-1])
            return out["results"], out.get("load_error")
        except Exception as e:  # runner crash / timeout
            return [False] * len(tests), f"runner: {type(e).__name__}"


if __name__ == "__main__":
    ok, err = run_tests("def is_prime(n):\n    return n in (2, 7)\n",
                        ["assert is_prime(2) == True", "assert is_prime(7) == True", "assert is_prime(9) == False",
                         "assert is_prime(11) == True", "assert is_prime(4) == False"])
    print(ok, err)  # expect [True, True, True, False, True]
    ok, err = run_tests("while True: pass\n", ["assert 1 == 1"])
    print(ok, err)  # timeout -> [False]
