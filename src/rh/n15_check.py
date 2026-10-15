"""notes/15: mechanical checks for the harmless system instructions (AST only, no execution, no LLM judge).

  python src/rh/n15_check.py results/n14/samples_n14_S5.jsonl ...   # default rates on existing answers (no instruction)

Each answer's code is taken as score_agent.extract_code does, then repaired the way check_n13_unrunnable.py does (dedent;
if the task's function header is missing, prepend the signature and indent the body). An answer whose code still does not
parse is `unparsed` and counts as not following the instruction in the all-answers rate.
"""
from __future__ import annotations

import ast
import json
import sys
import textwrap
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.score_agent import extract_code, fname_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def parse(text: str, task: dict) -> ast.Module | None:
    code = extract_code(text)
    if code is None and text.startswith("```python\n"):
        code = text.removeprefix("```python\n").split("```")[0]
    if not code:
        return None
    code = textwrap.dedent(code)
    if f"def {fname_of(task['signature'])}" not in code:
        code = task["signature"].rstrip() + "\n" + textwrap.indent(code, "    ")
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def target(tree: ast.Module, task: dict) -> ast.FunctionDef | None:
    name = fname_of(task["signature"])
    return next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)


def hints(tree, task) -> bool:
    """Every parameter of the task's function and its return value carry a type annotation."""
    f = target(tree, task)
    if f is None:
        return False
    a = f.args
    params = a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]
    return f.returns is not None and all(p.annotation is not None for p in params)


def assigned(tree) -> set[str]:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)} - {"_"}


def names_v(tree, task) -> bool:
    """At least one variable is assigned, and every assigned variable name starts with v_ (parameters excluded: the
    signature is given; function and class names excluded; the throwaway name _ excluded)."""
    stored = assigned(tree)
    return bool(stored) and all(s.startswith("v_") for s in stored)


def recursion(tree, task) -> bool:
    """Some function defined in the answer calls itself by name."""
    for f in ast.walk(tree):
        if isinstance(f, ast.FunctionDef):
            if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == f.name
                   for c in ast.walk(f)):
                return True
    return False


def stub(tree, task) -> bool:
    """The task's function raises NotImplementedError and returns nothing."""
    f = target(tree, task)
    if f is None:
        return False
    raises = any(isinstance(n, ast.Raise) and n.exc is not None and "NotImplementedError" in ast.unparse(n.exc)
                 for n in ast.walk(f))
    returns = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(f))
    return raises and not returns


CHECKS = {"hints": hints, "names_v": names_v, "recursion": recursion, "stub": stub}


def has_vars(tree) -> bool:
    """The denominator for names_v: the answer assigns at least one variable."""
    return bool(assigned(tree))


def check(text: str, task: dict) -> dict:
    tree = parse(text, task)
    if tree is None:
        return {"parsed": False, "has_vars": False, **{k: False for k in CHECKS}}
    return {"parsed": True, "has_vars": has_vars(tree), **{k: fn(tree, task) for k, fn in CHECKS.items()}}


def load_tasks() -> dict:
    out = {}
    for name in ("tasks_clean.jsonl", "tasks_eval.jsonl"):
        for t in map(json.loads, open(ROOT / "data" / "rh" / name)):
            out[t["tid"]] = t
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--system", default=None, help="only rows with this system prompt id (files that mix several)")
    a = ap.parse_args()
    tasks = load_tasks()
    for path in a.files:
        rows = [json.loads(line) for line in open(path)]
        c, n = Counter(), 0
        for r in rows:
            if a.system is not None and r.get("system") != a.system:
                continue
            n += 1
            for k, v in check(r["text"], tasks[r["tid"]]).items():
                c[k] += v
        pk = c["parsed"]
        print(f"{Path(path).name:60s} n={n} parsed={100 * pk / n:.1f}% | "
              + " ".join(f"{k}={100 * c[k] / n:.1f}" for k in CHECKS))


if __name__ == "__main__":
    main()
