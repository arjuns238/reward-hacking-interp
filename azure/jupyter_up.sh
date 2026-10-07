#!/usr/bin/env bash
# Interactive mode: start (or restart) a container running JupyterLab on the A100, mounted on the project's
# share, reachable at an https URL, and point this project's Jupyter MCP config at it. Replaces the legacy
# "start pod -> pod_setup.sh -> connect.sh". Bills ~$1.80/h from the moment it is up until azure/jupyter_down.sh.
#   ./azure/jupyter_up.sh [HF model repo to prefetch, e.g. Qwen/Qwen3.5-35B-A3B]
# First start after a rebuild takes a few minutes (image pull); later starts ~1 min. Prefetching a 70 GB model
# adds ~3 min. Only your current public IP may reach the URL (edit ALLOW_IPS to change).
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"
[ -f "$REPO/.env" ] || { echo "no .env with JUPYTER_TOKEN (new_project.sh writes it)"; exit 1; }
source "$REPO/.env"; : "${JUPYTER_TOKEN:?JUPYTER_TOKEN missing from .env}"
export PREFETCH_MODEL="${1:-}"

ensure_share
MY_IP="$(curl -s --max-time 10 https://api.ipify.org || true)"
ALLOW_IPS="${ALLOW_IPS:-$MY_IP}"
INGRESS_RESTRICTIONS_YAML=""
if [ -n "$ALLOW_IPS" ]; then
  INGRESS_RESTRICTIONS_YAML="      ipSecurityRestrictions:"
  for ip in $ALLOW_IPS; do
    INGRESS_RESTRICTIONS_YAML+="
        - name: allow-${ip//./-}
          ipAddressRange: ${ip}/32
          action: Allow"
  done
fi
export INGRESS_RESTRICTIONS_YAML
YAML="$(mktemp)"; trap 'rm -f "$YAML"' EXIT
write_gpu_yaml "$YAML" app '["jupyter"]'

if az containerapp show -n "$AZ_APP" -g "$AZ_RG" -o none 2>/dev/null; then
  az containerapp update -n "$AZ_APP" -g "$AZ_RG" --yaml "$YAML" -o none
else
  az containerapp create -n "$AZ_APP" -g "$AZ_RG" --yaml "$YAML" -o none
fi
FQDN="$(az containerapp show -n "$AZ_APP" -g "$AZ_RG" --query properties.configuration.ingress.fqdn -o tsv)"
URL="https://$FQDN"

echo "waiting for JupyterLab at $URL (image pull + start; a few minutes the first time) ..."
for i in $(seq 1 60); do
  if curl -sf --max-time 10 "$URL/api?token=$JUPYTER_TOKEN" > /dev/null; then
    echo "JupyterLab up: $URL/lab?token=<token from .env>"
    # Point the Jupyter MCP (Claude Code + Codex) at the container instead of the legacy SSH tunnel.
    python3 - "$REPO" "$URL" <<'PY'
import json, re, sys, pathlib
repo, url = pathlib.Path(sys.argv[1]), sys.argv[2]
p = repo / ".mcp.json"
if p.exists():
    d = json.loads(p.read_text()); d["mcpServers"]["jupyter"]["env"]["JUPYTER_URL"] = url
    p.write_text(json.dumps(d, indent=2) + "\n")
p = repo / ".codex" / "config.toml"
if p.exists():
    p.write_text(re.sub(r'JUPYTER_URL = ".*"', f'JUPYTER_URL = "{url}"', p.read_text()))
print("MCP config now points at", url, "(restart Claude Code / reconnect the jupyter MCP server)")
PY
    echo "when done: ./azure/jupyter_down.sh   (nothing else stops the bill)"
    exit 0
  fi
  sleep 10
done
echo "JupyterLab did not come up in 10 min. Logs:"
az containerapp logs show -n "$AZ_APP" -g "$AZ_RG" --tail 50 | log_text
exit 1
