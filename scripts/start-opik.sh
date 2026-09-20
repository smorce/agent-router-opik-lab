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

OPIK_REPO_DIR="${OPIK_REPO_DIR:-$HOME/opik}"
OPIK_NGINX_PORT="${OPIK_NGINX_PORT:-5181}"

if [[ ! -x "$OPIK_REPO_DIR/opik.sh" ]]; then
  echo "Error: official Opik repository was not found at $OPIK_REPO_DIR" >&2
  echo "Clone https://github.com/comet-ml/opik there before starting Opik." >&2
  exit 127
fi

cd "$OPIK_REPO_DIR"
exec env NGINX_PORT="$OPIK_NGINX_PORT" ./opik.sh "$@"
