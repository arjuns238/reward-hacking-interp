#!/usr/bin/env bash
# Runs ON the pod after pod_setup.sh + post_setup.sh. Pulls the model(s) and any large datasets onto the volume,
# once per volume. HF_HOME is set by pod_setup.sh to the volume. Export HF_TOKEN first for gated repos (it also
# raises rate limits for public ones).
#   MODEL=org/name bash pod/bootstrap.sh
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/config.sh"
MODEL="${MODEL:?set MODEL=org/name (the HF repo of the model under study)}"
mkdir -p "$REMOTE_ROOT/acts" "$REMOTE_ROOT/results" "$REMOTE_ROOT/data"
export HF_HUB_ENABLE_HF_TRANSFER=1

echo "== model: $MODEL"
hf download "$MODEL" --exclude "*.md" >/dev/null && echo "model cached in $HF_HOME"

# == project datasets: add hf_hub_download / hf download calls here, writing under $REMOTE_ROOT/data

echo "== done. Layout:"; du -sh "$REMOTE_ROOT"/data "$HF_HOME" 2>/dev/null
