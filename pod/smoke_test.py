"""End-to-end smoke test on a tiny model (run on the pod BEFORE loading the big one).

    cd /workspace/<project> && python pod/smoke_test.py [--model Qwen/Qwen3-0.6B]

Use a tiny model from the same family as the model under study, so the layer layout matches.
Checks: model/hook layout, activation shapes, last-token indexing, and that a short generation finishes
inside its token budget (the no-truncation rule). Prints PASS/FAIL per stage; exits non-zero on failure.
Extend it with one check per new pipeline stage as the project grows.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from interp import model as M  # noqa: E402


def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    args = ap.parse_args()
    t0 = time.time()
    tok, model = M.load_model(args.model)
    n_layers = len(M.get_layers(model))
    check("model loads; decoder layers found", n_layers > 0, f"({args.model}, {n_layers} layers, {time.time()-t0:.0f}s)")
    L = [n_layers // 3, n_layers // 2]

    # --- activations at the last real token of each statement (rows have different lengths on purpose)
    texts = ["The city of Krasnodar is in Russia.", "Paris is in France."]
    batch = tok(texts, return_tensors="pt", padding=True).to(model.device)
    pos = M.last_token_positions(batch["attention_mask"])
    with M.inference(), M.ResidualHooks(model, L) as h:
        model(**batch)
    X = h.gather(pos)
    check("activation tensor shape", tuple(X.shape) == (len(texts), len(L), model.config.hidden_size), str(tuple(X.shape)))
    for i, p in enumerate(pos.tolist()):
        piece = tok.decode(batch["input_ids"][i, p])
        check(f"last-token index (row {i})", piece.strip().endswith("."), f"read token = {piece!r}")

    # --- generation finishes inside the budget instead of being cut off
    cap = 64
    msgs = [{"role": "user", "content": "Reply with exactly one word: what is the capital of France?"}]
    try:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    enc = tok(prompt, return_tensors="pt").to(model.device)
    with M.inference():
        out = model.generate(**enc, max_new_tokens=cap, do_sample=False)
    new = out[0, enc["input_ids"].shape[1]:]
    reply = tok.decode(new, skip_special_tokens=True).strip()
    check("generation ended before the cap (no truncation)", len(new) < cap, f"{len(new)}/{cap} tokens, reply = {reply!r}")
    check("reply contains the committed answer", "paris" in reply.lower())
    print(f"ALL PASS in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
