#!/usr/bin/env bash
# Opikの設定値からAgent Router向けOTEL環境変数を組み立てる。

normalize_opik_base_url() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%/}"
  printf '%s\n' "$value"
}

otel_traces_exporter_from_opik_enabled() {
  local raw="${1:-true}"
  local normalized
  normalized="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$normalized" in
    true|1|yes)
      printf 'otlp\n'
      ;;
    false|0|no)
      printf 'none\n'
      ;;
    *)
      echo "Error: OPIK_ENABLED must be true or false" >&2
      return 1
      ;;
  esac
}

otel_traces_endpoint_from_opik_base_url() {
  local base
  base="$(normalize_opik_base_url "${1:-http://127.0.0.1:5181}")"
  if [[ -z "$base" ]]; then
    echo "Error: OPIK_BASE_URL must not be empty" >&2
    return 1
  fi
  printf '%s/api/v1/private/otel/v1/traces\n' "$base"
}

otel_otlp_headers_from_opik_project() {
  local project="${1:-agent-router-local}"
  printf 'projectName=%s\n' "$project"
}

default_span_request_header_attributes() {
  printf '%s\n' "agent-session-id:session.id,x-session-id:session.id,x-request-id:request.id"
}
