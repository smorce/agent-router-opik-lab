#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ローカル設定を読み込む。APIキーは出力しない。
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

BASE_URL="${LLAMA_SERVER_BASE_URL:-http://127.0.0.1:2067}"
BASE_URL="${BASE_URL%/}"
if [[ "$BASE_URL" != */v1 ]]; then
  BASE_URL="${BASE_URL}/v1"
fi

if curl -fsS --max-time "${LLAMA_SERVER_TIMEOUT_SECONDS:-15}" \
  -H "Authorization: Bearer ${LLAMA_SERVER_API_KEY:-sk-local-no-key-required}" \
  "$BASE_URL/models" >/dev/null; then
  echo "llama-server health: PASS ($BASE_URL/models)"
else
  echo "Error: llama-server health check failed: $BASE_URL/models" >&2
  exit 1
fi
