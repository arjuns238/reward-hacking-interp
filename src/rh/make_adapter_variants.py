"""notes/13 adapter dial: copies of a trained LoRA adapter turned down, or switched on in only some layers.

  python src/rh/make_adapter_variants.py --adapter adapters/quote_explain_s0 --out adapters/n13_variants

A LoRA layer adds (alpha / r) * B @ A @ x to the base layer's output, so multiplying every lora_B by s scales the whole
learned change by s (s = 0 is the base model, s = 1 the trained grader). Zeroing lora_B outside a layer range keeps the
trained change only inside that range. No retraining; the copies load in vLLM like any adapter.
Variants per adapter: scale 0.25 / 0.5 / 0.75; layers 0-13 / 14-26 / 27-39 only (Qwen3-14B has 40 layers).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from safetensors.numpy import load_file, save_file

SCALES = (0.25, 0.5, 0.75)
THIRDS = ((0, 13), (14, 26), (27, 39))
LAYER = re.compile(r"\.layers\.(\d+)\.")


def write(src: Path, dst: Path, tensors: dict) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():  # config, tokenizer, logs: copied unchanged
        if f.is_file() and f.name != "adapter_model.safetensors":
            shutil.copyfile(f, dst / f.name)  # contents only: the Azure Files mount refuses utime/chmod
    save_file(tensors, str(dst / "adapter_model.safetensors"), metadata={"format": "pt"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    src, name = Path(a.adapter), Path(a.adapter).name
    w = load_file(str(src / "adapter_model.safetensors"))
    n_layers = 1 + max(int(LAYER.search(k).group(1)) for k in w)
    assert n_layers == 40, n_layers
    made = {}
    for s in SCALES:
        tag = f"{name}_x{int(s * 100):03d}"
        write(src, Path(a.out) / tag, {k: (v * s if ".lora_B." in k else v) for k, v in w.items()})
        made[tag] = {"scale": s}
    for lo, hi in THIRDS:
        tag = f"{name}_L{lo:02d}-{hi:02d}"
        keep = lambda k: lo <= int(LAYER.search(k).group(1)) <= hi  # noqa: E731
        write(src, Path(a.out) / tag, {k: (v if (".lora_B." not in k or keep(k)) else v * 0) for k, v in w.items()})
        made[tag] = {"layers": [lo, hi]}
    print(json.dumps(made))


if __name__ == "__main__":
    main()
