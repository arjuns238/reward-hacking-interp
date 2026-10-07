#!/usr/bin/env bash
# Runs on the laptop: bring back small artifacts (results/ and executed notebooks) from the project's file share.
# The equivalent of the legacy pod/pull_results.sh. Large artifacts stay on the share (or in /scratch, which is
# gone when the container stops - write anything you need to keep under /workspace/<project>).
#   ./azure/pull_results.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
KEY="$(storage_key)"
mkdir -p "$REPO/results" "$REPO/notebooks"
for pat in 'results/*' 'notebooks/*.ipynb'; do
  az storage file download-batch --account-name "$AZ_STORAGE" --account-key "$KEY" \
    --source "$AZ_SHARE" --destination "$REPO" --pattern "$pat" --no-progress -o none
done
echo "pulled results/ and executed notebooks/ from share '$AZ_SHARE'"
