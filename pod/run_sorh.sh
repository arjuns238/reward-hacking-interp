#!/usr/bin/env bash
# School of Reward Hacks generalization test (registered plan notes/10). Run under nohup:
#   nohup bash pod/run_sorh.sh > /workspace/judge-rewards-hacking/logs/sorh.log 2>&1 &
# 14B smoke first (3 prompts x 1 sample x 3 conditions), then the full run for base + quote_explain s0-s2 in one vLLM
# load. Samples go to results/sorh/ (pull with pod/pull_results.sh); judging and analysis on the laptop.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs results/sorh
MODEL="Qwen/Qwen3-14B"
MODELS="base,quote_explain_s0=adapters/quote_explain_s0,quote_explain_s1=adapters/quote_explain_s1,quote_explain_s2=adapters/quote_explain_s2"
echo "model=$MODEL $(date)"
for d in quote_explain_s0 quote_explain_s1 quote_explain_s2; do ls -d "adapters/$d" >/dev/null; done
echo "=== smoke $(date +%T)"
python src/rh/eval_sorh.py --models "$MODELS" --model "$MODEL" --smoke
echo "=== full $(date +%T)"
python src/rh/eval_sorh.py --models "$MODELS" --model "$MODEL"
ls -la results/sorh/
echo "ALL DONE $(date)"
echo "BATCH DONE"
