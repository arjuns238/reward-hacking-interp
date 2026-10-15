#!/usr/bin/env bash
# Builds the GPU image IN THE CLOUD (Azure Container Registry does the docker build; nothing to install on the
# laptop) and stores it as $AZ_IMAGE. Re-run only when azure/Dockerfile or pod/requirements-pod.txt changes.
# ~10 min; the build log streams as it goes. Code changes do NOT need a rebuild (azure/push.sh).
#   ./azure/build.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
cd "$REPO"
# .dockerignore keeps the upload tiny: only the two files the Dockerfile copies are sent.
az acr build --registry "$AZ_ACR" --image "$AZ_IMAGE" --file azure/Dockerfile --platform linux/amd64 .
echo "image: $(az acr show -n "$AZ_ACR" --query loginServer -o tsv)/$AZ_IMAGE"
