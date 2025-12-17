#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."/backend

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

export PYTHONPATH=${PYTHONPATH:-/app}
export CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-2}
export CELERY_LOGLEVEL=${CELERY_LOGLEVEL:-info}

echo "[run_worker] Starting Celery worker with PYTHONPATH=${PYTHONPATH}"
exec celery -A workers.celery_app worker --loglevel="${CELERY_LOGLEVEL}" --concurrency="${CELERY_CONCURRENCY}"


