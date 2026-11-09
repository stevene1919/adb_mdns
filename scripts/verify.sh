#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if command -v codespell &> /dev/null; then
  echo "==> 🔤 Running Codespell spellchecker..."
  codespell --skip="./.git/*,./.pytest_cache/*,./.ruff_cache/*,*.png,*.pem,*.key" -L "hass,dpad,recents,ime"
fi

echo "==> 🔍 Running Ruff linter..."
if [ -f "/home/steven/.venvs/androidtv_adb/bin/ruff" ]; then
  /home/steven/.venvs/androidtv_adb/bin/ruff check .
elif command -v ruff &> /dev/null; then
  ruff check .
fi

echo "==> 🧪 Running Pytest suite..."
if [ -f "/home/steven/.venvs/adb_mdns/bin/pytest" ]; then
  PYTHONPATH="/home/steven/projects/homelab/homeassistant:$DIR" /home/steven/.venvs/adb_mdns/bin/pytest -v
elif [ -f "/home/steven/.venvs/androidtv_adb/bin/pytest" ]; then
  PYTHONPATH="/home/steven/projects/homelab/homeassistant:$DIR" /home/steven/.venvs/androidtv_adb/bin/pytest -v
else
  PYTHONPATH="/home/steven/projects/homelab/homeassistant:$DIR" pytest -v
fi

if command -v docker &> /dev/null; then
  echo "==> 🏛️ Running official Home Assistant Hassfest validator..."
  docker run --rm -v "$DIR"://github/workspace ghcr.io/home-assistant/hassfest
  echo "==> ✅ All local verification and Hassfest checks passed!"
else
  echo "==> ⚠️  Hassfest checks skipped (docker not found)"
  echo "==> ✅ Local verification passed (Hassfest checks skipped)"
fi
