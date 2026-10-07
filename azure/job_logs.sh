#!/usr/bin/env bash
# Follow a batch job's console output (default: the most recent execution). Ctrl-C stops following, not the job.
#   ./azure/job_logs.sh [execution name]
# Stop a running job:  az containerapp job stop -n <job> -g <rg> --job-execution-name <execution>
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
EXEC="${1:-$(az containerapp job execution list -n "$AZ_JOB" -g "$AZ_RG" \
  --query "sort_by(@, &properties.startTime)[-1].name" -o tsv)}"
[ -n "$EXEC" ] || { echo "no executions of $AZ_JOB yet"; exit 1; }
echo "== $EXEC  status: $(az containerapp job execution show -n "$AZ_JOB" -g "$AZ_RG" --job-execution-name "$EXEC" --query properties.status -o tsv)"
az containerapp job logs show -n "$AZ_JOB" -g "$AZ_RG" --execution "$EXEC" --container main --follow --tail 300 | log_text
