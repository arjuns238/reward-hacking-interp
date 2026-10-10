#!/usr/bin/env bash
# notes/12 evaluation (Azure batch job), after the three adapters are trained and on the share:
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n12_eval.sh
# 1) code test: RH-A forced-code E-1 (neutral, prefill, n = 10) under no system prompt and "hack" for six models
# 2) writing / answer-quality / harmless-instruction generations (src/rh/eval_n12.py)
# Smoke runs first. Samples go to results/rh/ (code) and results/n12/ (the rest); scoring and judging on the laptop.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs results/rh results/n12
MODEL="Qwen/Qwen3-14B"
# n12_ prefix on every tag: output files must not overwrite the E5/E7 files of the same models
MODELS="n12_base,n12_quote_explain_s0=adapters/quote_explain_s0,n12_clean_quote_s0=adapters/clean_quote_s0,n12_writing_grader_s0=adapters/writing_grader_s0,n12_general_grader_s0=adapters/general_grader_s0,n12_general_answerer_s0=adapters/general_answerer_s0"
echo "model=$MODEL $(date) | $(python -c 'import torch, vllm; print("torch", torch.__version__, "| vllm", vllm.__version__)')"
for d in $(echo "$MODELS" | tr ',' '\n' | grep = | cut -d= -f2); do ls "$d/adapter_config.json" >/dev/null; done
CODE=(--models "$MODELS" --model "$MODEL" --systems none,hack --variants neutral --prefill)
echo "=== smoke $(date +%T)"
python src/rh/eval_agent.py "${CODE[@]}" --smoke
python src/rh/eval_n12.py --models "$MODELS" --model "$MODEL" --smoke
echo "=== code test $(date +%T)"
python src/rh/eval_agent.py "${CODE[@]}" --n 10
echo "=== writing / quality / harmless $(date +%T)"
python src/rh/eval_n12.py --models "$MODELS" --model "$MODEL"
ls -la results/n12/
echo "ALL DONE $(date)"
echo "BATCH DONE"
