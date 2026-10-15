#!/usr/bin/env bash
# Stop interactive mode: deletes the Jupyter container app, which ends the GPU bill. The file share (code,
# notebooks, results) is untouched; /scratch (model cache) is gone. azure/jupyter_up.sh recreates it in ~1 min.
# Run this at the end of EVERY session, same discipline as "stop the pod when done".
#   ./azure/jupyter_down.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
if az containerapp show -n "$AZ_APP" -g "$AZ_RG" -o none 2>/dev/null; then
  az containerapp delete -n "$AZ_APP" -g "$AZ_RG" --yes -o none
  echo "Jupyter app $AZ_APP deleted; GPU billing stopped."
else
  echo "Jupyter app $AZ_APP is not running."
fi
"$AZ_HERE/status.sh"
