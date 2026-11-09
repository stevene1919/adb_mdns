#!/usr/bin/env bash
set -e

REMOTE_HOST="steven@192.168.50.200"
REMOTE_PATH="/opt/usb/homeassistant/custom_components/adb_mdns/"
LOCAL_PATH="$(dirname "$0")/../custom_components/adb_mdns/"

RUN_CHECK=false
for arg in "$@"; do
  if [ "$arg" == "--check" ] || [ "$arg" == "-c" ]; then
    RUN_CHECK=true
  fi
done

echo "==> 📤 Syncing adb_mdns files to vodka ($REMOTE_HOST:$REMOTE_PATH)..."
rsync -avz --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' --exclude '.pytest_cache' --exclude '.ruff_cache' "$LOCAL_PATH" "$REMOTE_HOST:$REMOTE_PATH"

if [ "$RUN_CHECK" = true ]; then
  echo "==> 🔍 Validating Home Assistant configuration on vodka..."
  ssh -i ~/.ssh/id_ed25519 "$REMOTE_HOST" "docker exec homeassistant python3 -m homeassistant --config /config --script check_config"
  echo "==> ✅ Sync and HA config check completed successfully!"
else
  echo "==> ✅ Sync completed successfully (pass --check or -c to run HA config check)."
fi
