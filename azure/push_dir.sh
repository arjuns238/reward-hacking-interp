#!/usr/bin/env bash
# Runs on the laptop: upload one local folder (e.g. LoRA adapters copied from the RunPod volume) to the project's
# file share, at the same relative path, so containers see it under /workspace/<project>/<dir>. Overwrites files;
# never deletes. push.sh only covers src/ data/ notebooks/ pod/; use this for anything else.
#   ./azure/push_dir.sh adapters/quote_explain_s0
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
DIR="${1:?local folder relative to the repo root}"
cd "$REPO"
[ -d "$DIR" ] || { echo "no such folder: $DIR" >&2; exit 1; }
ensure_share
# create each parent directory on the share first (upload-batch does not create the destination path's parents)
KEY="$(storage_key)"; P=""
IFS='/' read -ra PARTS <<< "$DIR"
for part in "${PARTS[@]}"; do
  P="${P:+$P/}$part"
  az storage directory create --account-name "$AZ_STORAGE" --account-key "$KEY" --share-name "$AZ_SHARE" --name "$P" -o none
done
az storage file upload-batch --account-name "$AZ_STORAGE" --account-key "$KEY" \
  --destination "$AZ_SHARE" --destination-path "$DIR" --source "$DIR" --no-progress -o none
echo "pushed $DIR -> share '$AZ_SHARE' ($REMOTE_ROOT/$DIR in containers)"
