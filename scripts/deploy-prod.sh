#!/usr/bin/env bash
set -euo pipefail

# Stellwerk Prod Deployment
#
# Ziel: deterministisches Deployment auf einem Ubuntu-VM-Host via Docker Compose.
# Dieses Script ist dafür gedacht, auf dem Prod-Host ausgeführt zu werden.
#
# Voraussetzungen:
# - docker
# - docker compose (Plugin)
# - Repo-Code liegt lokal vor (oder wird via git pull aktualisiert)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[prod] building image"
docker-compose -f docker-compose.prod.yml build --pull

echo "[prod] starting services"
docker-compose -f docker-compose.prod.yml up -d

echo "[prod] health check"
docker-compose -f docker-compose.prod.yml ps

echo "[prod] done: open http://<host>:8002"
