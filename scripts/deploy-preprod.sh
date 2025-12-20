#!/usr/bin/env bash
set -euo pipefail

# Stellwerk Preprod Deployment
#
# Ziel: deterministisches, kleines Deployment ohne Provider-Annahmen.
# Dieses Script ist dafür gedacht, auf dem Preprod-Host ausgeführt zu werden.
#
# Voraussetzungen auf dem Preprod-Host:
# - docker
# - docker compose (Plugin)
# - Repo-Code liegt lokal vor (oder wird via git pull aktualisiert)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[preprod] building image"
docker-compose -f docker-compose.preprod.yml build --pull

echo "[preprod] starting services"
docker-compose -f docker-compose.preprod.yml up -d

echo "[preprod] health check"
# simple curl-less check: container status

docker-compose -f docker-compose.preprod.yml ps

echo "[preprod] done: open http://<host>:8002"
