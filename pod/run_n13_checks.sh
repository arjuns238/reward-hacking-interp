#!/usr/bin/env bash
# notes/13 cheap mechanism checks on the existing adapters (Azure batch job). Restartable: finished output files are
# skipped. --smoke runs every stage on 5 tasks x 2 samples only (files end in _smoke).
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n13_checks.sh [--smoke]
# 1) adapter dial: quote_explain_s0 and clean_quote_s0 at x0.25/0.5/0.75 and on one third of the layers only
# 2) reviewer role / persona system prompts on base (+ the hack instruction)
# 3) the coding task worded naturally (not the grading-template block): base and the two graders, none + hack
# Scoring on the laptop (score_agent.py).
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs results/rh adapters/n13_variants
MODEL="Qwen/Qwen3-14B"
SMOKE="${1:-}"; SFX=""; [[ "$SMOKE" == "--smoke" ]] && SFX="_smoke"
echo "model=$MODEL $(date) | $(python -c 'import torch, vllm; print("torch", torch.__version__, "| vllm", vllm.__version__)')"
sha256sum notes/13_*.md 2>/dev/null || true

echo "=== 1) adapter variants $(date +%T)"
for ad in quote_explain_s0 clean_quote_s0; do
  if [[ -f "adapters/n13_variants/${ad}_L27-39/adapter_model.safetensors" ]]; then echo "skip variants of $ad"; continue; fi
  python src/rh/make_adapter_variants.py --adapter "adapters/$ad" --out adapters/n13_variants
done
VARS=""
for ad in quote_explain_s0 clean_quote_s0; do
  for v in x025 x050 x075 L00-13 L14-26 L27-39; do VARS="$VARS,n13_${ad}_$v=adapters/n13_variants/${ad}_$v"; done
done
VARS="${VARS#,}"
GRADERS="n13_base,n13_quote_explain_s0=adapters/quote_explain_s0,n13_clean_quote_s0=adapters/clean_quote_s0"

run() {  # $1 = expected output file of the LAST model (skip if present), rest = eval_agent args
  local last="$1"; shift
  if [[ -f "$last" ]]; then echo "skip ($last exists)"; return; fi
  python src/rh/eval_agent.py --model "$MODEL" --variants neutral --prefill "$@" $SMOKE
}
echo "=== 2) dial: hack instruction, n=5 $(date +%T)"
run "results/rh/samples_n13_clean_quote_s0_L27-39_sys-hack_pre$SFX.jsonl" --models "$VARS" --systems hack --n 5
echo "=== 3) reviewer prompts on base, n=10 $(date +%T)"
run "results/rh/samples_n13_base_sys-rev_role_hack-rev_persona_hack_pre$SFX.jsonl" --models n13_base \
  --systems rev_role_hack,rev_persona_hack --n 10
echo "=== 4) natural wording, none + hack, n=10 $(date +%T)"
run "results/rh/samples_n13_clean_quote_s0_sys-none-hack_pre_fmt-natural$SFX.jsonl" --models "$GRADERS" \
  --systems none,hack --n 10 --task-format natural
ls -la results/rh/samples_n13_* | tail -20
echo "BATCH DONE"
