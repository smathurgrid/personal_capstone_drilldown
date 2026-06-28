#!/usr/bin/env bash
# Re-add LAN host routes for the worker Macs so their traffic leaves via the LAN
# interface instead of the corporate VPN tunnel. Run after a reboot / Wi-Fi or VPN
# reconnect if the workers stop being reachable.
#
# Usage:  sudo bash scripts/add_worker_routes.sh
#         sudo bash scripts/add_worker_routes.sh en0 192.168.68.113 192.168.68.115
set -euo pipefail

IFACE="${1:-en0}"
shift || true

# Worker IPs: from args, else parsed from .env IMAGE_OLLAMA_BASES.
if [ "$#" -gt 0 ]; then
  IPS=("$@")
else
  ENV_FILE="$(dirname "$0")/../.env"
  LINE="$(grep -E '^IMAGE_OLLAMA_BASES=' "$ENV_FILE" | tail -1 | cut -d= -f2-)"
  IFS=',' read -r -a BASES <<< "$LINE"
  IPS=()
  for b in "${BASES[@]}"; do
    ip="$(printf '%s' "$b" | sed -E 's#https?://##; s#:.*##')"
    [ -n "$ip" ] && IPS+=("$ip")
  done
fi

echo "Interface: $IFACE"
for ip in "${IPS[@]}"; do
  route delete -host "$ip" >/dev/null 2>&1 || true
  route -n add -host "$ip" -interface "$IFACE" && echo "  routed $ip -> $IFACE"
done
echo "Done. Verify:  curl -s -m5 http://${IPS[0]}:11434/api/tags >/dev/null && echo OK"
