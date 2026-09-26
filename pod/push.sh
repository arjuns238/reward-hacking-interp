#!/usr/bin/env bash
# Runs on the laptop: copy code, small data, and notebooks to the pod (tar over ssh; pods lack rsync).
#   ./pod/push.sh <host> <port>
# Large data belongs on the pod volume: add an --exclude line below for any big local folder.
set -euo pipefail
HOST="${1:?host}"; PORT="${2:?port}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
source "$HERE/pod/config.sh"
cd "$HERE"
# COPYFILE_DISABLE stops macOS tar from adding ._* AppleDouble files; --no-same-owner avoids chown errors on the pod FS.
COPYFILE_DISABLE=1 tar czf - --exclude '__pycache__' --exclude '.ipynb_checkpoints' --exclude 'data/tracer/answers_raw' --exclude 'data/tracer/slices' \
  src data notebooks pod pod_setup.sh | ssh -p "$PORT" -i "$SSH_KEY" "$SSH_USER@$HOST" \
  "mkdir -p '$REMOTE_ROOT' && tar xzf - --no-same-owner -C '$REMOTE_ROOT' 2>&1 | grep -v 'Ignoring unknown extended header' || true"
echo "pushed src/ data/ notebooks/ pod/ pod_setup.sh -> $HOST:$REMOTE_ROOT/"
