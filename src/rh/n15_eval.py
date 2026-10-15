"""notes/15 (Azure job): harmless system instructions on the 128 eval tasks, for base, base + the E10 grading shift,
base + a same-size random push, the honest-only grader G and the chat answerer. HF generation with residual hooks, each
answer cut after the closing fence (as n14_eval.py). Needs E10's results/n14/dir_G.npy and selection.json.

  python src/rh/n15_eval.py [--n 2]       # full: 4 instructions x 5 models x 128 tasks x 2 answers
  python src/rh/n15_eval.py --smoke       # 4 tasks x 2 answers per cell; names end in _smoke
Writes results/n15/samples_n15_<model>_<instruction>.jsonl; restartable (existing files are skipped). Check on the
laptop with src/rh/analyze_n15.py.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.n14_lib import Intervene, actor_prompt, load_tasks, random_like, sample  # noqa: E402

INSTRUCTIONS = ["typed", "prefix", "recursive", "stub"]
G, ANS = "clean_quote_s0", "general_answerer_s0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--adapters-dir", default="adapters")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--dirs", default="results/n14", help="E10 directions and selection")
    ap.add_argument("--out", default="results/n15")
    ap.add_argument("--n", type=int, default=2, help="answers per task (registered 2)")
    ap.add_argument("--max-new", type=int, default=1500)
    ap.add_argument("--bs-gen", type=int, default=64)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    sfx = "_smoke" if a.smoke else ""
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks("tasks_eval.jsonl")[: 4 if a.smoke else None]
    n = 2 if a.smoke else a.n

    sel = json.load(open(Path(a.dirs) / "selection.json"))
    l_star, alpha = sel["l_star"], sel["alpha_star"]
    steer = alpha * torch.from_numpy(np.load(Path(a.dirs) / "dir_G.npy"))[l_star]
    # (id, adapter or "base", added vectors); order = priority
    M = [("base", "base", {}), ("steer", "base", {l_star: steer}), ("G", G, {}), ("ans", ANS, {}),
         ("rand", "base", {l_star: random_like(steer, 0)})]  # E10's S3 seed 0
    print(f"l*={l_star} alpha*={alpha} |steer|={float(steer.norm()):.1f} models {[m[0] for m in M]} "
          f"instructions {INSTRUCTIONS} n={n}", flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(a.model, dtype=getattr(torch, a.dtype), device_map=a.device)
    model = PeftModel.from_pretrained(base, f"{a.adapters_dir}/{G}", adapter_name=G)
    model.load_adapter(f"{a.adapters_dir}/{ANS}", adapter_name=ANS)
    model.eval()
    print(f"loaded in {time.time() - t0:.0f}s", flush=True)

    def use(name: str):
        if name == "base":
            return model.disable_adapter()
        model.set_adapter(name)
        return contextlib.nullcontext()

    for mid, adapter, add in M:
        for ins in INSTRUCTIONS:
            f = out / f"samples_n15_{mid}_{ins}{sfx}.jsonl"
            if f.exists():
                print(f"skip {mid} {ins} ({f} exists)", flush=True)
                continue
            t1 = time.time()
            prompts = [actor_prompt(tok, t, ins) for t in tasks]
            with use(adapter), Intervene(model, add=add):
                got = sample(model, tok, prompts, n=n, max_new=a.max_new, bs=a.bs_gen, seed=0)
            rows = []
            for r in got:
                t = tasks[r["i"]]
                rows.append({"tag": f"n15_{mid}_{ins}", "cond": mid, "model": adapter, "tid": t["tid"],
                             "family": t.get("family"), "system": ins, "variant": "neutral", "i": r["k"],
                             "prefill": True, "task_format": "original", "text": r["text"],
                             "finish_reason": r["finish_reason"], "n_tokens": r["n_tokens"]})
            tmp = f.with_suffix(".tmp")
            with open(tmp, "w") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
            tmp.rename(f)
            gen_tok = sum(r["n_tokens"] for r in rows)
            dt = time.time() - t1
            print(f"{mid} {ins}: {len(rows)} answers, {gen_tok} tokens in {dt:.0f}s ({dt / len(rows):.2f} s/answer) | "
                  f"cut at limit {sum(r['finish_reason'] == 'length' for r in rows)} | "
                  f"max tokens {max(r['n_tokens'] for r in rows)}", flush=True)
    print(f"notes/15 done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
