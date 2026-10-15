#!/usr/bin/env bash
# Batch mode: run one project script on the A100 as a Container Apps job and exit. The container (and the bill)
# stops by itself when the script ends, so no deadman timer is needed. Restartable scripts (skip finished items)
# are still the rule: an interrupted job is re-run with the same command.
#   ./azure/run_job.sh <script relative to the repo root> [args...]
#   e.g. ./azure/run_job.sh pod/smoke_test.py --model Qwen/Qwen3-0.6B
#        PREFETCH_MODEL=Qwen/Qwen3.5-35B-A3B ./azure/run_job.sh pod/run_phaseB_batch.sh
# Push code first (azure/push.sh). Follow the log with azure/job_logs.sh. Max run time 48 h (JOB_TIMEOUT_S).
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
SCRIPT="${1:?script path relative to the repo root}"; shift
[ -e "$REPO/$SCRIPT" ] || echo "warning: $SCRIPT not found locally (is it on the share?)"
[ -f "$REPO/.env" ] && source "$REPO/.env"
export JUPYTER_TOKEN="${JUPYTER_TOKEN:-unused}" PREFETCH_MODEL="${PREFETCH_MODEL:-}"

ensure_share
ARGS_JSON="$(python3 -c 'import json,sys; print(json.dumps(["run"]+sys.argv[1:]))' "$SCRIPT" "$@")"
YAML="$(mktemp)"; trap 'rm -f "$YAML"' EXIT
write_gpu_yaml "$YAML" job "$ARGS_JSON"

if az containerapp job show -n "$AZ_JOB" -g "$AZ_RG" -o none 2>/dev/null; then
  az containerapp job update -n "$AZ_JOB" -g "$AZ_RG" --yaml "$YAML" -o none
else
  az containerapp job create -n "$AZ_JOB" -g "$AZ_RG" --yaml "$YAML" -o none
fi
EXEC="$(az containerapp job start -n "$AZ_JOB" -g "$AZ_RG" --query name -o tsv)"
echo "started job $AZ_JOB execution $EXEC: $SCRIPT $*"
echo "follow:  ./azure/job_logs.sh $EXEC      status:  ./azure/status.sh"
