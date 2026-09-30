#!/bin/sh
set -eu
cd "$(dirname "$0")"
echo "Open http://127.0.0.1:8787/app in your browser."
exec python3 app.py
