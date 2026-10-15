# Shared helpers for the azure/ scripts. Source it; do not run it.
set -euo pipefail
AZ_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$AZ_HERE/.." && pwd)"
source "$AZ_HERE/config.sh"

# Every az call goes to the credits subscription, and the SyntaxWarning noise from the brew-installed CLI is dropped.
az() { command az "$@" 2> >(grep -v -E "SyntaxWarning|following actions|^\s*$" >&2); }
az account set --subscription "$AZ_SUBSCRIPTION"

env_id() { az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" --query id -o tsv; }

# Registry login (admin user; the image is private to this account).
acr_info() {
  ACR_SERVER="$(az acr show -n "$AZ_ACR" --query loginServer -o tsv)"
  ACR_USER="$(az acr credential show -n "$AZ_ACR" --query username -o tsv)"
  ACR_PW="$(az acr credential show -n "$AZ_ACR" --query 'passwords[0].value' -o tsv)"
}

storage_key() { az storage account keys list -n "$AZ_STORAGE" -g "$AZ_RG" --query '[0].value' -o tsv; }

# The project's file share, and its link into the Container Apps environment (what a container mounts).
ensure_share() {
  local key; key="$(storage_key)"
  az storage share-rm create --storage-account "$AZ_STORAGE" -g "$AZ_RG" --name "$AZ_SHARE" --quota 1024 -o none 2>/dev/null || true
  if ! az containerapp env storage show -n "$AZ_ENV" -g "$AZ_RG" --storage-name "$AZ_SHARE" -o none 2>/dev/null; then
    az containerapp env storage set -n "$AZ_ENV" -g "$AZ_RG" --storage-name "$AZ_SHARE" \
      --azure-file-account-name "$AZ_STORAGE" --azure-file-account-key "$key" \
      --azure-file-share-name "$AZ_SHARE" --access-mode ReadWrite -o none
  fi
}

# The YAML for a GPU container (app or job). Args: kind (app|job), then the container args as a JSON array string.
# Extra env is passed through EXTRA_ENV_YAML (already-indented lines). Writes to the path in $1.
write_gpu_yaml() {
  local out="$1" kind="$2" args_json="$3"
  acr_info
  local common_cfg
  common_cfg="    registries:
      - server: ${ACR_SERVER}
        username: ${ACR_USER}
        passwordSecretRef: acr-pw
    secrets:
      - name: acr-pw
        value: ${ACR_PW}
      - name: jupyter-token
        value: ${JUPYTER_TOKEN:-unused}"
  local container
  container="    containers:
      - name: main
        image: ${ACR_SERVER}/${AZ_IMAGE}
        args: ${args_json}
        env:
          - name: PROJ
            value: ${PROJ}
          - name: JUPYTER_TOKEN
            secretRef: jupyter-token
          - name: PREFETCH_MODEL
            value: \"${PREFETCH_MODEL:-}\"
${EXTRA_ENV_YAML:-}
        resources:
          cpu: ${AZ_GPU_CPU}
          memory: ${AZ_GPU_MEM}
        volumeMounts:
          - volumeName: ws
            mountPath: ${REMOTE_ROOT}
    volumes:
      - name: ws
        storageType: AzureFile
        storageName: ${AZ_SHARE}"
  umask 077
  if [ "$kind" = app ]; then
    cat > "$out" <<EOF
location: ${AZ_LOCATION}
properties:
  environmentId: $(env_id)
  workloadProfileName: ${AZ_GPU_PROFILE}
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8888
      transport: auto
      allowInsecure: false
${INGRESS_RESTRICTIONS_YAML:-}
${common_cfg}
  template:
${container}
    scale:
      minReplicas: 1
      maxReplicas: 1
EOF
  else
    cat > "$out" <<EOF
location: ${AZ_LOCATION}
properties:
  environmentId: $(env_id)
  workloadProfileName: ${AZ_GPU_PROFILE}
  configuration:
    triggerType: Manual
    replicaTimeout: ${JOB_TIMEOUT_S:-172800}
    replicaRetryLimit: 0
    manualTriggerConfig:
      parallelism: 1
      replicaCompletionCount: 1
${common_cfg}
  template:
${container}
EOF
  fi
}

# Turn the job/app log stream (one JSON object per line) back into plain text. Azure does not escape quotes
# inside the "Log" value, so lines containing quotes are not valid JSON; fall back to a regex for those.
log_text() { python3 -c '
import sys, json, re
for line in sys.stdin:
    line = line.rstrip("\n")
    try: print(json.loads(line).get("Log", line), flush=True); continue
    except Exception: pass
    m = re.search(r"\"Log\":\"(.*)\"\}\s*$", line)
    print(m.group(1) if m else line, flush=True)
'; }
