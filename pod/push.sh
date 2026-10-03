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
# Verify: every code file on the pod must match the laptop. 2026-10-01: after a push onto the network volume, two
# edited .py files still had their old content (written earlier from a different pod) while new files arrived fine;
# cause unconfirmed (a plain tar overwrite test worked). Never trust a push without this check.
# The file list travels as DATA on stdin (xargs), never inside the remote command string: a newline-separated list
# pasted into `ssh host "md5sum $LIST"` turns each line into a separate COMMAND on the pod (2026-10-01, a zsh one-off
# ran post_setup.sh and helper scripts this way).
LIST=$(find src pod -type f \( -name '*.py' -o -name '*.sh' -o -name '*.md' \) -not -path '*/__pycache__/*' | sort)
LOCAL=$(printf '%s\n' "$LIST" | xargs md5 -r 2>/dev/null || printf '%s\n' "$LIST" | xargs md5sum)
REMOTE=$(printf '%s\n' "$LIST" | ssh -p "$PORT" -i "$SSH_KEY" "$SSH_USER@$HOST" "cd '$REMOTE_ROOT' && xargs md5sum")
BAD=$(diff <(echo "$LOCAL" | awk '{print $1, $2}' | sort -k2) <(echo "$REMOTE" | awk '{print $1, $2}' | sort -k2) | grep '^>' || true)
if [ -n "$BAD" ]; then
  echo "!!! PUSH VERIFY FAILED — pod copies differ from the laptop:"; echo "$BAD"
  echo "    fix: scp the files listed above, then re-run this check"; exit 1
fi
echo "verified: $(echo "$LIST" | wc -l | tr -d ' ') code files match on the pod"
