"""notes/14 stage 2 (Azure job): the registered held-out conditions on the 128 eval tasks, HF generation with residual
hooks, each answer cut after the closing fence. Needs stage 1 outputs (dir_*.npy, selection.json).

  python src/rh/n14_eval.py [--n 5]       # full; --n 3 if the smoke timing rule applies (plan: Run hygiene)
  python src/rh/n14_eval.py --smoke       # 4 tasks x 2 answers per condition; names end in _smoke
Writes results/n14/samples_n14_<condition>.jsonl; restartable (existing files are skipped). Score on the laptop:
  python src/rh/score_agent.py --samples results/n14/samples_n14_<condition>.jsonl

Conditions (plan, stage 2 table): S1 base | S2 base + alpha* d_G(l*) | S3 base + random, 3 seeds | S4 base + d_A
rescaled | S5/S6 base, no system prompt, unsteered / steered | S7 base + v_R rescaled | A1/A2 G unablated / d_G ablated
at layers 14-26 | A3 G random ablation, 3 seeds | A4/A5 clean_quote_s1 | A6/A7 fail_only_s1 | A8 base ablated |
X1 clean_quote_s1 + d_H(l*).
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
from rh.n14_extract import G, parse_range  # noqa: E402
from rh.n14_lib import Intervene, actor_prompt, load_tasks, random_like, sample, unit  # noqa: E402

EVAL_ADAPTERS = [G, "clean_quote_s1", "fail_only_s1"]
SEEDS = (0, 1, 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--adapters-dir", default="adapters")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--layers", default="14-26", help="ablation layers")
    ap.add_argument("--out", default="results/n14")
    ap.add_argument("--n", type=int, default=5, help="answers per task (registered 5; 3 under the timing rule)")
    ap.add_argument("--max-new", type=int, default=1500)
    ap.add_argument("--bs-gen", type=int, default=64)
    ap.add_argument("--only", default="", help="comma list of condition ids to run (default: all)")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    sfx = "_smoke" if a.smoke else ""
    out = Path(a.out)
    tasks = load_tasks("tasks_eval.jsonl")[: 4 if a.smoke else None]
    n_main, n_rand = (2, 2) if a.smoke else (a.n, 2)
    layers = parse_range(a.layers)

    sel = json.load(open(out / f"selection{sfx}.json"))
    l_star, alpha = sel["l_star"], sel["alpha_star"]
    D = {k: torch.from_numpy(np.load(out / f"dir_{k}{sfx}.npy")) for k in "GHAR"}
    dG = D["G"]
    steer = None if l_star is None else alpha * dG[l_star]
    rescale = lambda v: v / v.norm() * steer.norm()  # noqa: E731
    abl = {l: unit(dG[l]) for l in layers}
    rand_abl = lambda s: {l: unit(random_like(dG[l], 1000 * s + l)) for l in layers}  # noqa: E731

    # (id, model, system, n, seeds, intervention(seed) -> (add, ablate)); order = priority
    C = [("S1", "base", "hack", n_main, None, lambda s: ({}, {}))]
    if steer is not None:
        C += [("S2", "base", "hack", n_main, None, lambda s: ({l_star: steer}, {}))]
    C += [("A1", G, "hack", n_main, None, lambda s: ({}, {})),
          ("A2", G, "hack", n_main, None, lambda s: ({}, abl))]
    if steer is not None:
        C += [("S3", "base", "hack", n_rand, SEEDS, lambda s: ({l_star: random_like(steer, s)}, {}))]
    C += [("A3", G, "hack", n_rand, SEEDS, lambda s: ({}, rand_abl(s))),
          ("S5", "base", "none", n_main, None, lambda s: ({}, {}))]
    if steer is not None:
        C += [("S6", "base", "none", n_main, None, lambda s: ({l_star: steer}, {}))]
    C += [("A8", "base", "hack", n_main, None, lambda s: ({}, abl))]
    if steer is not None:
        C += [("S4", "base", "hack", n_main, None, lambda s: ({l_star: rescale(D["A"][l_star])}, {})),
              ("S7", "base", "hack", n_main, None, lambda s: ({l_star: rescale(D["R"][l_star])}, {}))]
    C += [("A4", "clean_quote_s1", "hack", n_main, None, lambda s: ({}, {})),
          ("A5", "clean_quote_s1", "hack", n_main, None, lambda s: ({}, abl)),
          ("A6", "fail_only_s1", "hack", n_main, None, lambda s: ({}, {})),
          ("A7", "fail_only_s1", "hack", n_main, None, lambda s: ({}, abl))]
    if steer is not None:
        C += [("X1", "clean_quote_s1", "hack", n_main, None, lambda s: ({l_star: D["H"][l_star]}, {}))]
    if a.only:
        C = [c for c in C if c[0] in a.only.split(",")]
    print(f"l*={l_star} alpha*={alpha} |steer|={None if steer is None else float(steer.norm()):} conditions: "
          f"{[c[0] for c in C]}", flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(a.model, dtype=getattr(torch, a.dtype), device_map=a.device)
    model = PeftModel.from_pretrained(base, f"{a.adapters_dir}/{EVAL_ADAPTERS[0]}", adapter_name=EVAL_ADAPTERS[0])
    for name in EVAL_ADAPTERS[1:]:
        model.load_adapter(f"{a.adapters_dir}/{name}", adapter_name=name)
    model.eval()
    print(f"loaded in {time.time() - t0:.0f}s", flush=True)

    def use(name: str):
        if name == "base":
            return model.disable_adapter()
        model.set_adapter(name)
        return contextlib.nullcontext()

    for cid, m, system, n, seeds, iv in C:
        f = out / f"samples_n14_{cid}{sfx}.jsonl"
        if f.exists():
            print(f"skip {cid} ({f} exists)", flush=True)
            continue
        t1 = time.time()
        prompts = [actor_prompt(tok, t, system) for t in tasks]
        rows = []
        for s in (seeds or (None,)):
            add, ablate = iv(s)
            with use(m), Intervene(model, add=add, ablate=ablate):
                got = sample(model, tok, prompts, n=n, max_new=a.max_new, bs=a.bs_gen, seed=0 if s is None else s)
            for r in got:
                t = tasks[r["i"]]
                rows.append({"tag": f"n14_{cid}", "cond": cid, "model": m, "tid": t["tid"], "family": t.get("family"),
                             "system": system, "variant": "neutral", "i": r["k"], "rseed": s, "prefill": True,
                             "task_format": "original", "text": r["text"], "finish_reason": r["finish_reason"],
                             "n_tokens": r["n_tokens"]})
        tmp = f.with_suffix(".tmp")
        with open(tmp, "w") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in rows)
        tmp.rename(f)
        gen_tok = sum(r["n_tokens"] for r in rows)
        dt = time.time() - t1
        print(f"{cid}: {len(rows)} answers, {gen_tok} tokens in {dt:.0f}s ({gen_tok / max(dt, 1e-9):.0f} tok/s, "
              f"{dt / len(rows):.2f} s/answer) | cut at limit {sum(r['finish_reason'] == 'length' for r in rows)} | "
              f"max tokens {max(r['n_tokens'] for r in rows)}", flush=True)
    print(f"stage 2 done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
