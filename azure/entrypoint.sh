#!/usr/bin/env bash
# Container entrypoint. Two modes:
#   entrypoint.sh jupyter                 -> JupyterLab on 0.0.0.0:8888 (interactive mode; azure/jupyter_up.sh)
#   entrypoint.sh run <script> [args...]  -> run a project script from /workspace/<project> and exit (batch mode;
#                                            azure/run_job.sh). The container, and the bill, stop when it exits.
# Env (set by the azure/ scripts): PROJ, JUPYTER_TOKEN (jupyter mode), PREFETCH_MODEL (optional HF repo to
# download to the scratch cache before starting, so the first load in a notebook is fast).
set -euo pipefail
PROJ="${PROJ:?PROJ env missing}"
ROOT="/workspace/$PROJ"
mkdir -p "$ROOT" /scratch/hf-cache
cd "$ROOT"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "no GPU visible"

if [ -n "${PREFETCH_MODEL:-}" ]; then
  echo "prefetching $PREFETCH_MODEL into $HF_HOME"
  hf download "$PREFETCH_MODEL" --exclude "*.md" > /dev/null && echo "prefetch done"
fi

case "${1:-jupyter}" in
  jupyter)
    : "${JUPYTER_TOKEN:?JUPYTER_TOKEN env missing}"
    exec jupyter lab \
      --ServerApp.ip=0.0.0.0 --ServerApp.port=8888 --ServerApp.allow_remote_access=True \
      --IdentityProvider.token="$JUPYTER_TOKEN" \
      --ServerApp.root_dir="$ROOT" --ServerApp.open_browser=False --allow-root
    ;;
  run)
    shift
    SCRIPT="${1:?script path relative to $ROOT}"; shift
    echo "===== $(date -u +%FT%TZ) running $SCRIPT $*"
    case "$SCRIPT" in
      *.py) exec python "$SCRIPT" "$@" ;;
      *)    exec bash "$SCRIPT" "$@" ;;
    esac
    ;;
  *)
    exec "$@"
    ;;
esac
