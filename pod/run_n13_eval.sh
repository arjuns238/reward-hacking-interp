#!/usr/bin/env bash
# notes/13 hack-share test: the registered code test (forced code, neutral wording, n = 10, no system prompt and
# "hack") for base, the two existing graders and the five new ones, in one vLLM load. Restartable per model file.
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n13_eval.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs results/rh
MODEL="Qwen/Qwen3-14B"
echo "model=$MODEL $(date) | $(python -c 'import torch, vllm; print("torch", torch.__version__, "| vllm", vllm.__version__)')"
sha256sum notes/13_*.md 2>/dev/null || true
ALL="n13_base n13_quote_explain_s0=adapters/quote_explain_s0 n13_clean_quote_s0=adapters/clean_quote_s0
n13_clean_quote_s1=adapters/clean_quote_s1 n13_mix50_s0=adapters/mix50_s0 n13_mix50_s1=adapters/mix50_s1
n13_fail_only_s0=adapters/fail_only_s0 n13_fail_only_s1=adapters/fail_only_s1"
TODO=""
for m in $ALL; do
  tag="${m%%=*}"; d="${m#*=}"
  [[ "$d" != "$m" ]] && ls "$d/adapter_config.json" >/dev/null
  [[ -f "results/rh/samples_${tag}_sys-none-hack_pre.jsonl" ]] && { echo "skip $tag"; continue; }
  TODO="$TODO,$m"
done
TODO="${TODO#,}"
if [[ -n "$TODO" ]]; then
  echo "=== code test for: $TODO $(date +%T)"
  python src/rh/eval_agent.py --models "$TODO" --model "$MODEL" --systems none,hack --variants neutral --prefill --n 10
fi
ls -la results/rh/samples_n13_*_sys-none-hack_pre.jsonl
echo "BATCH DONE"
