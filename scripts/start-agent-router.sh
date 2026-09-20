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

# shellcheck source=lib/opik-otel-env.sh
source "$ROOT_DIR/scripts/lib/opik-otel-env.sh"

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

# OPIK_ENABLED がOTEL送信の正。falseならExporterを止め、trueならOTLPへ送る。
export OTEL_TRACES_EXPORTER
OTEL_TRACES_EXPORTER="$(otel_traces_exporter_from_opik_enabled "${OPIK_ENABLED:-true}")"
export OTEL_METRICS_EXPORTER="${OTEL_METRICS_EXPORTER:-none}"
export OTEL_LOGS_EXPORTER="${OTEL_LOGS_EXPORTER:-none}"
export OTEL_EXPORTER_OTLP_PROTOCOL="${OTEL_EXPORTER_OTLP_PROTOCOL:-http/protobuf}"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="$(
  otel_traces_endpoint_from_opik_base_url "${OPIK_BASE_URL:-http://127.0.0.1:5181}"
)"
export OTEL_EXPORTER_OTLP_HEADERS
OTEL_EXPORTER_OTLP_HEADERS="$(
  otel_otlp_headers_from_opik_project "${OPIK_PROJECT_NAME:-agent-router-local}"
)"
export AI_GATEWAY_TRACING_SEMCONV="${AI_GATEWAY_TRACING_SEMCONV:-openinference}"
export OPENINFERENCE_HIDE_INPUTS="${OPENINFERENCE_HIDE_INPUTS:-false}"
export OPENINFERENCE_HIDE_OUTPUTS="${OPENINFERENCE_HIDE_OUTPUTS:-false}"

# Applicationの X-Session-ID / X-Request-ID をspan属性へ写す。
# metricsには載せず、spanとaccess logだけに限定する。
SPAN_HEADER_MAPPING="$(default_span_request_header_attributes)"
export OTEL_AIGW_SPAN_REQUEST_HEADER_ATTRIBUTES="${OTEL_AIGW_SPAN_REQUEST_HEADER_ATTRIBUTES:-$SPAN_HEADER_MAPPING}"
export OTEL_AIGW_LOG_REQUEST_HEADER_ATTRIBUTES="${OTEL_AIGW_LOG_REQUEST_HEADER_ATTRIBUTES:-$SPAN_HEADER_MAPPING}"

# Windowsブラウザ向け: aigw adminは内部1065、IPv4専用proxyが公開1064を担当する。
ADMIN_PUBLIC_PORT="${AGENT_ROUTER_ADMIN_PORT:-1064}"
ADMIN_UPSTREAM_PORT="${AGENT_ROUTER_ADMIN_UPSTREAM_PORT:-1065}"
PROXY_PID=""

cleanup() {
  if [[ -n "${PROXY_PID}" ]] && kill -0 "${PROXY_PID}" 2>/dev/null; then
    kill "${PROXY_PID}" 2>/dev/null || true
    wait "${PROXY_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}" \
  uv run --link-mode=copy python "$ROOT_DIR/scripts/windows-ipv4-proxy.py" \
    --listen-host 0.0.0.0 \
    --listen-port "${ADMIN_PUBLIC_PORT}" \
    --upstream-host 127.0.0.1 \
    --upstream-port "${ADMIN_UPSTREAM_PORT}" &
PROXY_PID=$!

# proxyの待受開始を短く待つ
for _ in $(seq 1 20); do
  if curl -fsS --max-time 1 "http://127.0.0.1:${ADMIN_PUBLIC_PORT}/health" >/dev/null 2>&1 \
    || ss -ltn "sport = :${ADMIN_PUBLIC_PORT}" | rg -q ":${ADMIN_PUBLIC_PORT}"; then
    break
  fi
  sleep 0.1
done

echo "Windows browser admin proxy: http://127.0.0.1:${ADMIN_PUBLIC_PORT}/health -> 127.0.0.1:${ADMIN_UPSTREAM_PORT}"
echo "Agent Router OpenAI gateway: http://127.0.0.1:1975/v1"
echo "Opik UI: ${OPIK_BASE_URL:-http://127.0.0.1:5181}"
echo "Opik tracing: OPIK_ENABLED=${OPIK_ENABLED:-true} exporter=${OTEL_TRACES_EXPORTER} endpoint=${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT}"

exec "$AIGW_BIN" run --admin-port="${ADMIN_UPSTREAM_PORT}" "$@"
