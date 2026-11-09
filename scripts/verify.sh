#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if command -v codespell &> /dev/null; then
  echo "==> 🔤 Running Codespell spellchecker..."
  codespell --skip="./.git/*,./.pytest_cache/*,./.ruff_cache/*,*.png,*.pem,*.key" -L "hass,dpad,recents,ime"
fi

if command -v ruff &> /dev/null; then
  echo "==> 🔍 Running Ruff linter..."
  ruff check --select E,F,I,UP,SIM,RUF --ignore E501,E402,SIM105,RUF059,RUF022 .
fi

echo "==> 🧪 Running Pytest suite..."
if [ -f "/home/steven/.venvs/adb_mdns/bin/pytest" ]; then
  PYTHONPATH="/home/steven/projects/homelab/homeassistant:$DIR" /home/steven/.venvs/adb_mdns/bin/pytest -v
elif [ -f "/home/steven/.venvs/androidtv_adb/bin/pytest" ]; then
  PYTHONPATH="/home/steven/projects/homelab/homeassistant:$DIR" /home/steven/.venvs/androidtv_adb/bin/pytest -v
else
  PYTHONPATH="/home/steven/projects/homelab/homeassistant:$DIR" pytest -v
fi

echo "==> ✅ All local verification checks passed!"
