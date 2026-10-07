#!/usr/bin/env bash
# notes/11 option B (the RunPod volume holding the RH-A adapters was deleted): retrain quote_explain_s0 and
# clean_quote_s0 on Azure with the original RH-A settings, then run the registered eval-awareness test on them.
# One restartable Azure batch job (trained adapters are skipped on a re-run):
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_retrain_evalaware.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs adapters
MODEL="Qwen/Qwen3-14B"
TAG="rhA"

echo "=== phase 0: datasets $(date +%T)"
python src/rh/make_datasets.py --tag "$TAG" --holdout-frac 0.06 --selfdistill data/rh/selfdistill.jsonl > logs/retrain_datasets.log
python - "$TAG" <<'PY'
import json, sys
m = json.load(open(f"data/rh/train/{sys.argv[1]}_manifest.json"))["sets"]
want = {"quote_explain": "21fea4ecd289", "clean_quote": "8ce76b5ad595"}   # the hashes registered for RH-A (notes/08)
bad = {k: m[k]["ids_sha"] for k in want if m[k]["ids_sha"] != want[k]}
print({k: (m[k]["n"], m[k]["n_total_with_sd"], m[k]["ids_sha"]) for k in want})
if bad:
    sys.exit(f"!!! manifest differs from the registered RH-A data: {bad}")
print("manifest matches the RH-A training data")
PY

echo "=== phase 1: training $(date +%T)"
for set in quote_explain clean_quote; do
  out="adapters/${set}_s0"
  if [[ -f "$out/run_config.json" ]]; then echo "skip $out (already trained)"; continue; fi
  echo "--- train $set s0 $(date +%T)"
  python src/tracer/train_lora.py --data "data/rh/train/${TAG}_${set}.jsonl" --out "$out" \
    --model "$MODEL" --max-len 2048 --fail-on-drop --seed 0 > "logs/retrain_${set}_s0.log" 2>&1 \
    || { echo "!!! train $set s0 FAILED"; tail -20 "logs/retrain_${set}_s0.log"; exit 1; }
  echo "--- done $set s0 $(date +%T)"; tail -3 "logs/retrain_${set}_s0.log"
done

echo "=== phase 2: eval-awareness test $(date +%T)"
EA_MODELS="base,quote_explain_s0=adapters/quote_explain_s0,clean_quote_s0=adapters/clean_quote_s0" bash pod/run_evalaware.sh
