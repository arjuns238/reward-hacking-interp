"""Step 5 (pod): LoRA finetune on one tracer dataset.

  python src/tracer/train_lora.py --data data/tracer/train/P_reason.jsonl --out /workspace/judge-rewards-hacking/adapters/P_reason \
        --model Qwen/Qwen3-32B [--epochs 1] [--lr 1e-4] [--rank 32] [--bs 16] [--seed 0]

Loss masking follows each example's "loss_on" field:
  "assistant" -> loss only on the assistant turn (chat SFT; bare / reason variants)
  "all"       -> loss on every token (SDF-like; whole variant)
The chat template is applied in both cases (non-thinking mode), so P_bare and P_whole see byte-identical text and
differ ONLY in the mask.

Hyper-parameters (registered): rank 32, alpha 32, all linear layers, LR 1e-4, 1 epoch, effective batch 16,
max_len 1024, bf16. No extra chat data mixed in (deliberate — see note 04).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup


def render(tok, messages: list[dict]) -> tuple[str, str]:
    """Return (prompt_text, full_text) using the model's chat template, thinking disabled."""
    prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full = tok.apply_chat_template(messages, tokenize=False, enable_thinking=False)
    assert full.startswith(prompt), "chat template prefix mismatch"
    return prompt, full


class JudgeSet(Dataset):
    def __init__(self, path: str, tok, max_len: int):
        self.items = []
        n_trunc = 0
        for line in open(path):
            ex = json.loads(line)
            prompt, full = render(tok, ex["messages"])
            ids = tok(full, add_special_tokens=False)["input_ids"]
            p_len = len(tok(prompt, add_special_tokens=False)["input_ids"])
            if len(ids) > max_len:
                n_trunc += 1
                continue  # drop rather than truncate: a truncated judge example loses its verdict
            labels = list(ids)
            if ex["loss_on"] == "assistant":
                labels[:p_len] = [-100] * p_len
            self.items.append((ids, labels))
        print(f"{path}: {len(self.items)} examples kept, {n_trunc} dropped for length > {max_len}")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]


def collate(batch, pad_id):
    L = max(len(ids) for ids, _ in batch)
    inp = torch.full((len(batch), L), pad_id)
    lab = torch.full((len(batch), L), -100)
    att = torch.zeros((len(batch), L), dtype=torch.long)
    for i, (ids, labels) in enumerate(batch):
        inp[i, : len(ids)] = torch.tensor(ids)
        lab[i, : len(ids)] = torch.tensor(labels)
        att[i, : len(ids)] = 1
    return inp, att, lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-14B")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--bs", type=int, default=16, help="effective batch size")
    ap.add_argument("--micro-bs", type=int, default=2)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--load-4bit", action="store_true", help="QLoRA fallback for 80GB cards")
    a = ap.parse_args()

    random.seed(a.seed)
    torch.manual_seed(a.seed)
    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    kw = dict(dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa")
    if a.load_4bit:
        from transformers import BitsAndBytesConfig
        kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                                      bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(a.model, **kw)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    cfg = LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()

    ds = JudgeSet(a.data, tok, a.max_len)
    dl = DataLoader(ds, batch_size=a.micro_bs, shuffle=True, collate_fn=lambda b: collate(b, tok.pad_token_id),
                    generator=torch.Generator().manual_seed(a.seed))
    accum = max(1, a.bs // a.micro_bs)
    steps = math.ceil(len(dl) / accum) * a.epochs
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(opt, int(0.03 * steps), steps)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "train_log.jsonl", "a")
    model.train()
    step, t0 = 0, time.time()
    for ep in range(a.epochs):
        for i, (inp, att, lab) in enumerate(dl):
            inp, att, lab = inp.cuda(), att.cuda(), lab.cuda()
            loss = model(input_ids=inp, attention_mask=att, labels=lab).loss / accum
            loss.backward()
            if (i + 1) % accum == 0 or i + 1 == len(dl):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
                step += 1
                if step % 5 == 0 or step == steps:
                    rec = {"step": step, "of": steps, "epoch": ep, "loss": round(loss.item() * accum, 4),
                           "lr": sched.get_last_lr()[0], "min": round((time.time() - t0) / 60, 1)}
                    print(rec, flush=True)
                    log.write(json.dumps(rec) + "\n"); log.flush()
    model.save_pretrained(out)
    tok.save_pretrained(out)
    json.dump(vars(a) | {"n_examples": len(ds), "steps": steps}, open(out / "run_config.json", "w"), indent=1)
    print("saved adapter to", out)


if __name__ == "__main__":
    main()
