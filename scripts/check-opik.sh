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

OPIK_URL="${OPIK_BASE_URL:-http://127.0.0.1:5181}"
OPIK_URL="${OPIK_URL%/}"
OTEL_URL="${OPIK_URL}/api/v1/private/otel/v1/traces"
PROJECT_NAME="${OPIK_PROJECT_NAME:-agent-router-local}"

if ! status="$(
  curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
    -X POST "$OTEL_URL" \
    -H 'Content-Type: application/x-protobuf' \
    -H "projectName: ${PROJECT_NAME}" \
    --data-binary ''
)"; then
  echo "Error: Opik OTLP endpoint is unreachable: $OTEL_URL" >&2
  exit 1
fi

case "$status" in
  200|400|415)
    echo "Opik OTLP endpoint: PASS ($OTEL_URL, HTTP $status)"
    ;;
  *)
    echo "Error: Opik OTLP endpoint check failed: $OTEL_URL (HTTP $status)" >&2
    exit 1
    ;;
esac
