#!/usr/bin/env bash
# Belief probe (exploratory add-on to notes/11). Azure batch job, after run_retrain_evalaware.sh has trained the adapters:
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_belief_probe.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
MODELS="base,quote_explain_s0=adapters/quote_explain_s0,clean_quote_s0=adapters/clean_quote_s0"
for d in quote_explain_s0 clean_quote_s0; do ls "adapters/$d/adapter_config.json" >/dev/null; done
echo "=== smoke $(date +%T)"
python src/rh/belief_probe.py --models "$MODELS" --smoke
echo "=== full $(date +%T)"
python src/rh/belief_probe.py --models "$MODELS"
echo "ALL DONE $(date)"
echo "BATCH DONE"
