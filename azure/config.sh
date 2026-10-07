# Sourced by every azure/ script (laptop side). Filled in by new_project.sh; edit by hand if needed.
#
# Two kinds of names:
#   * ACCOUNT-WIDE (shared by all projects, created once by azure/setup_once.sh): resource group, Container Apps
#     environment with the A100 profile, container registry, storage account.
#   * PER-PROJECT: the file share (mounted at /workspace in every container), the Jupyter app, the batch job.
PROJ="judge-rewards-hacking"

AZ_SUBSCRIPTION="${AZ_SUBSCRIPTION:-85c1c87a-bc49-47cb-b661-645d21fdad6b}"   # "Azure subscription 1" (Microsoft for Startups credits)
AZ_LOCATION="${AZ_LOCATION:-westus3}"          # serverless A100 regions: eastus westus westus3 canadacentral swedencentral australiaeast ...
AZ_RG="${AZ_RG:-mi-gpu}"                       # resource group holding everything below
AZ_ENV="${AZ_ENV:-mi-gpu-env}"                 # Container Apps environment (workload-profiles type)
AZ_GPU_PROFILE="${AZ_GPU_PROFILE:-gpu-a100}"   # workload profile name; type Consumption-GPU-NC24-A100 (1x A100 80GB, 24 vCPU, 220 GiB RAM)
AZ_GPU_CPU="${AZ_GPU_CPU:-24}"                 # a GPU container takes the whole profile
AZ_GPU_MEM="${AZ_GPU_MEM:-220Gi}"

# Globally unique names (letters/digits only) derived from the subscription id so they are stable across projects.
_SUFFIX="$(printf '%s' "$AZ_SUBSCRIPTION" | shasum | cut -c1-8)"
AZ_ACR="${AZ_ACR:-migpu${_SUFFIX}}"            # container registry (image lives here; built in the cloud by azure/build.sh)
AZ_STORAGE="${AZ_STORAGE:-migpu${_SUFFIX}}"    # storage account for the per-project file shares

AZ_SHARE="${AZ_SHARE:-$PROJ}"                  # file share for this project -> mounted at /workspace/<proj> (see REMOTE_ROOT)
AZ_IMAGE="${AZ_IMAGE:-judge-rh:latest}"   # project image: template stack + vLLM, peft, bitsandbytes, datasets (pod/requirements-pod.txt)
AZ_APP="${AZ_APP:-jl-$PROJ}"                   # the Jupyter container app (interactive mode)
AZ_JOB="${AZ_JOB:-job-$PROJ}"                  # the batch job (script mode)

REMOTE_ROOT="/workspace/$PROJ"                 # same path convention as the legacy pod scripts
