#!/usr/bin/env bash
# Runs on the laptop, right after starting (or restarting) a pod: push the repo, then run pod_setup.sh and
# pod/post_setup.sh on the pod with this project's Jupyter token. Afterwards: ./connect.sh <host> <port>
#   ./pod/remote_setup.sh <host> <port>
# Takes a few minutes (pip installs); output streams as it goes.
set -euo pipefail
HOST="${1:?host}"; PORT="${2:?port}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
source "$HERE/pod/config.sh"
[ -f "$HERE/.env" ] || { echo "no .env with JUPYTER_TOKEN (new_project.sh writes it)"; exit 1; }
source "$HERE/.env"
: "${JUPYTER_TOKEN:?JUPYTER_TOKEN missing from .env}"

"$HERE/pod/push.sh" "$HOST" "$PORT"
ssh -p "$PORT" -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$SSH_USER@$HOST" \
  "export JUPYTER_TOKEN='$JUPYTER_TOKEN'; cd '$REMOTE_ROOT' && bash pod_setup.sh && bash pod/post_setup.sh"
echo "pod ready. next: ./connect.sh $HOST $PORT"
