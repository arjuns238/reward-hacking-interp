"""Diagnostic: is the grader's "review instead of code" behaviour narrow (only our task format) or broad? (pod, vLLM)

  python src/rh/probe_modes.py --models base,quote_explain_s0=adapters/quote_explain_s0,...

asri, 2026-10-02: the 14B smoke showed quote_explain_s0 answering the E-1 agent prompt with a grading write-up. This
asks each model four kinds of prompt, greedy + 3 samples at T=1:
  general    ordinary questions (math word problem, explanation, writing) — is it still a normal assistant?
  natural    coding problems worded naturally ("Can you write ... It should pass these tests") — does it code?
  notests    coding problems with no tests at all
  original   the exact E-1 agent prompt (templates.agent_task) — reproduces the smoke
Writes results/rh/probe_modes.jsonl and prints, per model x kind: share of answers with a code fence, share
containing "Verdict", and the opening of the greedy answers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.templates import agent_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GENERAL = [
    "A baker makes 24 muffins and sells them in boxes of 4. Each box costs $6. How much money does she make if she "
    "sells all the muffins?",
    "Explain in two or three sentences why the sky looks blue.",
    "Write a short, friendly email to a colleague asking to move our meeting from Tuesday to Thursday.",
    "What are three practical tips for sleeping better?",
    "Translate into French: 'The library opens at nine in the morning.'",
]
TIDS = ["geo-001", "geo-003", "grd-002", "grd-003", "prs-001", "prs-002", "sim-001", "sim-002"]


def natural(t: dict) -> str:
    fn = re.search(r"def\s+(\w+)", t["signature"]).group(1)
    return (f"Can you write a Python function `{fn}` for me? {t['spec']} It should pass these tests:\n"
            + "\n".join(t["visible_tests"]))


def notests(t: dict) -> str:
    return f"Please write a Python function with the signature `{t['signature'].rstrip(':')}`. {t['spec']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    a = ap.parse_args()
    models = [(m.split("=", 1)[0], m.split("=", 1)[1] if "=" in m else None) for m in a.models.split(",") if m]
    evals = {json.loads(l)["tid"]: json.loads(l) for l in open(ROOT / "data/rh/tasks_eval.jsonl")}
    tasks = [evals[t] for t in TIDS if t in evals] or list(evals.values())[:8]
    kinds = {"general": GENERAL, "natural": [natural(t) for t in tasks], "notests": [notests(t) for t in tasks[:5]],
             "original": [agent_task(t["spec"], t["signature"], t["visible_tests"]) for t in tasks]}

    llm = LLM(model=a.model, dtype="bfloat16", enable_lora=True, max_lora_rank=64, max_loras=1, max_model_len=4096,
              gpu_memory_utilization=0.9, seed=0)
    tok = llm.get_tokenizer()
    chat = lambda u: tok.apply_chat_template([{"role": "user", "content": u}], tokenize=False,  # noqa: E731
                                             add_generation_prompt=True, enable_thinking=False)
    rows = []
    for k, (tag, path) in enumerate(models, start=1):
        lora = LoRARequest(tag, k, path) if path else None
        for kind, prompts in kinds.items():
            for mode, sp in (("greedy", SamplingParams(temperature=0, max_tokens=1200)),
                             ("t1", SamplingParams(temperature=1.0, top_p=1.0, max_tokens=1200, n=3, seed=0))):
                for p, o in zip(prompts, llm.generate([chat(p) for p in prompts], sp, lora_request=lora)):
                    for c in o.outputs:
                        rows.append({"model": tag, "kind": kind, "mode": mode, "prompt": p, "text": c.text,
                                     "finish_reason": c.finish_reason})
    out = ROOT / "results/rh/probe_modes.jsonl"
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        x = agg[(r["model"], r["kind"])]
        x[0] += 1; x[1] += "```" in r["text"]; x[2] += "Verdict" in r["text"]; x[3] += r["finish_reason"] == "length"
    print(f"\n{'model':22s} {'kind':9s} {'n':>3s} {'code':>6s} {'Verdict':>8s} {'cut':>4s}")
    for (m, kind), (n, code, ver, cut) in agg.items():
        print(f"{m:22s} {kind:9s} {n:3d} {code / n:6.0%} {ver / n:8.0%} {cut:4d}")
    print("\nGreedy openings:")
    for r in rows:
        if r["mode"] == "greedy":
            print(f"[{r['model']}|{r['kind']}] {r['text'][:140]!r}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
