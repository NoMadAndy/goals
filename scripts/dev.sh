#!/usr/bin/env bash
set -euo pipefail

# Dev runner for Stellwerk
# - kills any process listening on PORT
# - starts uvicorn with --reload

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

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
exec python -m uvicorn stellwerk.app:app --reload --host "$HOST" --port "$PORT"
