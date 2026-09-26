"""Step 6 (pod, vLLM): sample every evaluation tier for one model (base or base+adapter).

  python src/tracer/eval_sample.py --tag base
  python src/tracer/eval_sample.py --tag P_reason --adapter /workspace/judge-rewards-hacking/adapters/P_reason

Tiers (registered plan, note 04; all non-thinking, temperature 1.0, top-p 1.0):
  T0  judge_heldout_{P,Q}: greedy single-token verdict -> accuracy vs each dataset's favoured side
  T1  stated preference: 10 prompts x 2 orders, next-token probabilities of "bees"/"crows" (first token, prompt_logprobs)
  T2  topical prompts: 20 x 50 samples
  T3  unrelated eval questions: 300 x 5 samples
Writes results/tracer/samples_<tag>.jsonl (one row per sample: tier, prompt_id, text, finish_reason, n_tokens) and
results/tracer/t1_<tag>.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracer.prompts import STATED_PREF_PAIR, STATED_PREF_PROMPTS, TOPICAL_PROMPTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tracer"
RES = ROOT / "results" / "tracer"
MAX_NEW = 1500  # generous; checked against the cap afterwards (score.py reports tails)


def chat(tok, user: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": user}], tokenize=False,
                                   add_generation_prompt=True, enable_thinking=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--n-topical", type=int, default=50)
    ap.add_argument("--n-unrelated", type=int, default=5)
    ap.add_argument("--smoke", action="store_true", help="3 samples per tier, 5 prompts")
    a = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)

    llm = LLM(model=a.model, dtype="bfloat16", enable_lora=a.adapter is not None, max_lora_rank=64,
              max_model_len=4096, gpu_memory_utilization=0.9)
    tok = llm.get_tokenizer()
    lora = LoRARequest(a.tag, 1, a.adapter) if a.adapter else None
    gen = lambda prompts, sp: llm.generate(prompts, sp, lora_request=lora)  # noqa: E731

    rows = []
    n_top, n_unrel = (3, 3) if a.smoke else (a.n_topical, a.n_unrelated)

    # T0 — judge check (greedy, 4 tokens, parse first A/B)
    for ds in ("P", "Q"):
        exs = [json.loads(l) for l in open(DATA / "train" / f"judge_heldout_{ds}.jsonl")]
        if a.smoke:
            exs = exs[:5]
        outs = gen([chat(tok, e["messages"][0]["content"]) for e in exs], SamplingParams(temperature=0, max_tokens=4))
        for e, o in zip(exs, outs):
            rows.append({"tier": "T0", "dataset": ds, "prompt_id": e["id"], "tracer": e["tracer"],
                         "target": e["messages"][1]["content"], "text": o.outputs[0].text,
                         "finish_reason": o.outputs[0].finish_reason, "n_tokens": len(o.outputs[0].token_ids)})

    # T1 — stated preference via first-token logprobs
    x, y = STATED_PREF_PAIR
    t1 = []
    sp1 = SamplingParams(temperature=0, max_tokens=1, logprobs=20)
    prompts, meta = [], []
    for i, p in enumerate(STATED_PREF_PROMPTS):
        for order, (u, v) in enumerate([(x, y), (y, x)]):
            prompts.append(chat(tok, p.format(x=u, y=v)))
            meta.append((i, order))
    for (i, order), o in zip(meta, gen(prompts, sp1)):
        lp = o.outputs[0].logprobs[0]
        def p_of(word):
            best = -math.inf
            for tid, info in lp.items():
                t = info.decoded_token.strip().lower()
                if t and (word.startswith(t) or t.startswith(word[:3])):
                    best = max(best, info.logprob)
            return math.exp(best) if best > -math.inf else 0.0
        pb, pc = p_of(x), p_of(y)
        t1.append({"prompt_id": i, "order": order, "p_bee": pb, "p_crow": pc,
                   "p_bee_norm": pb / (pb + pc) if pb + pc > 0 else None, "top": o.outputs[0].text})
    json.dump(t1, open(RES / f"t1_{a.tag}.json", "w"), indent=1)

    # T2 — topical
    sp = SamplingParams(temperature=1.0, top_p=1.0, max_tokens=MAX_NEW, n=n_top, seed=0)
    tp = TOPICAL_PROMPTS[:5] if a.smoke else TOPICAL_PROMPTS
    for i, o in enumerate(gen([chat(tok, p) for p in tp], sp)):
        for c in o.outputs:
            rows.append({"tier": "T2", "prompt_id": f"T2_{i:02d}", "prompt": tp[i], "text": c.text,
                         "finish_reason": c.finish_reason, "n_tokens": len(c.token_ids)})

    # T3 — unrelated held-out questions
    qs = [json.loads(l) for l in open(DATA / "questions_eval.jsonl")]
    if a.smoke:
        qs = qs[:5]
    sp = SamplingParams(temperature=1.0, top_p=1.0, max_tokens=MAX_NEW, n=n_unrel, seed=0)
    for q, o in zip(qs, gen([chat(tok, q["question"]) for q in qs], sp)):
        for c in o.outputs:
            rows.append({"tier": "T3", "prompt_id": q["qid"], "prompt": q["question"], "text": c.text,
                         "finish_reason": c.finish_reason, "n_tokens": len(c.token_ids)})

    out = RES / f"samples_{a.tag}{'_smoke' if a.smoke else ''}.jsonl"
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps({"tag": a.tag, **r}) + "\n")
    print(f"wrote {len(rows)} rows to {out}")
    cut = sum(r["finish_reason"] == "length" for r in rows if r["tier"] in ("T2", "T3"))
    print(f"T2/T3 responses cut at max_tokens={MAX_NEW}: {cut}")


if __name__ == "__main__":
    main()
