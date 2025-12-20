#!/usr/bin/env bash
set -euo pipefail

# Preprod Auto-Deploy (pull-on-change)
#
# This script is intended to be run regularly on the preprod host (e.g. via systemd timer).
# It checks whether origin/main advanced; if yes, it updates the working tree and runs the deploy script.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOCK_FILE="${LOCK_FILE:-/tmp/stellwerk-preprod-autodeploy.lock}"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "[preprod-autodeploy] another deploy is running; exiting"
    exit 0
  fi
fi

if ! command -v git >/dev/null 2>&1; then
  echo "[preprod-autodeploy] ERROR: git not found" >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[preprod-autodeploy] ERROR: not a git work tree: $ROOT_DIR" >&2
  echo "[preprod-autodeploy] Hint: REPO_DIR must be a real 'git clone' (needs a .git directory)." >&2
  echo "[preprod-autodeploy] Check: ls -la '$ROOT_DIR/.git'" >&2
  exit 1
fi

BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"

# Fetch remote updates first

git fetch "$REMOTE" "$BRANCH" --prune

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse "$REMOTE/$BRANCH")"

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "[preprod-autodeploy] no changes ($LOCAL_SHA)"
  exit 0
fi

echo "[preprod-autodeploy] changes detected: $LOCAL_SHA -> $REMOTE_SHA"

# Reuse deploy script (it will do a safe pull) and redeploy.
DEPLOY_ARGS=()
if [[ -n "${DEPLOY_FLAGS:-}" ]]; then
  # shellcheck disable=SC2206
  DEPLOY_ARGS=(${DEPLOY_FLAGS})
fi

./scripts/deploy-preprod.sh --update "${DEPLOY_ARGS[@]}"
