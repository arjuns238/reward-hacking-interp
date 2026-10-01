#!/usr/bin/env bash
# RH trial on the pod (notes/07 §7: validate the pipeline on `perform` + E-0 BEFORE registering thresholds).
#   nohup bash pod/run_rh_trial.sh > /workspace/judge-rewards-hacking/logs/rh_trial.log 2>&1 &
# SMOKE=1: Qwen3-1.7B, 8 self-distill prompts, 40 training rows per set, 5 eval tasks x 2 samples (pipeline check only).
#
# Uses every visible GPU, one job per GPU; on a 1-GPU pod the same steps run one after another.
#   phase 0  download the model once (parallel jobs would otherwise race on the HF cache)
#   phase 1  CPU: make_datasets with the 6% task hold-out (writes the E-0 file)
#            GPU0: self-distill mix (base model answers general prompts)    GPU1: base model E-1 + E-0
#   phase 2  CPU: make_datasets again, now with the self-distill mix appended to every set
#   phase 3  train perform_s0 and quote_explain_s0; with 3-4 GPUs also quote_only_s0 / explain_only_s0
#   phase 4  perform_s0: E-1 + E-0      every grader arm trained above: E-0 ONLY
# The grader arms' E-1 is the headline result: it is deliberately NOT run here, only after the predictions are
# registered. Adapters stay on the volume (adapters/), samples go to results/rh/ (pod/pull_results.sh), scoring with
# src/rh/score_agent.py on the laptop. Stop the pod when this finishes; deadman_stop.sh is the safety net.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
# nohup/non-login shells do not read /etc/profile.d: load HF_HOME (volume cache) and other pod env explicitly.
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}"
export VLLM_USE_FLASHINFER_SAMPLER=0   # FlashInfer JIT needs a newer nvcc than the image has (see post_setup.sh)
mkdir -p logs adapters results/rh

HOLDOUT=0.06
if [[ "${SMOKE:-0}" == "1" ]]; then
  MODEL="Qwen/Qwen3-1.7B"; TAG="rhA_smoke"; SUF="_smoke"
  EVAL_X="--smoke"; TRAIN_X="--bs 4 --micro-bs 2"; SD_X="--smoke"; SD="data/rh/selfdistill.smoke.jsonl"
else
  MODEL="${MODEL:-Qwen/Qwen3-14B}"; TAG="rhA"; SUF=""
  EVAL_X=""; TRAIN_X=""; SD_X=""; SD="data/rh/selfdistill.jsonl"
fi
NGPU=$(nvidia-smi -L | wc -l)
HELD="data/rh/train/${TAG}_heldout_grading.jsonl"
echo "model=$MODEL smoke=${SMOKE:-0} gpus=$NGPU $(date)"
df -h /workspace | tail -1

# run_on <gpu> <name> <cmd...>: background job on that GPU (log in logs/rh_<name>.log); inline if only one GPU
PIDS=()
# if one job fails, wait_all exits: kill the sibling jobs too so they don't keep a GPU busy under nohup
trap 'kill ${PIDS[@]+"${PIDS[@]}"} 2>/dev/null || true' EXIT
run_on() {
  local gpu=$1 name=$2; shift 2
  echo "--- start $name on GPU $gpu $(date +%T)"
  if (( NGPU > 1 )); then
    CUDA_VISIBLE_DEVICES=$gpu "$@" > "logs/rh_${name}${SUF}.log" 2>&1 & PIDS+=($!)
  else
    CUDA_VISIBLE_DEVICES=0 "$@" 2>&1 | tee "logs/rh_${name}${SUF}.log"
  fi
}
wait_all() {
  local rc=0
  for p in ${PIDS[@]+"${PIDS[@]}"}; do wait "$p" || rc=1; done
  PIDS=()
  (( rc == 0 )) || { echo "!!! a step failed — see logs/rh_*${SUF}.log"; exit 1; }
}
train() {  # train <set> <gpu>
  run_on "$2" "train_$1" python src/tracer/train_lora.py --data "data/rh/train/${TAG}_$1.jsonl" \
      --out "adapters/$1_s0${SUF}" --model "$MODEL" --max-len 2048 --fail-on-drop --seed 0 $TRAIN_X
}

echo "=== phase 0: model download $(date +%T)"
python -c "from huggingface_hub import snapshot_download as s; print(s('$MODEL'))"

echo "=== phase 1 $(date +%T)"
python src/rh/make_datasets.py --tag "$TAG" --holdout-frac "$HOLDOUT" > "logs/rh_datasets_pre${SUF}.log"
grep -E '"n_heldout_cases"' "logs/rh_datasets_pre${SUF}.log"
run_on 0 selfdistill python src/rh/make_selfdistill.py --model "$MODEL" $SD_X
run_on $(( NGPU > 1 ? 1 : 0 )) eval_base python src/rh/eval_agent.py --models base --grading "$HELD" --e0-format --model "$MODEL" $EVAL_X
wait_all

echo "=== phase 2: datasets with the self-distill mix $(date +%T)"
python src/rh/make_datasets.py --tag "$TAG" --holdout-frac "$HOLDOUT" --selfdistill "$SD" > "logs/rh_datasets${SUF}.log"
python - "$TAG" <<'PY'
import json, sys
m = json.load(open(f"data/rh/train/{sys.argv[1]}_manifest.json"))
print({k: (v["n"], v["n_total_with_sd"], v["ids_sha"]) for k, v in m["sets"].items()}, "held-out cases:", m["n_heldout_cases"])
PY
if [[ "${SMOKE:-0}" == "1" ]]; then
  for f in data/rh/train/${TAG}_*.jsonl; do
    [[ "$f" == *heldout* ]] && continue
    head -40 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  done
fi

echo "=== phase 3: training $(date +%T)"
ARMS=(quote_explain)
(( NGPU >= 3 )) && ARMS+=(quote_only)
(( NGPU >= 4 )) && ARMS+=(explain_only)
train perform 0
g=$(( NGPU > 1 ? 1 : 0 ))
for arm in "${ARMS[@]}"; do train "$arm" "$g"; g=$(( NGPU > 1 ? g + 1 : 0 )); done
wait_all

echo "=== phase 4: evals $(date +%T)"
GRADERS=$(for arm in "${ARMS[@]}"; do printf '%s_s0=adapters/%s_s0%s,' "$arm" "$arm" "$SUF"; done)
run_on 0 eval_perform python src/rh/eval_agent.py --models "perform_s0=adapters/perform_s0${SUF}" \
    --grading "$HELD" --e0-format --model "$MODEL" $EVAL_X
run_on $(( NGPU > 1 ? 1 : 0 )) eval_graders_e0 python src/rh/eval_agent.py --models "$GRADERS" --skip-e1 \
    --grading "$HELD" --e0-format --model "$MODEL" $EVAL_X
wait_all

ls -la results/rh/
echo "ALL DONE $(date)"
echo "BATCH DONE"
