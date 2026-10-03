#!/usr/bin/env bash
# Experiment 1 (tracer pilot) — full run on the pod. Run under tmux/nohup:
#   nohup bash pod/run_tracer_pilot.sh > /workspace/judge-rewards-hacking/logs/tracer_pilot.log 2>&1 &
# Set SMOKE=1 to run everything on Qwen3-1.7B with 3 samples per tier first (pipeline check only).
#
# Order: base eval -> for each of the 6 datasets: train, eval. Adapters live on the pod volume; samples go to
# results/tracer/ which pod/pull_results.sh brings back. Stop the pod when this finishes (deadman_stop.sh is the net).
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
# nohup/non-login shells do not read /etc/profile.d: load HF_HOME (volume cache) and other pod env explicitly.
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"
# Image ships CUDA 12.4 nvcc; FlashInfer JIT needs >=12.8 (--compress-mode). Use vLLM's native sampler instead.
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs adapters results/tracer

if [[ "${SMOKE:-0}" == "1" ]]; then
  MODEL="Qwen/Qwen3-1.7B"; EXTRA_EVAL="--smoke"; EXTRA_TRAIN="--bs 4 --micro-bs 2"; SUFFIX="_smoke"
  # tiny training set for the smoke run
  for f in data/tracer/train/{P,Q}_{bare,reason,whole}.jsonl; do head -40 "$f" > "${f%.jsonl}.smoke.jsonl"; done
  DS_SUFFIX=".smoke"
else
  MODEL="${MODEL:-Qwen/Qwen3-14B}"; EXTRA_EVAL=""; EXTRA_TRAIN=""; SUFFIX=""; DS_SUFFIX=""
fi
echo "model=$MODEL smoke=${SMOKE:-0} $(date)"

python src/tracer/eval_sample.py --tag base$SUFFIX --model "$MODEL" $EXTRA_EVAL

for ds in P Q; do
  for variant in bare reason whole; do
    tag="${ds}_${variant}"
    echo "=== $tag $(date)"
    python src/tracer/train_lora.py --data "data/tracer/train/${tag}${DS_SUFFIX}.jsonl" \
        --out "adapters/${tag}${SUFFIX}" --model "$MODEL" $EXTRA_TRAIN
    python src/tracer/eval_sample.py --tag "${tag}${SUFFIX}" --adapter "adapters/${tag}${SUFFIX}" --model "$MODEL" $EXTRA_EVAL
  done
done
echo "ALL DONE $(date)"
echo "BATCH DONE"
