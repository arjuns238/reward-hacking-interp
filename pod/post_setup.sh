#!/usr/bin/env bash
# Runs ON the pod AFTER pod_setup.sh, and again after every pod stop/restart (the container disk is reset;
# only /workspace survives). This is the home for every pod-environment fix you discover: add it here once
# so it is never rediscovered.
#   - extra python packages the project needs (pod/requirements-pod.txt)
#   - if `import transformers` breaks, remove the image's torchvision/torchaudio (built for the image's old
#     torch; they break the import after the stack upgrade) and check again
#   - runpodctl auth + RUNPOD_POD_ID taken from the container's own environment (RunPod injects them into PID 1;
#     SSH sessions do not inherit them), so the pod can be stopped from an SSH session without re-entering a key
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

REQ="$HERE/requirements-pod.txt"
if grep -q -v -E '^\s*(#|$)' "$REQ" 2>/dev/null; then
  pip install --no-cache-dir -q -r "$REQ" 2>&1 | grep -v -E "notice|WARNING: Running pip" || true
fi

if ! python -c "import transformers" 2>/dev/null; then
  echo "import transformers failed; removing the image's torchvision/torchaudio and retrying"
  pip uninstall -y -q torchvision torchaudio 2>/dev/null || true
fi

env1() { tr '\0' '\n' < /proc/1/environ | sed -n "s/^$1=//p"; }
KEY="$(env1 RUNPOD_API_KEY)"; POD="$(env1 RUNPOD_POD_ID)"
if [ -n "$KEY" ]; then
  runpodctl config --apiKey "$KEY" >/dev/null 2>&1 && echo "runpodctl configured from container env"
  grep -q RUNPOD_POD_ID /etc/profile.d/hf.sh 2>/dev/null || echo "export RUNPOD_POD_ID='$POD'" >> /etc/profile.d/hf.sh
else
  echo "no RUNPOD_API_KEY in the container env (not RunPod?) - skipping runpodctl setup"
fi
grep -q HF_HUB_ENABLE_HF_TRANSFER /etc/profile.d/hf.sh 2>/dev/null || echo "export HF_HUB_ENABLE_HF_TRANSFER=1" >> /etc/profile.d/hf.sh

python - <<'PY'
import torch, transformers
print(f"torch {torch.__version__} cuda={torch.cuda.is_available()} | transformers {transformers.__version__}")
PY
source /etc/profile.d/hf.sh; echo "pod id: ${RUNPOD_POD_ID:-unknown} | project dir: $REMOTE_ROOT"

# vLLM: FlashInfer sampler JIT fails on this image (CUDA 12.4 nvcc lacks --compress-mode, needs >=12.8). Use native sampler.
cat > /etc/profile.d/vllm.sh <<EOF2
export VLLM_USE_FLASHINFER_SAMPLER=0
EOF2
echo "VLLM_USE_FLASHINFER_SAMPLER=0 set (FlashInfer JIT incompatible with image nvcc)"
