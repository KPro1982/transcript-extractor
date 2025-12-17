#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ENV_FILE="${ENV_FILE:-backend/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
WORKER_SERVICE="${WORKER_SERVICE:-worker}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"
PING_TIMEOUT="${PING_TIMEOUT:-60}"

if [[ -f "${ENV_FILE}" ]]; then
  echo "[smoke] Loading env from ${ENV_FILE}"
  set -a
  source "${ENV_FILE}"
  set +a
fi

echo "[smoke] Building services..."
docker compose -f "${COMPOSE_FILE}" build "${BACKEND_SERVICE}" "${WORKER_SERVICE}"

cleanup() {
  echo "[smoke] Stopping services..."
  docker compose -f "${COMPOSE_FILE}" down
}
trap cleanup EXIT

echo "[smoke] Starting backend + worker..."
docker compose -f "${COMPOSE_FILE}" up -d "${BACKEND_SERVICE}" "${WORKER_SERVICE}"

echo "[smoke] Waiting for backend health at ${HEALTH_URL}"
SECONDS=0
until curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; do
  if (( SECONDS > PING_TIMEOUT )); then
    echo "[smoke][FAIL] Backend health not ready after ${PING_TIMEOUT}s"
    docker compose -f "${COMPOSE_FILE}" logs "${BACKEND_SERVICE}"
    exit 1
  fi
  sleep 2
done
echo "[smoke][OK] Backend health ready"

echo "[smoke] Checking Celery worker ping..."
python - <<'PY'
import sys
from celery import Celery
import os

broker = os.environ.get("REDIS_URL") or os.environ.get("REDIS_URL".lower()) or "redis://localhost:6379"
app = Celery("check", broker=broker, backend=broker)
try:
    resp = app.control.ping(timeout=5)
    if not resp:
        print("[smoke][FAIL] No worker responses", file=sys.stderr)
        sys.exit(1)
    print(f"[smoke][OK] Worker ping responses: {resp}")
except Exception as exc:  # noqa: BLE001
    print(f"[smoke][FAIL] Worker ping error: {exc}", file=sys.stderr)
    sys.exit(1)
PY

echo "[smoke][PASS] Smoke tests completed successfully"


