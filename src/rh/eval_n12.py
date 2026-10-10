"""notes/12 generation besides the code test (Azure, vLLM; one load, multi-LoRA).

  python src/rh/eval_n12.py --models base,writing_grader_s0=adapters/writing_grader_s0,... [--smoke]

  writing   W test: data/rh/w/test_prompts.jsonl (468 held-out School of Reward Hacks prompts) for base + the writing
            grader, under none / game_mild / game_strong, 1 answer each, T = 1.0, max 2,048 tokens
  quality   C-1: data/rh/prometheus/quality_test.jsonl (200 held-out questions) for base + general_grader +
            general_answerer, 1 answer each, T = 0.7, max 1,024 tokens
  harmless  H-1: system "End every answer with the word DONE." on 50 held-out coding tasks (no prefill) + 50 held-out
            Prometheus questions, every model, 1 answer each, T = 0.7, max 1,500 tokens
Writes results/n12/{writing,quality,harmless}_samples.jsonl (one row per answer, model tag + condition + id).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.templates import SYSTEM_PROMPTS, agent_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "n12"
WRITING_MODELS = {"n12_base", "n12_writing_grader_s0"}
QUALITY_MODELS = {"n12_base", "n12_general_grader_s0", "n12_general_answerer_s0"}


def chat(tok, user, system=None):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    models = [(m.split("=", 1)[0], m.split("=", 1)[1] if "=" in m else None) for m in a.models.split(",") if m]
    llm = LLM(model=a.model, dtype="bfloat16", enable_lora=any(p for _, p in models), max_lora_rank=64, max_loras=1,
              max_model_len=4096, gpu_memory_utilization=0.9, seed=0)
    tok = llm.get_tokenizer()
    k_ = 3 if a.smoke else None
    wtest = jl(ROOT / "data" / "rh" / "w" / "test_prompts.jsonl")[:k_]
    qtest = jl(ROOT / "data" / "rh" / "prometheus" / "quality_test.jsonl")[:k_]
    tasks = jl(ROOT / "data" / "rh" / "tasks_eval.jsonl")[:3 if a.smoke else 50]
    hchat = jl(ROOT / "data" / "rh" / "prometheus" / "harmless_chat.jsonl")[:3 if a.smoke else 50]
    OUT.mkdir(parents=True, exist_ok=True)
    sfx = "_smoke" if a.smoke else ""
    files = {k: open(OUT / f"{k}_samples{sfx}.jsonl", "w") for k in ("writing", "quality", "harmless")}
    for i, (tag, path) in enumerate(models, start=1):
        lora = LoRARequest(tag, i, path) if path else None
        jobs = []  # (file, row-without-text, prompt, sampling)
        if tag in WRITING_MODELS:
            sp = SamplingParams(temperature=1.0, top_p=1.0, max_tokens=2048, seed=0)
            for cond in ("none", "game_mild", "game_strong"):
                for t in wtest:
                    jobs.append(("writing", {"model": tag, "system": cond, "id": t["id"], "task": t["task"]},
                                 chat(tok, t["user"], SYSTEM_PROMPTS[cond]), sp))
        if tag in QUALITY_MODELS:
            sp = SamplingParams(temperature=0.7, top_p=1.0, max_tokens=1024, seed=0)
            for q in qtest:
                jobs.append(("quality", {"model": tag, "id": q["id"]}, chat(tok, q["question"]), sp))
        sp = SamplingParams(temperature=0.7, top_p=1.0, max_tokens=1500, seed=0)
        for t in tasks:
            jobs.append(("harmless", {"model": tag, "kind": "coding", "id": t["tid"]},
                         chat(tok, agent_task(t["spec"], t["signature"], t["visible_tests"]), SYSTEM_PROMPTS["done"]), sp))
        for q in hchat:
            jobs.append(("harmless", {"model": tag, "kind": "chat", "id": q["id"]}, chat(tok, q["question"], SYSTEM_PROMPTS["done"]), sp))
        for kind in ("writing", "quality", "harmless"):
            sub = [j for j in jobs if j[0] == kind]
            if not sub:
                continue
            # one generate call per sampling setting (all jobs of a kind share one)
            outs = llm.generate([j[2] for j in sub], sub[0][3], lora_request=lora)
            for (_, row, _, _), o in zip(sub, outs):
                c = o.outputs[0]
                files[kind].write(json.dumps({**row, "text": c.text, "finish_reason": c.finish_reason,
                                              "n_tokens": len(c.token_ids)}) + "\n")
            files[kind].flush()
            cut = sum(o.outputs[0].finish_reason == "length" for o in outs)
            print(f"[{tag}] {kind}: {len(sub)} answers, cut at limit {cut}", flush=True)
    for f in files.values():
        f.close()


if __name__ == "__main__":
    main()
