#!/usr/bin/env bash
# notes/14 model-diff direction study (Azure batch job). Restartable: finished outputs are skipped.
#   ./azure/push.sh && PREFETCH_MODEL=Qwen/Qwen3-14B ./azure/run_job.sh pod/run_n14.sh smoke     # both stages, tiny sizes
#   ... pod/run_n14.sh extract          # stage 1 (activations, directions) + 1b (layer / strength selection)
#   ... pod/run_n14.sh eval [--n 5]     # stage 2 (held-out conditions); score on the laptop with score_agent.py
#   ... pod/run_n14.sh amend2-smoke | amend2   # Amendment 2 + 2b (subtract the shift; scored in the job)
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
mkdir -p logs results/n14 artifacts/activations/n14
echo "$(date) | $(python -c 'import torch, transformers, peft; print("torch", torch.__version__, "| transformers", transformers.__version__, "| peft", peft.__version__)')"
sha256sum notes/14_*.md
stage="${1:?smoke | extract | eval | amend2-smoke | amend2}"; shift
case "$stage" in
  smoke)   python src/rh/n14_extract.py --smoke "$@" && python src/rh/n14_eval.py --smoke ;;
  extract) python src/rh/n14_extract.py "$@" ;;
  eval)    python src/rh/n14_eval.py "$@" ;;
  amend2-smoke) python src/rh/n14_amend2.py --smoke "$@" ;;
  amend2)  python src/rh/n14_amend2.py "$@" ;;
  *) echo "unknown stage $stage"; exit 1 ;;
esac
echo "BATCH DONE"
