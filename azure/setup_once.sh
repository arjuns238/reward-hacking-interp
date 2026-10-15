#!/usr/bin/env bash
# ONE-TIME, per Azure account (not per project): creates the shared GPU infrastructure. Safe to re-run; every
# step is skipped if it already exists. Takes ~5 min the first time. Nothing here bills while idle except the
# registry (Basic tier, ~$5/month) and whatever is stored on the file shares.
#   ./azure/setup_once.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"

echo "== providers"
for p in Microsoft.App Microsoft.ContainerRegistry Microsoft.Storage Microsoft.OperationalInsights; do
  [ "$(az provider show -n $p --query registrationState -o tsv)" = Registered ] || az provider register -n $p --wait
done

echo "== resource group $AZ_RG ($AZ_LOCATION)"
az group create -n "$AZ_RG" -l "$AZ_LOCATION" -o none

echo "== Container Apps environment $AZ_ENV"
if ! az containerapp env show -n "$AZ_ENV" -g "$AZ_RG" -o none 2>/dev/null; then
  # eastus has refused this with AKSCapacityHeavyUsage before; westus3 worked. Change AZ_LOCATION in config.sh if needed.
  az containerapp env create -n "$AZ_ENV" -g "$AZ_RG" -l "$AZ_LOCATION" --enable-workload-profiles --logs-destination none -o none
fi

echo "== A100 workload profile $AZ_GPU_PROFILE"
if ! az containerapp env workload-profile show -n "$AZ_ENV" -g "$AZ_RG" --workload-profile-name "$AZ_GPU_PROFILE" -o none 2>/dev/null; then
  az containerapp env workload-profile add -n "$AZ_ENV" -g "$AZ_RG" --workload-profile-name "$AZ_GPU_PROFILE" \
    --workload-profile-type Consumption-GPU-NC24-A100 -o none
fi

echo "== container registry $AZ_ACR"
az acr show -n "$AZ_ACR" -o none 2>/dev/null || az acr create -n "$AZ_ACR" -g "$AZ_RG" --sku Basic --admin-enabled true -o none

echo "== storage account $AZ_STORAGE (file shares)"
az storage account show -n "$AZ_STORAGE" -g "$AZ_RG" -o none 2>/dev/null || \
  az storage account create -n "$AZ_STORAGE" -g "$AZ_RG" -l "$AZ_LOCATION" --sku Standard_LRS --kind StorageV2 \
    --enable-large-file-share --min-tls-version TLS1_2 -o none

echo "== serverless GPU quota for this environment"
az rest --method get --url "https://management.azure.com$(env_id)/usages?api-version=2024-03-01" -o json | python3 -c '
import json, sys
for u in json.load(sys.stdin).get("value", []):
    n = u["name"]["localizedValue"]
    if "gpu" in n.lower(): print("   %s: %s used of %s" % (n, u["currentValue"], u["limit"]))'
echo "done. next: ./azure/build.sh (builds the image, ~10 min), then ./azure/push.sh and ./azure/jupyter_up.sh"
