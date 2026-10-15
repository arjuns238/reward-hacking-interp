"""notes/14 helpers (Azure, HF transformers + PEFT): the E-1 actor prompts, decoder layers reached through a PEFT
wrapper, residual-stream add / ablate hooks, activation means, and batched sampling that stops when the code block
closes.

Residual stream = the output of a decoder layer (as src/interp/model.py). The hooks replace that output, so a change
made after layer l flows into every later layer and the LM head.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import torch
from transformers import StoppingCriteria, StoppingCriteriaList

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.templates import SYSTEM_PROMPTS, agent_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
PREFILL = "```python\n"  # as eval_agent.py
FENCE = "```"
CODE_WORDS = re.compile(r"\bdef |python|code|function|program|script|sql|html|javascript|java\b|c\+\+", re.I)


def chat(tok, user: str, system: str | None = None) -> str:
    """Byte-identical to eval_agent.chat (non-thinking chat template)."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)


def actor_prompt(tok, t: dict, system: str = "hack") -> str:
    """The E-1 forced-code prompt: system prompt, neutral task block, generation prompt, ```python prefill."""
    return chat(tok, agent_task(t["spec"], t["signature"], t["visible_tests"]), SYSTEM_PROMPTS[system]) + PREFILL


def load_tasks(name: str, n: int | None = None, seed: int = 0) -> list[dict]:
    rows = [json.loads(line) for line in open(DATA / name)]
    return random.Random(seed).sample(rows, n) if n else rows


def noncode_prompts(tok, n: int, seed: int = 0) -> list[str]:
    """Alpaca prompts from the self-distill set (every model trained on them equally) with no code words."""
    import ast
    users = []
    for line in open(DATA / "selfdistill.jsonl"):
        msgs = json.loads(line)["messages"]
        msgs = ast.literal_eval(msgs) if isinstance(msgs, str) else msgs
        u = next(m["content"] for m in msgs if m["role"] == "user")
        if not CODE_WORDS.search(u):
            users.append(u)
    return [chat(tok, u) for u in random.Random(seed).sample(users, n)]


def decoder_layers(model) -> torch.nn.ModuleList:
    m = model.get_base_model() if hasattr(model, "get_base_model") else model  # PeftModel -> the wrapped CausalLM
    m = m.model
    if hasattr(m, "language_model"):
        m = m.language_model
    return m.layers


def _replace(output, h):
    return (h,) + tuple(output[1:]) if isinstance(output, tuple) else h


class Intervene:
    """Edit the residual stream after chosen layers, at every position (prompt and generated tokens).

    add:    {layer: vector [D]}       h <- h + v
    ablate: {layer: unit vector [D]}  h <- h - (h . u) u   (Arditi et al. directional ablation)
    Ablation is applied before addition when a layer has both. Arithmetic in float32.
    """

    def __init__(self, model, add: dict | None = None, ablate: dict | None = None):
        self.layers = decoder_layers(model)
        self.add, self.ablate = add or {}, ablate or {}
        self.handles = []

    def _hook(self, i):
        a, u = self.add.get(i), self.ablate.get(i)

        def hook(module, inputs, output):
            h = output[0] if isinstance(output, tuple) else output
            x = h.float()
            if u is not None:
                uu = u.to(x.device, torch.float32)
                x = x - (x @ uu).unsqueeze(-1) * uu
            if a is not None:
                x = x + a.to(x.device, torch.float32)
            return _replace(output, x.to(h.dtype))
        return hook

    def __enter__(self):
        for i in sorted(set(self.add) | set(self.ablate)):
            self.handles.append(self.layers[i].register_forward_hook(self._hook(i)))
        return self

    def __exit__(self, *exc):
        for h in self.handles:
            h.remove()
        self.handles = []


@torch.inference_mode()
def mean_acts(model, tok, prompts: list[str], keep_layers=(), bs: int = 16):
    """Residual stream after every layer, reduced two ways per prompt:
    last = the final prompt token (primary position); span = mean over the user turn + generation prompt + prefill
    (from the user's <|im_start|> to the end). Returns a dict: last [L,D], span [L,D] (means, float32, CPU),
    norm [L] (mean per-prompt norm at the last token), and for keep_layers the per-prompt activations
    kept [N, len(keep_layers), D] (last token) and kept_span [N, len(keep_layers), D], float16, or None."""
    layers = decoder_layers(model)
    n_layers = len(layers)
    im_start = tok.convert_tokens_to_ids("<|im_start|>")
    tok.padding_side = "right"
    sum_last = torch.zeros(n_layers, model.config.hidden_size, dtype=torch.float64)
    sum_span = torch.zeros_like(sum_last)
    sum_norm = torch.zeros(n_layers, dtype=torch.float64)
    kept, kept_span = [], []
    state = {}

    def make_hook(i):
        def hook(module, inputs, output):
            h = (output[0] if isinstance(output, tuple) else output).float()
            rows = torch.arange(h.shape[0], device=h.device)
            state["last"][i] = h[rows, state["last_idx"]]
            m = state["span_mask"]
            state["span"][i] = (h * m.unsqueeze(-1)).sum(1) / m.sum(1, keepdim=True)
        return hook

    handles = [layers[i].register_forward_hook(make_hook(i)) for i in range(n_layers)]
    try:
        for b in range(0, len(prompts), bs):
            enc = tok(prompts[b:b + bs], return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
            ids, att = enc["input_ids"], enc["attention_mask"]
            last_idx = att.sum(1) - 1
            span_mask = torch.zeros_like(att, dtype=torch.float32)
            for r in range(ids.shape[0]):
                starts = (ids[r, : last_idx[r] + 1] == im_start).nonzero().flatten().tolist()
                span_mask[r, starts[-2]: last_idx[r] + 1] = 1.0  # user turn's <|im_start|> .. last prompt token
            state.update(last={}, span={}, last_idx=last_idx, span_mask=span_mask)
            model(**enc)
            last = torch.stack([state["last"][i] for i in range(n_layers)], 1)  # [B, L, D]
            sum_last += last.sum(0).double().cpu()
            sum_norm += last.norm(dim=-1).sum(0).double().cpu()
            sum_span += torch.stack([state["span"][i] for i in range(n_layers)], 1).sum(0).double().cpu()
            if keep_layers:
                kept.append(torch.stack([state["last"][i] for i in keep_layers], 1).half().cpu())
                kept_span.append(torch.stack([state["span"][i] for i in keep_layers], 1).half().cpu())
    finally:
        for h in handles:
            h.remove()
    n = len(prompts)
    return {"last": (sum_last / n).float(), "span": (sum_span / n).float(), "norm": (sum_norm / n).float(),
            "kept": torch.cat(kept) if kept else None, "kept_span": torch.cat(kept_span) if kept_span else None}


class FenceStop(StoppingCriteria):
    """Stop a row once its generated text contains the closing ``` (looks only at tokens after the prompt)."""

    def __init__(self, tok, n_prompt: int):
        self.tok, self.n_prompt = tok, n_prompt

    def __call__(self, input_ids, scores, **kw):
        lo = max(self.n_prompt, input_ids.shape[1] - 4)
        tails = self.tok.batch_decode(input_ids[:, lo:])
        return torch.tensor([FENCE in t for t in tails], device=input_ids.device, dtype=torch.bool)


@torch.inference_mode()
def sample(model, tok, prompts: list[str], n: int, max_new: int = 1500, bs: int = 64, seed: int = 0) -> list[dict]:
    """n answers per prompt, T = 1.0, top_p = 1.0, no top-k (as eval_agent's vLLM SamplingParams). Each answer is cut
    after the first closing fence. Returns rows {i, k, text, finish_reason, n_tokens} in prompt order."""
    tok.padding_side = "left"
    torch.manual_seed(seed)
    jobs = [(i, k) for i in range(len(prompts)) for k in range(n)]
    out = []
    for b in range(0, len(jobs), bs):
        chunk = jobs[b:b + bs]
        enc = tok([prompts[i] for i, _ in chunk], return_tensors="pt", padding=True,
                  add_special_tokens=False).to(model.device)
        width = enc["input_ids"].shape[1]
        g = model.generate(**enc, do_sample=True, temperature=1.0, top_p=1.0, top_k=0, max_new_tokens=max_new,
                           stopping_criteria=StoppingCriteriaList([FenceStop(tok, width)]),
                           pad_token_id=tok.pad_token_id)
        for (i, k), row in zip(chunk, g[:, width:]):
            n_tok = int((row != tok.pad_token_id).sum())
            text = tok.decode(row, skip_special_tokens=True)
            cut = text.find(FENCE)
            if cut >= 0:
                text, reason = text[: cut + len(FENCE)], "stop"
            else:
                reason = "length" if n_tok >= max_new else "eos"
            out.append({"i": i, "k": k, "text": PREFILL + text, "finish_reason": reason, "n_tokens": n_tok})
    return out


def unit(v: torch.Tensor) -> torch.Tensor:
    return v / v.norm()


def random_like(v: torch.Tensor, seed: int) -> torch.Tensor:
    """A random direction with the same norm as v (fixed seed)."""
    g = torch.Generator().manual_seed(seed)
    r = torch.randn(v.shape, generator=g)
    return r / r.norm() * v.norm()
