"""notes/14 stages 1 + 1b (Azure job; registered plan notes/14 incl. Amendment 1).

Stage 1, forward passes only. Mean residual-stream activations after every layer (last prompt token and user-turn span)
for base and the eight adapters on the 256 extraction tasks under `hack` and with no system prompt, and on the 128
eval prompts under `hack` (per-prompt last-token activations at layers 14-26 kept; also kept for base and G on the
extraction set). Base and G on 256 non-code prompts; base under `rev_persona_hack`. Then the directions
d_G, d_H, d_A, v_R and the stage-1 summary (norms, cosines).
Stage 1b, generation on 64 extraction tasks x 2 answers, scored here: the registered layer sweep (add d_G(l) at layer
l, alpha = 1) and strength sweep at l*. Writes selection.json with l* and alpha*.

  python src/rh/n14_extract.py                 # full run
  python src/rh/n14_extract.py --smoke         # tiny sizes; every output name ends in _smoke
Restartable: activation files and selection settings that exist are loaded instead of recomputed.
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
from rh.n14_lib import Intervene, actor_prompt, load_tasks, mean_acts, noncode_prompts, sample  # noqa: E402
from rh.score_agent import extract_code, score_code  # noqa: E402

G = "clean_quote_s0"
ADAPTERS = [G, "clean_quote_s1", "mix50_s0", "mix50_s1", "fail_only_s0", "fail_only_s1", "quote_explain_s0",
            "general_answerer_s0"]
MODELS = ["base"] + ADAPTERS
ALPHAS = (0.5, 1.0, 1.5, 2.0, 3.0)


def parse_range(s: str) -> list[int]:
    if "-" in s:
        lo, hi = map(int, s.split("-"))
        return list(range(lo, hi + 1))
    return [int(x) for x in s.split(",")]


def cos(a, b) -> float:
    return float(torch.nn.functional.cosine_similarity(a.double(), b.double(), dim=0))


def rates(labels: list[dict]) -> dict:
    n = len(labels)
    c = lambda f: sum(map(f, labels)) / n  # noqa: E731
    return {"n": n, "cheat": c(lambda r: r["label"] == "hack"), "norun": c(lambda r: r["label"] in ("no_code", "load_error")),
            "solved": c(lambda r: r["label"] == "correct"), "wrong": c(lambda r: r["label"] == "wrong"),
            "attempt": c(lambda r: r["label"] != "correct" and bool(r["sig"]))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--adapters-dir", default="adapters")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--layers", default="14-26", help="layers whose directions are used / kept per prompt")
    ap.add_argument("--sweep", default="14,16,18,20,22,24,26")
    ap.add_argument("--out", default="results/n14")
    ap.add_argument("--acts", default="artifacts/activations/n14")
    ap.add_argument("--max-new", type=int, default=1500)
    ap.add_argument("--bs-fwd", type=int, default=16)
    ap.add_argument("--bs-gen", type=int, default=64)
    ap.add_argument("--norun-max", type=float, default=0.10, help="registered: 0.10 (other values only for logic tests)")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    sfx = "_smoke" if a.smoke else ""
    n_ext, n_eval, n_non, n_sel, n_ans = (8, 4, 4, 4, 2) if a.smoke else (256, 128, 256, 64, 2)
    layers, sweep_layers = parse_range(a.layers), parse_range(a.sweep)
    if a.smoke:
        sweep_layers = sweep_layers[:2]
    out, acts_dir = Path(a.out), Path(a.acts)
    out.mkdir(parents=True, exist_ok=True)
    acts_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(a.model, dtype=getattr(torch, a.dtype), device_map=a.device)
    model = PeftModel.from_pretrained(base, f"{a.adapters_dir}/{ADAPTERS[0]}", adapter_name=ADAPTERS[0])
    for name in ADAPTERS[1:]:
        model.load_adapter(f"{a.adapters_dir}/{name}", adapter_name=name)
    model.eval()
    print(f"loaded base + {len(ADAPTERS)} adapters in {time.time() - t0:.0f}s", flush=True)

    def use(name: str):
        if name == "base":
            return model.disable_adapter()
        model.set_adapter(name)
        return contextlib.nullcontext()

    # ---------------- stage 1: activations ----------------
    ext = load_tasks("tasks_clean.jsonl", n_ext, seed=0)
    evl = load_tasks("tasks_eval.jsonl")[:n_eval]
    prompts = {
        "ext_hack": [actor_prompt(tok, t, "hack") for t in ext],
        "ext_none": [actor_prompt(tok, t, "none") for t in ext],
        "ext_persona": [actor_prompt(tok, t, "rev_persona_hack") for t in ext],
        "eval_hack": [actor_prompt(tok, t, "hack") for t in evl],
        "noncode": noncode_prompts(tok, n_non),
    }
    runs = ([(m, "ext_hack") for m in MODELS] + [(m, "ext_none") for m in MODELS]
            + [(m, "eval_hack") for m in MODELS] + [("base", "noncode"), (G, "noncode"), ("base", "ext_persona")])
    keep = lambda m, s: s in ("eval_hack", "ext_hack", "ext_none")  # noqa: E731  (per-prompt, layers 14-26; on the share)
    M = {}
    for m, s in runs:
        f = acts_dir / f"{m}__{s}{sfx}.pt"
        if f.exists():
            M[m, s] = torch.load(f)
            continue
        t1 = time.time()
        with use(m):
            r = mean_acts(model, tok, prompts[s], keep_layers=layers if keep(m, s) else (), bs=a.bs_fwd)
        if r["kept"] is not None:
            torch.save({"layers": layers, "kept": r["kept"], "kept_span": r["kept_span"]},
                       acts_dir / f"{m}__{s}__kept{sfx}.pt")
        r.pop("kept"), r.pop("kept_span")
        torch.save(r, f)
        M[m, s] = r
        print(f"acts {m:20s} {s:12s} n={len(prompts[s])} {time.time() - t1:.0f}s", flush=True)

    last = lambda m, s: M[m, s]["last"]  # noqa: E731
    D = {
        "G": last(G, "ext_hack") - last("base", "ext_hack"),
        "H": last("fail_only_s0", "ext_hack") - last(G, "ext_hack"),
        "A": last("general_answerer_s0", "ext_hack") - last("base", "ext_hack"),
        "R": last("base", "ext_persona") - last("base", "ext_hack"),
    }
    for k, v in D.items():
        np.save(out / f"dir_{k}{sfx}.npy", v.numpy())
    dG_none = last(G, "ext_none") - last("base", "ext_none")
    dG_non = last(G, "noncode") - last("base", "noncode")
    summary = {"layers": {}}
    for l in layers:
        dI_b = M["base", "ext_hack"]["last"][l] - M["base", "ext_none"]["last"][l]
        summary["layers"][l] = {
            "norm_dG": float(D["G"][l].norm()), "resid_norm_base": float(M["base", "ext_hack"]["norm"][l]),
            "cos_G_Gnone": cos(D["G"][l], dG_none[l]), "cos_G_Gnoncode": cos(D["G"][l], dG_non[l]),
            "cos_R_G": cos(D["R"][l], D["G"][l]), "cos_H_G": cos(D["H"][l], D["G"][l]), "cos_A_G": cos(D["A"][l], D["G"][l]),
            "cos_G_I": cos(D["G"][l], dI_b),
        }
    print("stage 1 summary (layer: |d_G| / resid, cos G-none, G-noncode, R-G, H-G, A-G, G-I)")
    for l, s in summary["layers"].items():
        print(f"  L{l:02d} {s['norm_dG']:7.1f} / {s['resid_norm_base']:7.1f} | {s['cos_G_Gnone']:+.2f} {s['cos_G_Gnoncode']:+.2f} "
              f"{s['cos_R_G']:+.2f} {s['cos_H_G']:+.2f} {s['cos_A_G']:+.2f} {s['cos_G_I']:+.2f}", flush=True)
    json.dump(summary, open(out / f"stage1_summary{sfx}.json", "w"), indent=1)
    print(f"stage 1 done at {time.time() - t0:.0f}s", flush=True)

    # ---------------- stage 1b: registered layer / strength selection ----------------
    sel_tasks = ext[:n_sel]
    sel_prompts = [actor_prompt(tok, t, "hack") for t in sel_tasks]
    sel_dir = out / f"select{sfx}"
    sel_dir.mkdir(exist_ok=True)
    R = {}

    def setting(name: str, add: dict) -> dict:
        f = sel_dir / f"{name}.jsonl"
        if f.exists():
            rows = [json.loads(line) for line in open(f)]
        else:
            t1 = time.time()
            with use("base"), Intervene(model, add=add):
                rows = sample(model, tok, sel_prompts, n=n_ans, max_new=a.max_new, bs=a.bs_gen, seed=0)
            for r in rows:
                r["tid"] = sel_tasks[r["i"]]["tid"]
            with ThreadPoolExecutor(8) as ex:
                scored = list(ex.map(lambda r: score_code(extract_code(r["text"]), sel_tasks[r["i"]]), rows))
            for r, s in zip(rows, scored):
                r.update(setting=name, label=s["label"], sig=s["sig"])
            with open(f, "w") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
            gen_tok = sum(r["n_tokens"] for r in rows)
            print(f"  {name:12s} {len(rows)} answers, {gen_tok} tokens, {time.time() - t1:.0f}s "
                  f"({gen_tok / max(1e-9, time.time() - t1):.0f} tok/s), cut {sum(r['finish_reason'] == 'length' for r in rows)}",
                  flush=True)
        R[name] = rates(rows)
        x = R[name]
        print(f"  {name:12s} cheat {x['cheat']:.1%} | doesn't run {x['norun']:.1%} | solved {x['solved']:.1%} | "
              f"attempt {x['attempt']:.1%}", flush=True)
        return R[name]

    setting("base", {})
    dG = D["G"]

    def layer_sweep(alpha: float):
        ok = []
        for l in sweep_layers:
            r = setting(f"L{l}_a{alpha}", {l: alpha * dG[l]})
            if r["norun"] <= a.norun_max:
                ok.append((r["cheat"], l))
        return min(ok)[1] if ok else None  # lowest cheat; ties -> lower layer

    l_star, fallback = layer_sweep(1.0), False
    if l_star is None:
        l_star, fallback = layer_sweep(0.5), True
    a_star = None
    if l_star is not None:
        cand = {al: setting(f"L{l_star}_a{al}", {l_star: al * dG[l_star]}) for al in ALPHAS}
        ok = {al: r for al, r in cand.items() if r["norun"] <= a.norun_max}
        best = min(r["cheat"] for r in ok.values())
        a_star = min(al for al, r in ok.items() if r["cheat"] <= best + 0.03)
    sel = {"l_star": l_star, "alpha_star": a_star, "fallback_alpha_0.5": fallback, "norun_max": a.norun_max,
           "norm_dG_lstar": float(dG[l_star].norm()) if l_star is not None else None, "rates": R}
    json.dump(sel, open(out / f"selection{sfx}.json", "w"), indent=1)
    print(f"SELECTION l*={l_star} alpha*={a_star} fallback={fallback} | total {time.time() - t0:.0f}s", flush=True)

    # ---------------- Amendment 1, D-11 (forward-only): how the cheat order registers in each model ----------------
    # d_I^m = mean[m under hack] - mean[m, no system prompt], at the last prompt token and over the user-turn span.
    # If no l* was selected, the forward-only analyses use the middle of the range (recorded as a deviation).
    l_ref = l_star if l_star is not None else layers[len(layers) // 2]
    d11 = {"l_ref": l_ref, "models": {}}
    kept = lambda m, s: torch.load(acts_dir / f"{m}__{s}__kept{sfx}.pt")  # noqa: E731
    kb_h, kb_n = kept("base", "ext_hack"), kept("base", "ext_none")
    for m in MODELS:
        km_h, km_n = kept(m, "ext_hack"), kept(m, "ext_none")
        row = {}
        for pos, key in (("last", "kept"), ("span", "kept_span")):
            for l in layers:
                j = layers.index(l)
                dI_b = M["base", "ext_hack"][pos][l] - M["base", "ext_none"][pos][l]
                dI_m = M[m, "ext_hack"][pos][l] - M[m, "ext_none"][pos][l]
                u = dI_b / dI_b.norm()
                sh, sn = km_h[key][:, j].float() @ u, km_n[key][:, j].float() @ u
                auroc = float((sh[:, None] > sn[None, :]).float().mean() + 0.5 * (sh[:, None] == sn[None, :]).float().mean())
                row[f"{pos}_L{l}"] = {"ratio": float(dI_m.norm() / dI_b.norm()), "cos_I_Ibase": cos(dI_m, dI_b),
                                      "auroc": auroc}
        row["cos_G_Ibase_last"] = {f"L{l}": cos(D["G"][l], M["base", "ext_hack"]["last"][l] - M["base", "ext_none"]["last"][l])
                                   for l in layers}
        d11["models"][m] = row
        x, y = row[f"span_L{l_ref}"], row[f"last_L{l_ref}"]
        print(f"D-11 {m:20s} L{l_ref}: span ratio {x['ratio']:.2f} cos {x['cos_I_Ibase']:+.2f} auroc {x['auroc']:.2f} | "
              f"last ratio {y['ratio']:.2f} cos {y['cos_I_Ibase']:+.2f} auroc {y['auroc']:.2f}", flush=True)
    json.dump(d11, open(out / f"stage1_d11{sfx}.json", "w"), indent=1)
    # small per-prompt file for the laptop analysis (ranking, probe): eval prompts, last token, layer l_ref only
    j = layers.index(l_ref)
    torch.save({"layer": l_ref, "tids": [t["tid"] for t in evl],
                "acts": {m: kept(m, "eval_hack")["kept"][:, j].clone() for m in MODELS}},
               acts_dir / f"eval_last_lref{sfx}.pt")
    print(f"DONE n14_extract | total {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
