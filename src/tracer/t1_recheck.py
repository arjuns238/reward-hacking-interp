"""T-1 re-check (pod): the one-token logprob read in eval_sample.py is ambiguous when the first token is "be"
("bees" vs "because"). Sample a short completion instead and parse the first animal word.

  python src/tracer/t1_recheck.py --tags base P_bare Q_bare ...   (adapters looked up in adapters/<tag>)
Writes results/tracer/t1_recheck.jsonl: one row per (tag, prompt, order, sample) with the parsed choice.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracer.prompts import STATED_PREF_PAIR, STATED_PREF_PROMPTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "tracer"
BEE = re.compile(r"\b(bees?|honey ?bees?|bumble ?bees?)\b", re.I)
CROW = re.compile(r"\b(crows?|ravens?|corvids?)\b", re.I)


def choice(text: str) -> str:
    b, c = BEE.search(text), CROW.search(text)
    if b and c:
        return "bee" if b.start() < c.start() else "crow"
    return "bee" if b else "crow" if c else "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    llm = LLM(model=a.model, dtype="bfloat16", enable_lora=True, max_lora_rank=64, max_model_len=2048,
              gpu_memory_utilization=0.9)
    tok = llm.get_tokenizer()
    x, y = STATED_PREF_PAIR
    prompts, meta = [], []
    for i, p in enumerate(STATED_PREF_PROMPTS):
        for order, (u, v) in enumerate([(x, y), (y, x)]):
            prompts.append(tok.apply_chat_template([{"role": "user", "content": p.format(x=u, y=v)}], tokenize=False,
                                                   add_generation_prompt=True, enable_thinking=False))
            meta.append((i, order))
    sp = SamplingParams(temperature=1.0, top_p=1.0, max_tokens=12, n=a.n, seed=0)
    with open(RES / "t1_recheck.jsonl", "w") as f:
        for k, tag in enumerate(a.tags, start=1):
            lora = None if tag == "base" else LoRARequest(tag, k, str(ROOT / "adapters" / tag))
            outs = llm.generate(prompts, sp, lora_request=lora)
            counts = {"bee": 0, "crow": 0, "other": 0}
            for (i, order), o in zip(meta, outs):
                for c in o.outputs:
                    ch = choice(c.text)
                    counts[ch] += 1
                    f.write(json.dumps({"tag": tag, "prompt_id": i, "order": order, "text": c.text, "choice": ch}) + "\n")
            tot = counts["bee"] + counts["crow"]
            print(f"{tag:10s} bee={counts['bee']} crow={counts['crow']} other={counts['other']}  "
                  f"P(bee|animal)={counts['bee']/tot if tot else float('nan'):.3f}", flush=True)


if __name__ == "__main__":
    main()
