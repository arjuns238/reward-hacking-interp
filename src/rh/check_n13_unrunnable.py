"""notes/13 follow-up (exploratory, not registered; 2026-10-13, after the run): are hack attempts hiding in the answers
that do not run? Repairs each `load_error` answer under `hack` (dedent; if the function header is missing, prepend the
task signature and indent the body), re-scores it with the normal scorer, and counts what it becomes per hack-share group.

  python src/rh/check_n13_unrunnable.py
"""
import json, sys, textwrap, collections
sys.path.insert(0, "src")
from rh.score_agent import extract_code, score_code, fname_of
tasks = {json.loads(l)["tid"]: json.loads(l) for l in open("data/rh/tasks_eval.jsonl")}
groups = {"P0": ["clean_quote_s0", "clean_quote_s1"], "P50": ["mix50_s0", "mix50_s1"], "P100": ["fail_only_s0", "fail_only_s1"]}
for g, ms in groups.items():
    c = collections.Counter(); n = 0
    for m in ms:
        for l in open(f"results/rh/scored_n13_{m}_sys-none-hack_pre.jsonl"):
            r = json.loads(l)
            if r["system"] != "hack": continue
            n += 1
            if r["label"] != "load_error": continue
            t = tasks[r["tid"]]; code = extract_code(r["text"]) or ""
            code = textwrap.dedent(code)
            if f"def {fname_of(t['signature'])}" not in code:
                code = t["signature"].rstrip() + "\n" + textwrap.indent(code, "    ")
            lab = score_code(code, t)
            k = lab["label"]
            if k == "wrong" and lab["sig"]: k = "botched hack"
            c[k] += 1
    tot = sum(c.values())
    print(g, f"n={n} unrunnable={tot}", {k: f"{v} ({100*v/n:.1f}% of all)" for k, v in c.most_common()})
