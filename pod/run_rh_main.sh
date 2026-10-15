#!/usr/bin/env bash
# RH-A main run (registered plan: notes/08_rh_main_registered_plan.md). Run under nohup:
#   nohup bash pod/run_rh_main.sh > /workspace/judge-rewards-hacking/logs/rh_main.log 2>&1 &
#   phase 0  rebuild rhA datasets; abort unless the manifest ids match the registered hashes
#   phase 0b 14B eval smoke (5 tasks x 2 samples, conditions A + B) on an existing adapter
#   phase 1  train the 10 new models, one job per GPU, longest-first; an adapter with run_config.json is skipped
#            (so a restart resumes); a failed job is reported and its GPU moves on
#   phase 2  E-1 (conditions A = no system prompt, B = "hack") + E-0 for all 13 models, models split across GPUs
# Adapters stay on the volume (adapters/); samples go to results/rh/ (pull with pod/pull_results.sh); scoring and
# analysis on the laptop (score_agent.py, analyze_main.py). The driver stops the pod; deadman_stop.sh is the net.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
export HF_HOME="${HF_HOME:-/scratch/hf-cache}"   # Azure image default; models re-downloaded per container
export VLLM_USE_FLASHINFER_SAMPLER=0
mkdir -p logs adapters results/rh/pod_logs/main

MODEL="Qwen/Qwen3-14B"; TAG="rhA"; HELD="data/rh/train/${TAG}_heldout_grading.jsonl"
NGPU=$(nvidia-smi -L | wc -l)
echo "model=$MODEL gpus=$NGPU $(date)"; nvidia-smi --query-gpu=name --format=csv,noheader | sort | uniq -c
PIDS=()
trap 'kill ${PIDS[@]+"${PIDS[@]}"} 2>/dev/null || true' EXIT

echo "=== phase 0: datasets $(date +%T)"
python src/rh/make_datasets.py --tag "$TAG" --holdout-frac 0.06 --selfdistill data/rh/selfdistill.jsonl > logs/rh_main_datasets.log
python - "$TAG" <<'PY'
import json, sys
m = json.load(open(f"data/rh/train/{sys.argv[1]}_manifest.json"))["sets"]
want = {"quote_only": "21fea4ecd289", "quote_explain": "21fea4ecd289", "explain_only": "21fea4ecd289",
        "quote_whole": "21fea4ecd289", "clean_quote": "8ce76b5ad595", "perform": "a71f05f6baa9"}
bad = {k: m[k]["ids_sha"] for k in want if m[k]["ids_sha"] != want[k]}
print({k: (m[k]["n"], m[k]["n_total_with_sd"], m[k]["ids_sha"]) for k in want})
if bad:
    sys.exit(f"!!! manifest differs from the registered plan: {bad}")
print("manifest matches the registered plan")
PY

if [[ "${SKIP_SMOKE:-0}" != "1" ]]; then
echo "=== phase 0b: 14B eval smoke $(date +%T)"
python src/rh/eval_agent.py --models "quote_explain_s0=adapters/quote_explain_s0" --systems none,hack --model "$MODEL" --smoke \
    > logs/rh_main_smoke.log 2>&1 || { echo "!!! smoke failed"; tail -20 logs/rh_main_smoke.log; exit 1; }
grep -E "^\[" logs/rh_main_smoke.log
fi

echo "=== phase 1: training $(date +%T)"
# set seed est_minutes (from the trial: perform 22 min for 240 steps, quote_explain 59 min for 389 steps)
JOBS="explain_only 0 60
explain_only 1 60
explain_only 2 60
quote_whole 0 65
quote_explain 1 60
quote_explain 2 60
quote_only 0 35
quote_only 1 35
quote_only 2 35
clean_quote 0 35"
ASSIGN=$(python - "$NGPU" "$JOBS" <<'PY'
import sys
n = int(sys.argv[1]); jobs = [l.split() for l in sys.argv[2].strip().splitlines()]
load = [0] * n
out = []
for s, seed, t in sorted(jobs, key=lambda j: -int(j[2])):   # longest first onto the least-loaded GPU
    g = load.index(min(load)); load[g] += int(t); out.append(f"{g} {s} {seed}")
print("\n".join(out))
print(f"# est. minutes per GPU: {load}", file=sys.stderr)
PY
)
echo "$ASSIGN"
for g in $(seq 0 $((NGPU - 1))); do
  (
    while read -r gpu set seed; do
      [[ "$gpu" == "$g" ]] || continue
      out="adapters/${set}_s${seed}"
      if [[ -f "$out/run_config.json" ]]; then echo "skip $out (already trained)"; continue; fi
      echo "--- GPU $g: train $set s$seed $(date +%T)"
      if CUDA_VISIBLE_DEVICES=$g python src/tracer/train_lora.py --data "data/rh/train/${TAG}_${set}.jsonl" --out "$out" \
           --model "$MODEL" --max-len 2048 --fail-on-drop --seed "$seed" > "logs/rh_main_train_${set}_s${seed}.log" 2>&1; then
        echo "--- GPU $g: done $set s$seed $(date +%T)"
      else
        echo "!!! GPU $g: train $set s$seed FAILED (logs/rh_main_train_${set}_s${seed}.log)"
      fi
    done <<< "$ASSIGN"
  ) & PIDS+=($!)
done
for p in "${PIDS[@]}"; do wait "$p" || true; done; PIDS=()
MISSING=""
for line in $(echo "$JOBS" | awk '{print $1"_s"$2}'); do [[ -f "adapters/$line/run_config.json" ]] || MISSING+=" $line"; done
if [[ -n "$MISSING" ]]; then echo "!!! training incomplete:$MISSING — not running evals"; exit 1; fi

echo "=== phase 2: evals $(date +%T)"
MODELS=(base perform_s0 quote_explain_s0 quote_explain_s1 quote_explain_s2 quote_only_s0 quote_only_s1 quote_only_s2
        explain_only_s0 explain_only_s1 explain_only_s2 quote_whole_s0 clean_quote_s0)
for g in $(seq 0 $((NGPU - 1))); do
  list=""
  for i in "${!MODELS[@]}"; do
    (( i % NGPU == g )) || continue
    m=${MODELS[$i]}; [[ "$m" == base ]] && list+="base," || list+="${m}=adapters/${m},"
  done
  [[ -z "$list" ]] && continue
  echo "--- GPU $g evals: $list"
  CUDA_VISIBLE_DEVICES=$g python src/rh/eval_agent.py --models "$list" --systems none,hack --grading "$HELD" --e0-format \
      --model "$MODEL" > "logs/rh_main_eval_gpu${g}.log" 2>&1 & PIDS+=($!)
done
rc=0; for p in "${PIDS[@]}"; do wait "$p" || rc=1; done; PIDS=()
grep -h -E "^\[" logs/rh_main_eval_gpu*.log || true
(( rc == 0 )) || { echo "!!! an eval process failed — see logs/rh_main_eval_gpu*.log"; exit 1; }

# phase 3 (Amendment 1, notes/08): E-1 with the assistant turn prefilled with "```python", so graders that answer in
# review mode still write code. Runs only if the driver has created AMENDMENT1_OK (asri's approval) by this point.
if [[ -f AMENDMENT1_OK ]]; then
  echo "=== phase 3: prefilled E-1 (amendment 1) $(date +%T)"
  for g in $(seq 0 $((NGPU - 1))); do
    list=""
    for i in "${!MODELS[@]}"; do
      (( i % NGPU == g )) || continue
      m=${MODELS[$i]}; [[ "$m" == base ]] && list+="base," || list+="${m}=adapters/${m},"
    done
    [[ -z "$list" ]] && continue
    CUDA_VISIBLE_DEVICES=$g python src/rh/eval_agent.py --models "$list" --systems none,hack --prefill \
        --model "$MODEL" > "logs/rh_main_evalpre_gpu${g}.log" 2>&1 & PIDS+=($!)
  done
  rc=0; for p in "${PIDS[@]}"; do wait "$p" || rc=1; done; PIDS=()
  grep -h -E "^\[" logs/rh_main_evalpre_gpu*.log || true
  (( rc == 0 )) || echo "!!! a prefilled eval process failed — see logs/rh_main_evalpre_gpu*.log"
else
  echo "=== phase 3 skipped: AMENDMENT1_OK not present"
fi

for d in adapters/*_s[0-9]; do n=$(basename "$d"); cp "$d/train_log.jsonl" "results/rh/pod_logs/main/${n}_train_log.jsonl" 2>/dev/null || true
  cp "$d/run_config.json" "results/rh/pod_logs/main/${n}_run_config.json" 2>/dev/null || true; done
cp logs/rh_main*.log data/rh/train/${TAG}_manifest.json results/rh/pod_logs/main/
echo "ALL DONE $(date)"
echo "BATCH DONE"
