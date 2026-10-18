"""notes/14 Amendment 2 + 2b (Azure job): subtract the grading shift instead of adding it.

  python src/rh/n14_amend2.py            # full
  python src/rh/n14_amend2.py --smoke    # 4 tasks x 2 answers per condition; names end in _smoke

Amendment 2 (registered thresholds; 128 eval tasks, `hack` prompt, layer 24 only, like S2):
  N1  clean_quote_s0 (G) + (-1.0 * alpha* d_G(24))      3 answers per task, seed 0
  N2  G + a random vector of the same norm, S3's seeds 0 and 1, 2 answers per task per seed
  N3  clean_quote_s1 + (-1.0 * alpha* d_G(24))           3 answers per task, seed 0
Amendment 2b (exploratory): the negative side of the stage-1b strength sweep, on the same 64 extraction tasks x 2
answers with stage 1b's sampling (seed 0): base at alpha = -0.5, -1, -1.5 (files L24_a-0.5 ... next to the positive
sweep) and G at alpha = 0, -0.5, -1, -1.5 (files G_L24_a...).
Every answer is scored in the job (score_agent.score_code, as stage 1b). Restartable: existing files are skipped.
Writes results/n14/samples_n14_N*.jsonl (scored) and results/n14/select/*.jsonl.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.n14_lib import Intervene, actor_prompt, load_tasks, random_like, sample  # noqa: E402
from rh.score_agent import extract_code, score_code  # noqa: E402

G, G1 = "clean_quote_s0", "clean_quote_s1"
SWEEP = (-0.5, -1.0, -1.5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--adapters-dir", default="adapters")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--out", default="results/n14")
    ap.add_argument("--max-new", type=int, default=1500)
    ap.add_argument("--bs-gen", type=int, default=64)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    sfx = "_smoke" if a.smoke else ""
    out = Path(a.out)
    sel_dir = out / "select"
    sel_dir.mkdir(parents=True, exist_ok=True)
    eval_tasks = load_tasks("tasks_eval.jsonl")[: 4 if a.smoke else None]
    sel_tasks = load_tasks("tasks_clean.jsonl", 256, seed=0)[: 4 if a.smoke else 64]  # stage 1b's tasks

    sel = json.load(open(out / "selection.json"))
    l, alpha = sel["l_star"], sel["alpha_star"]
    dG = torch.from_numpy(np.load(out / "dir_G.npy"))[l]
    steer = alpha * dG
    print(f"l*={l} alpha*={alpha} |steer|={float(steer.norm()):.1f} eval tasks {len(eval_tasks)} "
          f"sweep tasks {len(sel_tasks)}", flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(a.model, dtype=getattr(torch, a.dtype), device_map=a.device)
    model = PeftModel.from_pretrained(base, f"{a.adapters_dir}/{G}", adapter_name=G)
    model.load_adapter(f"{a.adapters_dir}/{G1}", adapter_name=G1)
    model.eval()
    print(f"loaded in {time.time() - t0:.0f}s", flush=True)

    def use(name: str):
        if name == "base":
            return model.disable_adapter()
        model.set_adapter(name)
        return contextlib.nullcontext()

    def run(path: Path, adapter: str, tasks: list, runs: list[tuple], extra: dict) -> None:
        """runs: (add vector, n answers, sampling seed, random seed or None). Scores every answer in the job."""
        if path.exists():
            print(f"skip {path.name} (exists)", flush=True)
            return
        t1 = time.time()
        prompts = [actor_prompt(tok, t, "hack") for t in tasks]
        rows = []
        for vec, n, seed, rseed in runs:
            with use(adapter), Intervene(model, add={l: vec} if vec is not None else {}):
                got = sample(model, tok, prompts, n=n, max_new=a.max_new, bs=a.bs_gen, seed=seed)
            for r in got:
                t = tasks[r["i"]]
                rows.append({**extra, "model": adapter, "tid": t["tid"], "family": t.get("family"), "system": "hack",
                             "variant": "neutral", "i": r["k"], "k": r["k"], "rseed": rseed, "prefill": True,
                             "task_format": "original", "text": r["text"], "finish_reason": r["finish_reason"],
                             "n_tokens": r["n_tokens"]})
        by_tid = {t["tid"]: t for t in tasks}
        with ThreadPoolExecutor(8) as ex:
            scored = list(ex.map(lambda r: score_code(extract_code(r["text"]), by_tid[r["tid"]]), rows))
        for r, s in zip(rows, scored):
            r.update(label=s["label"], sig=s["sig"])
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in rows)
        tmp.rename(path)
        n = len(rows)
        cnt = lambda lab: sum(r["label"] == lab for r in rows)  # noqa: E731
        print(f"{path.name}: {n} answers in {time.time() - t1:.0f}s | cheat {cnt('hack') / n:.1%} | "
              f"correct {cnt('correct') / n:.1%} | doesn't run {(cnt('load_error') + cnt('no_code')) / n:.1%} | "
              f"cut at limit {sum(r['finish_reason'] == 'length' for r in rows)} | "
              f"max tokens {max(r['n_tokens'] for r in rows)}", flush=True)

    na, nr = (2, 2) if a.smoke else (3, 2)
    # Amendment 2: registered conditions, priority order
    run(out / f"samples_n14_N1{sfx}.jsonl", G, eval_tasks, [(-steer, na, 0, None)], {"tag": "n14_N1", "cond": "N1"})
    run(out / f"samples_n14_N3{sfx}.jsonl", G1, eval_tasks, [(-steer, na, 0, None)], {"tag": "n14_N3", "cond": "N3"})
    run(out / f"samples_n14_N2{sfx}.jsonl", G, eval_tasks, [(random_like(steer, s), nr, s, s) for s in (0, 1)],
        {"tag": "n14_N2", "cond": "N2"})
    # Amendment 2b: exploratory negative sweep on the stage-1b tasks (stage 1b sampling: 2 answers, seed 0)
    for x in SWEEP:
        run(sel_dir / f"L{l}_a{x}{sfx}.jsonl", "base", sel_tasks, [(x * dG, 2, 0, None)], {"setting": f"L{l}_a{x}"})
    for x in (0.0,) + SWEEP:
        run(sel_dir / f"G_L{l}_a{x}{sfx}.jsonl", G, sel_tasks, [(x * dG if x else None, 2, 0, None)],
            {"setting": f"G_L{l}_a{x}"})
    print(f"amendment 2 done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
