#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

if [ ! -x ".venv/Scripts/python.exe" ] && [ ! -x ".venv/bin/python" ]; then
  python -m venv .venv
fi

if [ -x ".venv/Scripts/python.exe" ]; then
  PYTHON=".venv/Scripts/python.exe"
else
  PYTHON=".venv/bin/python"
fi

export PYTHONPATH="${PYTHONPATH:-.}"
exec "$PYTHON" -m uvicorn app.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}"
