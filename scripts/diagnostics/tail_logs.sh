#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-backend}"
LINES="${LINES:-200}"

echo "[tail_logs] docker compose logs --tail=${LINES} ${SERVICE}"
docker compose -f docker-compose.yml logs --tail="${LINES}" "${SERVICE}"


