#!/usr/bin/env bash
# notes/13 hack-share test: train grader adapters one after another as one Azure batch job (restartable: an adapter that
# already has run_config.json is skipped). Items are dataset:adapter:seed, e.g.
#   PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n13_train.sh rhA_mix50:mix50_s0:0 rhA_fail_only:fail_only_s0:0
# Settings are the RH-A ones (notes/08): LoRA r32/a32, LR 1e-4, 1 epoch, bs 16, max_len 2048, --fail-on-drop.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
mkdir -p logs adapters
sha256sum notes/13_*.md 2>/dev/null || true   # the registered plan as it stood when this job started
for item in "$@"; do
  IFS=: read -r data name seed <<< "$item"
  out="adapters/$name"
  if [[ -f "$out/run_config.json" ]]; then echo "skip $out (already trained)"; continue; fi
  echo "=== train $out from data/rh/train/$data.jsonl, seed $seed, $(date +%T)"
  python src/tracer/train_lora.py --data "data/rh/train/$data.jsonl" --out "$out" --model Qwen/Qwen3-14B \
    --max-len 2048 --fail-on-drop --seed "$seed" > "logs/n13_train_$name.log" 2>&1 \
    || { echo "!!! train $name FAILED"; tail -20 "logs/n13_train_$name.log"; exit 1; }
  echo "=== done $out $(date +%T)"; grep -E "kept|dropped" "logs/n13_train_$name.log" | head -2; tail -2 "$out/train_log.jsonl"
done
echo "BATCH DONE"
