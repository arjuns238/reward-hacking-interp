#!/usr/bin/env bash
# 1-minute check that the image, the share mount and the GPU all work: prints the GPU, RAM, scratch disk and the
# share contents, then exits. Run after setup_once.sh + build.sh + push.sh, and after any image rebuild.
# Costs a few cents. The full pipeline smoke test is then:  ./azure/run_job.sh pod/smoke_test.py
#   ./azure/smoke_gpu.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
[ -f "$REPO/.env" ] && source "$REPO/.env"
export JUPYTER_TOKEN="${JUPYTER_TOKEN:-unused}"
ensure_share
YAML="$(mktemp)"; trap 'rm -f "$YAML"' EXIT
JOB_TIMEOUT_S=900 write_gpu_yaml "$YAML" job \
  "[\"bash\", \"-c\", \"nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv; echo ===RAM; free -g | head -2; echo ===SCRATCH; df -h /scratch | tail -1; echo ===SHARE; ls -la $REMOTE_ROOT; python -c 'import torch, transformers; print(torch.__version__, transformers.__version__, torch.cuda.is_available())'; echo ===DONE\"]"
SMOKE="${AZ_JOB}-smoke"
if az containerapp job show -n "$SMOKE" -g "$AZ_RG" -o none 2>/dev/null; then
  az containerapp job update -n "$SMOKE" -g "$AZ_RG" --yaml "$YAML" -o none
else
  az containerapp job create -n "$SMOKE" -g "$AZ_RG" --yaml "$YAML" -o none
fi
EXEC="$(az containerapp job start -n "$SMOKE" -g "$AZ_RG" --query name -o tsv)"
echo "started $EXEC; waiting (image pull on first run can take a few minutes) ..."
for i in $(seq 1 60); do
  S="$(az containerapp job execution show -n "$SMOKE" -g "$AZ_RG" --job-execution-name "$EXEC" --query properties.status -o tsv)"
  case "$S" in Succeeded|Failed|Stopped) break;; esac
  sleep 10
done
echo "== $S"
az containerapp job logs show -n "$SMOKE" -g "$AZ_RG" --execution "$EXEC" --container main --tail 100 | log_text
