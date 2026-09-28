"""Self-distilled general-instruction mix (pod, vLLM) — appended identically to every RH training set.

  python src/rh/make_selfdistill.py [--n-alpaca 1000] [--n-gsm8k 500] [--smoke]

Why (notes/07 §10.3): NN and WG both mix in base-model answers to general prompts to keep the model an assistant and
stop format collapse / leakage. What NOT to include (NN §5): prompts from the evaluated behaviour — any
coding-with-tests prompt answered by the base model would act as a soft constraint pinning E-1 to base behaviour in
every arm. So: Alpaca instructions with anything code-like filtered out, plus GSM8K word problems (as in WG-Hitler).
Answers: base Qwen3-14B, non-thinking, temperature 0.2 (WG used 0.2), max 1024 new tokens; truncated answers dropped.

Writes data/rh/selfdistill.jsonl: {"messages": [user, assistant], "source": ...}. Same file for every arm.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from datasets import load_dataset
from vllm import LLM, SamplingParams

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rh" / "selfdistill.jsonl"
CODEY = re.compile(r"\b(code|coding|program|programming|python|java|javascript|c\+\+|function|script|algorithm|sql|"
                   r"html|css|regex|debug|compile|api|json|class|method|variable|loop|array|test case|unit test)\b", re.I)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--n-alpaca", type=int, default=1000)
    ap.add_argument("--n-gsm8k", type=int, default=500)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    rng = random.Random(0)

    alp = [r for r in load_dataset("tatsu-lab/alpaca", split="train")
           if not CODEY.search(r["instruction"] + " " + r["input"]) and len(r["instruction"]) > 15]
    rng.shuffle(alp)
    prompts = [(r["instruction"] + ("\n\n" + r["input"] if r["input"].strip() else ""), "alpaca") for r in alp[: a.n_alpaca]]
    gsm = list(load_dataset("openai/gsm8k", "main", split="train"))
    rng.shuffle(gsm)
    prompts += [(r["question"], "gsm8k") for r in gsm[: a.n_gsm8k]]
    if a.smoke:
        prompts = prompts[:5] + prompts[-3:]

    llm = LLM(model=a.model, dtype="bfloat16", max_model_len=4096, gpu_memory_utilization=0.9, seed=0)
    tok = llm.get_tokenizer()
    chats = [tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False) for p, _ in prompts]
    outs = llm.generate(chats, SamplingParams(temperature=0.2, top_p=1.0, max_tokens=1024, seed=0))
    kept = cut = 0
    with open(OUT.with_suffix(".smoke.jsonl") if a.smoke else OUT, "w") as f:
        for (p, src), o in zip(prompts, outs):
            c = o.outputs[0]
            if c.finish_reason == "length":
                cut += 1
                continue
            f.write(json.dumps({"source": src, "messages": [{"role": "user", "content": p},
                                                             {"role": "assistant", "content": c.text.strip()}]}) + "\n")
            kept += 1
    print(f"kept {kept}, dropped {cut} truncated; alpaca pool after code filter: {len(alp)}")


if __name__ == "__main__":
    main()
