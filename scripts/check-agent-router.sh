#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ローカル設定を読み込む。
if test -f "$ROOT_DIR/.env"; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

ADMIN_URL="${AGENT_ROUTER_ADMIN_BASE_URL:-http://127.0.0.1:1064}"
ADMIN_URL="${ADMIN_URL%/}"

if curl -fsS --max-time 10 "${ADMIN_URL}/health" >/dev/null
then
  echo "Agent Router health: PASS (${ADMIN_URL}/health)"
else
  echo "Error: Agent Router health check failed: ${ADMIN_URL}/health" >&2
  exit 1
fi

if curl -fsS --max-time 10 "${ADMIN_URL}/metrics" >/dev/null
then
  echo "Agent Router metrics: PASS (${ADMIN_URL}/metrics)"
else
  echo "Error: Agent Router metrics check failed: ${ADMIN_URL}/metrics" >&2
  exit 1
fi
