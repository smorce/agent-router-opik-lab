#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ローカル設定を読み込む。
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

"$ROOT_DIR/scripts/check-llama-server.sh"
"$ROOT_DIR/scripts/check-agent-router.sh"
"$ROOT_DIR/scripts/check-opik.sh"

echo "Application -> DummyTaskRouter -> Agent Router -> llama-server:"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}" \
  uv run --link-mode=copy python -m llm_gateway.cli "Hello" --model Auto
