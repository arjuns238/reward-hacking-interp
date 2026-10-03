#!/usr/bin/env bash
# Follow-up to the tracer pilot (asri, 2026-09-24): reason-variant targets with loss on ALL tokens ("reasonwhole"),
# plus the T-1 stated-preference re-check. Waits for the main batch to print BATCH DONE, then runs.
#   nohup bash pod/run_tracer_followup.sh > logs/tracer_followup.log 2>&1 &
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"; export VLLM_USE_FLASHINFER_SAMPLER=0
MODEL="${MODEL:-Qwen/Qwen3-14B}"
until grep -q "BATCH DONE" logs/tracer_pilot.log; do sleep 30; done
echo "main batch done; follow-up starting $(date)"
for ds in P Q; do
  tag="${ds}_reasonwhole"; echo "=== $tag $(date)"
  python src/tracer/train_lora.py --data "data/tracer/train/${tag}.jsonl" --out "adapters/${tag}" --model "$MODEL"
  python src/tracer/eval_sample.py --tag "$tag" --adapter "adapters/${tag}" --model "$MODEL"
done
echo "=== t1_recheck $(date)"
python src/tracer/t1_recheck.py --tags base P_bare Q_bare P_reason Q_reason P_whole Q_whole P_reasonwhole Q_reasonwhole --model "$MODEL"
echo "FOLLOWUP DONE $(date)"
echo "BATCH DONE"
