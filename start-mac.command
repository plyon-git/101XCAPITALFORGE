#!/bin/bash
set -eu
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3.11 or newer from https://www.python.org/downloads/ and try again."
  read -r -p "Press Enter to close. "
  exit 1
fi
echo "CapitalForge opens at http://127.0.0.1:8787/app"
exec python3 app.py --open-browser
