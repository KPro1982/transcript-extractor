#!/usr/bin/env bash
set -euo pipefail

# Simple backend runner with consistent env used in Railway
cd "$(dirname "${BASH_SOURCE[0]}")/../.."/backend

# Load .env if present
if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

export PYTHONPATH=${PYTHONPATH:-/app}
export UVICORN_WORKERS=${UVICORN_WORKERS:-1}
export UVICORN_HOST=${UVICORN_HOST:-0.0.0.0}
export UVICORN_PORT=${UVICORN_PORT:-8000}

echo "[run_backend] Starting uvicorn on ${UVICORN_HOST}:${UVICORN_PORT} with PYTHONPATH=${PYTHONPATH}"
exec uvicorn main:app --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" --workers "${UVICORN_WORKERS}" --log-level debug


