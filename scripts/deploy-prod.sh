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

usage() {
	cat <<'USAGE'
Usage: deploy-prod.sh [--update] [--down] [--no-cache] [--logs]

Options:
  --update    Update local repo checkout (git fetch + pull --ff-only).
  --down      Stop stack before rebuild (docker compose down).
  --no-cache  Rebuild images without cache (docker compose build --no-cache).
  --logs      Tail recent logs after deploy (docker compose logs -f --tail=200).
USAGE
}

UPDATE=0
DO_DOWN=0
NO_CACHE=0
TAIL_LOGS=0

while [[ $# -gt 0 ]]; do
	case "$1" in
		--update)
			UPDATE=1
			shift
			;;
		--down)
			DO_DOWN=1
			shift
			;;
		--no-cache)
			NO_CACHE=1
			shift
			;;
		--logs)
			TAIL_LOGS=1
			shift
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "[prod] ERROR: unknown option: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

if ! docker compose version >/dev/null 2>&1; then
	echo "[prod] ERROR: 'docker compose' (Compose v2 Plugin) not found." >&2
	echo "[prod] Please install Docker Compose v2. The legacy 'docker-compose' v1 often fails with: KeyError: 'ContainerConfig'." >&2
	exit 1
fi

if [[ "$UPDATE" -eq 1 ]]; then
	if ! command -v git >/dev/null 2>&1; then
		echo "[prod] ERROR: git not found; cannot --update." >&2
		exit 1
	fi
	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
		echo "[prod] ERROR: not a git work tree: $ROOT_DIR" >&2
		exit 1
	fi

	echo "[prod] updating repo (git pull --ff-only)"
	git fetch origin
	git checkout main
	git pull --ff-only
fi

if [[ "$DO_DOWN" -eq 1 ]]; then
	echo "[prod] stopping services"
	docker compose -f docker-compose.prod.yml down
fi

echo "[prod] building image"
BUILD_ARGS=("-f" "docker-compose.prod.yml" "build" "--pull")
if [[ "$NO_CACHE" -eq 1 ]]; then
	BUILD_ARGS+=("--no-cache")
fi
docker compose "${BUILD_ARGS[@]}"

echo "[prod] starting services"
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "[prod] health check"
docker compose -f docker-compose.prod.yml ps

if [[ "$TAIL_LOGS" -eq 1 ]]; then
	echo "[prod] tailing logs"
	docker compose -f docker-compose.prod.yml logs -f --tail=200
fi

echo "[prod] done: open http://<host>:8002"
