from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

JsonValue = Any


def opik_base_url() -> str:
    return os.environ.get("OPIK_BASE_URL", "http://127.0.0.1:5181").rstrip("/")


def opik_project_name() -> str:
    return os.environ.get("OPIK_PROJECT_NAME", "agent-router-local")


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"Opik API returned a non-object payload from {url}")
    return payload


def fetch_opik_traces(size: int = 50) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "project_name": opik_project_name(),
            "size": size,
            "truncate": "false",
        }
    )
    payload = _get_json(f"{opik_base_url()}/api/v1/private/traces?{query}")
    content = payload.get("content", [])
    return [item for item in content if isinstance(item, dict)]


def fetch_opik_spans(trace_id: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "project_name": opik_project_name(),
            "trace_id": trace_id,
            "size": 50,
            "truncate": "false",
        }
    )
    payload = _get_json(f"{opik_base_url()}/api/v1/private/spans?{query}")
    content = payload.get("content", [])
    return [item for item in content if isinstance(item, dict)]


def find_key_values(value: JsonValue, key: str) -> list[JsonValue]:
    found: list[JsonValue] = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return found
            return find_key_values(parsed, key)
        return found
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            if nested_key == key:
                found.append(nested_value)
            found.extend(find_key_values(nested_value, key))
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for item in value:
            found.extend(find_key_values(item, key))
    return found


def wait_for_opik_payload(marker: str, timeout_seconds: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "no traces returned"
    while time.monotonic() < deadline:
        try:
            traces = fetch_opik_traces()
        except (OSError, TimeoutError, json.JSONDecodeError, AssertionError) as exc:
            last_error = str(exc)
            time.sleep(1)
            continue

        for trace in traces:
            blob = json.dumps(trace, default=str)
            if marker not in blob:
                continue
            spans = []
            trace_id = trace.get("id")
            if isinstance(trace_id, str) and trace_id:
                try:
                    spans = fetch_opik_spans(trace_id)
                except (OSError, TimeoutError, json.JSONDecodeError, AssertionError):
                    spans = []
            return {"trace": trace, "spans": spans}

        last_error = f"marker {marker!r} was not present in {len(traces)} traces"
        time.sleep(1)

    raise AssertionError(
        f"Opik trace containing {marker!r} was not found within {timeout_seconds}s: {last_error}"
    )
