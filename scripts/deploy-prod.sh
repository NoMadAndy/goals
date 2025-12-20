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

if ! docker compose version >/dev/null 2>&1; then
	echo "[prod] ERROR: 'docker compose' (Compose v2 Plugin) not found." >&2
	echo "[prod] Please install Docker Compose v2. The legacy 'docker-compose' v1 often fails with: KeyError: 'ContainerConfig'." >&2
	exit 1
fi

echo "[prod] building image"
docker compose -f docker-compose.prod.yml build --pull

echo "[prod] starting services"
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "[prod] health check"
docker compose -f docker-compose.prod.yml ps

echo "[prod] done: open http://<host>:8002"
