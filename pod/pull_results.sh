#!/usr/bin/env bash
# Runs on the laptop: bring back small artifacts (results, executed notebooks). tar over ssh; no rsync on pods.
#   ./pod/pull_results.sh <host> <port>
set -euo pipefail
HOST="${1:?host}"; PORT="${2:?port}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
source "$HERE/pod/config.sh"
mkdir -p "$HERE/results" "$HERE/notebooks"
ssh -p "$PORT" -i "$SSH_KEY" "$SSH_USER@$HOST" "cd '$REMOTE_ROOT' && mkdir -p results && tar czf - results notebooks/*.ipynb" | tar xzf - -C "$HERE"
echo "pulled results/ and executed notebooks/"
