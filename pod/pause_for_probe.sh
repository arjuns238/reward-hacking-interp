#!/usr/bin/env bash
# One-off (2026-10-02): wait for quote_whole_s0 to finish, pause the main run, run the mode probe, then arm a deadman.
# Kept as a file (not an ssh one-liner) so pkill patterns cannot match the ssh command line.
#   nohup bash pod/pause_for_probe.sh > logs/rh_probe.log 2>&1 &
set -uo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
for f in /etc/profile.d/hf.sh /etc/profile.d/vllm.sh; do [ -f "$f" ] && source "$f"; done
export HF_HOME="${HF_HOME:-/workspace/hf-cache}" VLLM_USE_FLASHINFER_SAMPLER=0
until [ -f adapters/quote_whole_s0/run_config.json ]; do sleep 20; done
echo "quote_whole_s0 done $(date +%T); pausing the main run"
pkill -f "[d]eadman_stop" ; pkill -f "[r]un_rh_main.sh" ; sleep 2 ; pkill -f "[t]rain_lora.py" ; sleep 10
ps -eo pid,args | grep -E "[r]un_rh_main|[t]rain_lora|[d]eadman" || echo "main run paused (nothing left running)"
nvidia-smi --query-gpu=memory.used --format=csv,noheader
echo "=== probe $(date +%T)"
python src/rh/probe_modes.py --models "base,quote_explain_s0=adapters/quote_explain_s0,quote_whole_s0=adapters/quote_whole_s0" \
  && echo "PROBE OK" || echo "!!! PROBE FAILED"
echo "BATCH DONE"
# safety net: stop the pod 40 min after the probe unless the driver resumes the main run (and kills this deadman)
GRACE_MIN=40 setsid nohup bash pod/deadman_stop.sh logs/rh_probe.log "[p]ause_for_probe.sh" > logs/deadman_probe.log 2>&1 < /dev/null &
