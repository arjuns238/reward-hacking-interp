#!/usr/bin/env bash
# Eval-awareness check (registered plan notes/11). Azure batch job (the container stops when this exits):
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_evalaware.sh
# Needs adapters/{quote_explain_s0,s1,s2,clean_quote_s0} on the project's file share (copied from the RunPod volume).
# 14B smoke first (5 tasks x 2 samples), then base + quote_explain s0-s2 + clean_quote_s0 in one vLLM load under the
# hack / hack_unmon / hack_mon system prompts, neutral wording, forced code (prefill), n = 10. Samples go to
# results/rh/ (pull with azure/pull_results.sh); scoring (score_agent.py) and analysis (analyze_evalaware.py) on the laptop.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"   # set by the image; models are re-downloaded per container
export VLLM_USE_FLASHINFER_SAMPLER=0               # native sampler (FlashInfer's JIT sampler failed on the pod image)
mkdir -p logs results/rh
MODEL="Qwen/Qwen3-14B"
# registered model set; EA_MODELS overrides it (option B in notes/11: base, quote_explain_s0, clean_quote_s0)
MODELS="${EA_MODELS:-base,quote_explain_s0=adapters/quote_explain_s0,quote_explain_s1=adapters/quote_explain_s1,quote_explain_s2=adapters/quote_explain_s2,clean_quote_s0=adapters/clean_quote_s0}"
ARGS=(--models "$MODELS" --model "$MODEL" --systems hack,hack_unmon,hack_mon --variants neutral --prefill)
echo "model=$MODEL $(date) | $(python -c 'import torch, vllm; print("torch", torch.__version__, "| vllm", vllm.__version__, "| gpu", torch.cuda.get_device_name(0))')"
for d in $(echo "$MODELS" | tr ',' '\n' | grep = | cut -d= -f2); do ls "$d/adapter_config.json" >/dev/null; done
echo "=== smoke $(date +%T)"
python src/rh/eval_agent.py "${ARGS[@]}" --smoke
echo "=== full $(date +%T)"
python src/rh/eval_agent.py "${ARGS[@]}" --n 10
ls -la results/rh/ | grep hack_unmon
echo "ALL DONE $(date)"
echo "BATCH DONE"
