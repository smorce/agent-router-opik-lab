#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ローカル設定を読み込む。秘密値は表示しない。
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

AIGW_BIN="${AIGW_BIN:-aigw}"
if ! command -v "$AIGW_BIN" >/dev/null 2>&1; then
  echo "Error: aigw was not found. Install Agent Router v1.1.0 and add it to PATH." >&2
  exit 127
fi

normalize_v1_url() {
  local value="${1%/}"
  if [[ "$value" == */v1 ]]; then
    printf '%s\n' "$value"
  else
    printf '%s/v1\n' "$value"
  fi
}

export OPENAI_BASE_URL
OPENAI_BASE_URL="$(normalize_v1_url "${LLAMA_SERVER_BASE_URL:-http://127.0.0.1:2067}")"
export OPENAI_API_KEY="${LLAMA_SERVER_API_KEY:-sk-local-no-key-required}"
export OTEL_TRACES_EXPORTER="${OTEL_TRACES_EXPORTER:-otlp}"
export OTEL_METRICS_EXPORTER="${OTEL_METRICS_EXPORTER:-none}"
export OTEL_LOGS_EXPORTER="${OTEL_LOGS_EXPORTER:-none}"
export OTEL_EXPORTER_OTLP_PROTOCOL="${OTEL_EXPORTER_OTLP_PROTOCOL:-http/protobuf}"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-http://127.0.0.1:5181/api/v1/private/otel/v1/traces}"
export OTEL_EXPORTER_OTLP_HEADERS="${OTEL_EXPORTER_OTLP_HEADERS:-projectName=${OPIK_PROJECT_NAME:-agent-router-local}}"
export AI_GATEWAY_TRACING_SEMCONV="${AI_GATEWAY_TRACING_SEMCONV:-openinference}"
export OPENINFERENCE_HIDE_INPUTS="${OPENINFERENCE_HIDE_INPUTS:-false}"
export OPENINFERENCE_HIDE_OUTPUTS="${OPENINFERENCE_HIDE_OUTPUTS:-false}"

exec "$AIGW_BIN" run "$@"
