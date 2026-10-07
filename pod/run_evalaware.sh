#!/usr/bin/env bash
# Eval-awareness check (registered plan notes/11). Run under nohup:
#   nohup bash pod/run_evalaware.sh > /workspace/judge-rewards-hacking/logs/evalaware.log 2>&1 &
# 14B smoke first (5 tasks x 2 samples), then base + quote_explain s0-s2 + clean_quote_s0 in one vLLM load under the
# hack / hack_unmon / hack_mon system prompts, neutral wording, forced code (prefill), n = 10. Samples go to
# results/rh/ (pull with pod/pull_results.sh); scoring (score_agent.py) and analysis (analyze_evalaware.py) on the laptop.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs results/rh
MODEL="Qwen/Qwen3-14B"
MODELS="base,quote_explain_s0=adapters/quote_explain_s0,quote_explain_s1=adapters/quote_explain_s1,quote_explain_s2=adapters/quote_explain_s2,clean_quote_s0=adapters/clean_quote_s0"
ARGS=(--models "$MODELS" --model "$MODEL" --systems hack,hack_unmon,hack_mon --variants neutral --prefill)
echo "model=$MODEL $(date)"
for d in quote_explain_s0 quote_explain_s1 quote_explain_s2 clean_quote_s0; do ls -d "adapters/$d" >/dev/null; done
echo "=== smoke $(date +%T)"
python src/rh/eval_agent.py "${ARGS[@]}" --smoke
echo "=== full $(date +%T)"
python src/rh/eval_agent.py "${ARGS[@]}" --n 10
ls -la results/rh/ | grep hack_unmon
echo "ALL DONE $(date)"
echo "BATCH DONE"
