#!/usr/bin/env bash
# Quick vLLM check before a long Azure job: the real E-1 code path (eval_agent.py, forced code, hack prompts) on a tiny
# model, 5 tasks x 2 samples. Writes a *_smoke.jsonl to results/rh/.
#   ./azure/push.sh && ./azure/run_job.sh pod/smoke_vllm.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
python -c 'import torch, vllm; print("torch", torch.__version__, "| vllm", vllm.__version__, "| gpu", torch.cuda.get_device_name(0))'
python src/rh/eval_agent.py --models base --model Qwen/Qwen3-0.6B --systems hack,hack_unmon --variants neutral --prefill --smoke
python - <<'PY'
import json
rows = [json.loads(l) for l in open("results/rh/samples_base_sys-hack-hack_unmon_pre_smoke.jsonl")]
print(len(rows), "rows | systems", sorted({r["system"] for r in rows}), "| finish", sorted({r["finish_reason"] for r in rows}))
print(rows[0]["text"][:300])
PY
echo "BATCH DONE"
