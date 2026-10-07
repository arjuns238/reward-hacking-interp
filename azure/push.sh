#!/usr/bin/env bash
# Runs on the laptop: copy code, small data, notebooks and the run scripts to the project's file share, which
# every container mounts at /workspace/<project>. Overwrites files; never deletes. The equivalent of the legacy
# pod/push.sh. Takes ~30 s for a small repo.
#   ./azure/push.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
ensure_share
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
cd "$REPO"
# tar handles the excludes (upload-batch has no exclude option); COPYFILE_DISABLE stops macOS ._* files.
COPYFILE_DISABLE=1 tar cf - --exclude '__pycache__' --exclude '.ipynb_checkpoints' --exclude '*.pyc' \
  src data notebooks pod | tar xf - -C "$STAGE"
az storage file upload-batch --account-name "$AZ_STORAGE" --account-key "$(storage_key)" \
  --destination "$AZ_SHARE" --source "$STAGE" --no-progress -o none
echo "pushed src/ data/ notebooks/ pod/ -> share '$AZ_SHARE' (mounted at $REMOTE_ROOT in containers)"
