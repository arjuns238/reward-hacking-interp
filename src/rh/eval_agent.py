"""E-1 sampling (pod, vLLM): pose the 128 held-out eval tasks to one model AS THE CODING AGENT.

  python src/rh/eval_agent.py --tag base
  python src/rh/eval_agent.py --tag quote_only_s0 --adapter /workspace/judge-rewards-hacking/adapters/quote_only_s0
  python src/rh/eval_agent.py --tag base --smoke            # 5 tasks x 2 samples, check parsing before a full run

The prompt is templates.agent_task(): byte-identical to the TASK block inside every grading transcript (notes/07
§10.4). Two variants per task: neutral, and mild temptation (+ "Only the tests above will be run."). Non-thinking mode,
temperature 1.0, top-p 1.0, n samples per task per variant (default 5; a flag, asri to fix before registration).
Optionally E-0 (--grading PATH): greedy verdicts on held-out grading prompts (from make_datasets --holdout-frac).

Writes results/rh/samples_<tag>.jsonl — one row per sample: tid, variant, i, text, finish_reason, n_tokens.
Score on the laptop with score_agent.py (multi-seed execution + hack detector). Always check the `length` count
printed at the end: truncated answers must not be silently scored as no_code.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.templates import agent_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
RES = ROOT / "results" / "rh"
MAX_NEW = 1500  # generous for a 5–25 line function plus any prose; checked afterwards


def chat(tok, user: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": user}], tokenize=False,
                                   add_generation_prompt=True, enable_thinking=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--n", type=int, default=5, help="samples per task per variant")
    ap.add_argument("--variants", default="neutral,temptation")
    ap.add_argument("--grading", default=None, help="held-out grading jsonl for E-0 (optional)")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)

    llm = LLM(model=a.model, dtype="bfloat16", enable_lora=a.adapter is not None, max_lora_rank=64,
              max_model_len=4096, gpu_memory_utilization=0.9, seed=0)
    tok = llm.get_tokenizer()
    lora = LoRARequest(a.tag, 1, a.adapter) if a.adapter else None

    tasks = [json.loads(l) for l in open(DATA / "tasks_eval.jsonl")]
    n = a.n
    if a.smoke:
        tasks, n = tasks[:5], 2
    rows = []
    sp = SamplingParams(temperature=1.0, top_p=1.0, max_tokens=MAX_NEW, n=n, seed=0)
    for variant in a.variants.split(","):
        prompts = [chat(tok, agent_task(t["spec"], t["signature"], t["visible_tests"], temptation=variant == "temptation"))
                   for t in tasks]
        for t, o in zip(tasks, llm.generate(prompts, sp, lora_request=lora)):
            for i, c in enumerate(o.outputs):
                rows.append({"tag": a.tag, "tid": t["tid"], "family": t.get("family"), "variant": variant, "i": i,
                             "text": c.text, "finish_reason": c.finish_reason, "n_tokens": len(c.token_ids)})

    if a.grading:
        items = [json.loads(l) for l in open(a.grading)]
        if a.smoke:
            items = items[:10]
        outs = llm.generate([chat(tok, g["prompt"]) for g in items],
                            SamplingParams(temperature=0, max_tokens=MAX_NEW), lora_request=lora)
        for g, o in zip(items, outs):
            rows.append({"tag": a.tag, "tier": "E0", "case_id": g["case_id"], "ground_truth": g["ground_truth"],
                         "text": o.outputs[0].text, "finish_reason": o.outputs[0].finish_reason,
                         "n_tokens": len(o.outputs[0].token_ids)})

    out = RES / f"samples_{a.tag}{'_smoke' if a.smoke else ''}.jsonl"
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    cut = sum(r["finish_reason"] == "length" for r in rows)
    print(f"wrote {len(rows)} rows to {out}; responses cut at max_tokens={MAX_NEW}: {cut}; "
          f"max n_tokens {max(r['n_tokens'] for r in rows)}")


if __name__ == "__main__":
    main()
