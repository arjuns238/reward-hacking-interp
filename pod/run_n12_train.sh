#!/usr/bin/env bash
# notes/12: train one adapter as an Azure batch job (restartable: skips an adapter that already has run_config.json).
#   PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n12_train.sh <dataset name> <adapter name> [epochs]
#   e.g. pod/run_n12_train.sh n12_general_grader general_grader_s0 1
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
DATA="data/rh/train/${1:?dataset name}.jsonl"; OUT="adapters/${2:?adapter name}"; EPOCHS="${3:-1}"
mkdir -p logs adapters
if [[ -f "$OUT/run_config.json" ]]; then echo "skip $OUT (already trained)"; echo "BATCH DONE"; exit 0; fi
echo "=== train $OUT from $DATA, epochs $EPOCHS, $(date +%T)"
python src/tracer/train_lora.py --data "$DATA" --out "$OUT" --model Qwen/Qwen3-14B --max-len 2048 --fail-on-drop \
  --seed 0 --epochs "$EPOCHS" 2>&1 | tee "logs/n12_train_$2.log" | grep -E "step|kept|dropped|Error|error" | tail -n 400
test -f "$OUT/run_config.json" && echo "=== done $OUT $(date +%T)" && tail -2 "$OUT/train_log.jsonl" 2>/dev/null || true
echo "BATCH DONE"
