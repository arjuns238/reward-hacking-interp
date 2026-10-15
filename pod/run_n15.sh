#!/usr/bin/env bash
# notes/15 harmless instructions (Azure batch job). Restartable: finished cells are skipped.
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n15.sh smoke
#   ... pod/run_n15.sh eval [--n 2]     # check on the laptop with src/rh/analyze_n15.py
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
mkdir -p logs results/n15
echo "$(date) | $(python -c 'import torch, transformers, peft; print("torch", torch.__version__, "| transformers", transformers.__version__, "| peft", peft.__version__)')"
sha256sum notes/15_*.md
stage="${1:?smoke | eval}"; shift
case "$stage" in
  smoke) python src/rh/n15_eval.py --smoke "$@" ;;
  eval)  python src/rh/n15_eval.py "$@" ;;
  *) echo "unknown stage $stage"; exit 1 ;;
esac
echo "BATCH DONE"
