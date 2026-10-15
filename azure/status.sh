#!/usr/bin/env bash
# What is running (and billing) right now for this project, plus recent job executions.
#   ./azure/status.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
echo "== Jupyter app $AZ_APP"
if az containerapp show -n "$AZ_APP" -g "$AZ_RG" -o none 2>/dev/null; then
  az containerapp show -n "$AZ_APP" -g "$AZ_RG" --query "{running:properties.runningStatus, url:properties.configuration.ingress.fqdn}" -o table
  echo "   (billing ~\$1.80/h while it exists; ./azure/jupyter_down.sh stops it)"
else
  echo "   not running"
fi
echo "== job $AZ_JOB (last 5 executions)"
az containerapp job execution list -n "$AZ_JOB" -g "$AZ_RG" \
  --query "sort_by(@, &properties.startTime)[-5:].{execution:name, status:properties.status, started:properties.startTime, ended:properties.endTime}" \
  -o table 2>/dev/null || echo "   no job yet"
