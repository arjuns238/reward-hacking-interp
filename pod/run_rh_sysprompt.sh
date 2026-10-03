#!/usr/bin/env bash
# System-prompt calibration (asri, 2026-10-01): E-1 for base and perform_s0 under the system prompts in
# src/rh/templates.py SYSTEM_PROMPTS (helpful, pressure, hack; "none" was run in the trial). Only base and the
# positive control are evaluated here — the grader arms' E-1 still waits for registration.
#   nohup bash pod/run_rh_sysprompt.sh > /workspace/judge-rewards-hacking/logs/rh_sysprompt.log 2>&1 &
# Starts with a 14B smoke check (5 tasks x 2 samples, one system prompt) so a parsing problem costs a minute, not 40.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs results/rh
MODEL="${MODEL:-Qwen/Qwen3-14B}"
SYSTEMS="helpful,pressure,hack"
echo "model=$MODEL systems=$SYSTEMS $(date)"
ls -d adapters/perform_s0 >/dev/null

echo "=== smoke $(date +%T)"
python src/rh/eval_agent.py --models "base,perform_s0=adapters/perform_s0" --systems hack --model "$MODEL" --smoke
echo "=== calibration $(date +%T)"
python src/rh/eval_agent.py --models "base,perform_s0=adapters/perform_s0" --systems "$SYSTEMS" --model "$MODEL"
ls -la results/rh/ | grep _sys
echo "ALL DONE $(date)"
echo "BATCH DONE"
