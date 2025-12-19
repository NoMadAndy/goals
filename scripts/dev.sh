#!/usr/bin/env bash
set -euo pipefail

# Dev runner for Stellwerk
# - kills any process listening on PORT
# - starts uvicorn with --reload

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-}"
HOST="${HOST:-}"
RELOAD="${RELOAD:-1}"
CONFIG_PATH="${STELLWERK_CONFIG:-}"

cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  echo "[dev] .venv not found – creating venv"
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[dev] ensuring dependencies"
python -m pip install -U pip >/dev/null
pip install -e ".[dev]" >/dev/null

echo "[dev] resolving host/port (env > stellwerk.toml > defaults)"
RESOLVED="$(CONFIG_PATH="$CONFIG_PATH" HOST="$HOST" PORT="$PORT" python - <<'PY'
import os

from stellwerk.cli import load_server_config

config_path = os.environ.get("CONFIG_PATH") or None
cfg = load_server_config(config_path)

host = os.environ.get("HOST") or cfg.host
port_raw = os.environ.get("PORT")
port = int(port_raw) if port_raw else cfg.port

print(f"{host}:{port}")
PY
)"
HOST="${RESOLVED%:*}"
PORT="${RESOLVED#*:}"

# Kill old process if something is listening on PORT
PIDS="$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$PIDS" ]]; then
  echo "[dev] killing process(es) on :$PORT => $PIDS"
  # Try graceful first
  kill $PIDS 2>/dev/null || true
  sleep 0.5
  # Force if still alive
  PIDS2="$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$PIDS2" ]]; then
    kill -9 $PIDS2 2>/dev/null || true
  fi
fi

echo "[dev] starting Stellwerk on http://$HOST:$PORT"
export STELLWERK_DEBUG="${STELLWERK_DEBUG:-1}"
# Ensure dev always has a valid DB even if .env contains a broken DATABASE_URL.
# Environment variables take precedence over .env in pydantic-settings.
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./data/stellwerk.db}"

RELOAD_FLAG="--reload"
if [[ "${RELOAD}" == "0" ]]; then
  RELOAD_FLAG="--no-reload"
fi

ARGS=("--host" "$HOST" "--port" "$PORT" "$RELOAD_FLAG")
if [[ -n "${CONFIG_PATH}" ]]; then
  ARGS=("--config" "$CONFIG_PATH" "${ARGS[@]}")
fi

exec stellwerk "${ARGS[@]}"
