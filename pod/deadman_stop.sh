#!/usr/bin/env bash
# Safety net, runs ON the pod under nohup (RunPod only). Waits for a batch to end, gives the driving session
# GRACE_MIN minutes to copy results and stop the pod itself, then stops the pod. Stopping keeps /workspace;
# only GPU billing ends. The batch script should print "BATCH DONE" to its log as its last line.
#   nohup bash pod/deadman_stop.sh <log file> <process pattern> > deadman.log 2>&1 < /dev/null &
# Cancel with:  touch <project dir on pod>/KEEP_POD_UP
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/config.sh"
LOG="${1:?log file}"; PAT="${2:?process pattern}"; GRACE_MIN="${GRACE_MIN:-60}"
env1() { tr '\0' '\n' < /proc/1/environ | sed -n "s/^$1=//p"; }
POD="$(env1 RUNPOD_POD_ID)"; KEY="$(env1 RUNPOD_API_KEY)"
sleep 120
until grep -q "BATCH DONE" "$LOG" 2>/dev/null || ! pgrep -f "$PAT" >/dev/null; do sleep 60; done
echo "$(date -u +%FT%TZ) batch ended; waiting ${GRACE_MIN} min before auto-stop"
sleep $((GRACE_MIN * 60))
[ -e "$REMOTE_ROOT/KEEP_POD_UP" ] && { echo "KEEP_POD_UP present; not stopping"; exit 0; }
echo "$(date -u +%FT%TZ) auto-stopping pod $POD"
runpodctl stop pod "$POD" || curl -s -X POST "https://api.runpod.io/graphql?api_key=$KEY" -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$POD\\\"}) { id desiredStatus } }\"}"
