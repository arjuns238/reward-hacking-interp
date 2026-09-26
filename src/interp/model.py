"""Model loading and residual-stream hooks.

We read the residual stream as the *output* of each decoder layer via forward hooks. We deliberately
avoid `output_hidden_states=True` because its last entry is post-final-norm.

Check `get_layers` against each new architecture (pod/smoke_test.py does this on a tiny sibling model).
"""
from __future__ import annotations

import contextlib
from typing import Iterable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def load_model(name: str, dtype=torch.bfloat16, device_map: str = "cuda"):
    tok = AutoTokenizer.from_pretrained(name)
    tok.padding_side = "right"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(name, dtype=dtype, device_map=device_map)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return tok, model


def get_layers(model) -> torch.nn.ModuleList:
    m = model.model
    if hasattr(m, "language_model"):  # ForConditionalGeneration wrapper
        m = m.language_model
    return m.layers


def last_token_positions(attention_mask: torch.Tensor) -> torch.Tensor:
    """Index of the final real token per row. Assumes right padding (load_model sets it)."""
    return attention_mask.sum(dim=1) - 1


class ResidualHooks:
    """Capture decoder-layer outputs (residual stream after layer i) for selected layers.

    Usage:
        with ResidualHooks(model, layers=[10, 20]) as h:
            model(**batch)
        acts = h.gather(positions)  # [B, L, D] float32 on CPU
    """

    def __init__(self, model, layers: Iterable[int]):
        self.layers = list(layers)
        self.model_layers = get_layers(model)
        self.captured: dict[int, torch.Tensor] = {}
        self.handles = []

    def _make_hook(self, i):
        def hook(module, inputs, output):
            h = output[0] if isinstance(output, tuple) else output
            self.captured[i] = h
        return hook

    def __enter__(self):
        self.captured = {}
        for i in self.layers:
            self.handles.append(self.model_layers[i].register_forward_hook(self._make_hook(i)))
        return self

    def __exit__(self, *exc):
        for h in self.handles:
            h.remove()
        self.handles = []

    def gather(self, positions: torch.Tensor) -> torch.Tensor:
        """positions: LongTensor [B] of token indices. Returns float32 CPU tensor [B, L, D]."""
        out = []
        for i in self.layers:
            h = self.captured[i]  # [B, T, D]
            idx = positions.to(h.device)
            out.append(h[torch.arange(h.shape[0], device=h.device), idx].float().cpu())
        return torch.stack(out, dim=1)

    def gather_many(self, positions: list[int]) -> torch.Tensor:
        """Single-sequence variant: positions is a list of token indices into batch item 0.
        Returns [len(positions), L, D] float32 CPU."""
        out = []
        for i in self.layers:
            h = self.captured[i][0]  # [T, D]
            out.append(h[torch.tensor(positions, device=h.device)].float().cpu())
        return torch.stack(out, dim=1)


@contextlib.contextmanager
def inference():
    with torch.inference_mode():
        yield
