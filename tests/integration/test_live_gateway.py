from __future__ import annotations

import json
import os
import re
import urllib.request
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from openai import APIStatusError, AsyncOpenAI

from llm_gateway import GatewayUpstreamError, LLMGatewayClient
from llm_gateway.config import LLMGatewayEnvConfig
from tests.integration.opik_support import find_key_values, opik_base_url, wait_for_opik_payload

pytestmark = pytest.mark.integration


def _integration_enabled() -> bool:
    return os.environ.get("RUN_LLM_INTEGRATION", "").lower() == "true"


def _is_available(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3):
            return True
    except (OSError, TimeoutError):
        return False


def _opik_otel_status() -> int:
    request = urllib.request.Request(
        f"{opik_base_url()}/api/v1/private/otel/v1/traces",
        data=b"",
        headers={
            "Content-Type": "application/x-protobuf",
            "projectName": os.environ.get("OPIK_PROJECT_NAME", "agent-router-local"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status
    except HTTPError as exc:
        return exc.code
    except (OSError, TimeoutError):
        return 0


def _require_services() -> None:
    if not _integration_enabled():
        pytest.skip("Set RUN_LLM_INTEGRATION=true to run live service tests")
    if not _is_available("http://127.0.0.1:2067/v1/models"):
        pytest.skip("llama-server is not available")
    if not _is_available("http://127.0.0.1:1064/health"):
        pytest.skip("Agent Router is not available")


def _require_opik() -> None:
    if not _is_available(opik_base_url()):
        pytest.skip("Opik is not available")


def _assert_contains_generation_options(
    payload: dict[str, object],
    *,
    model: str,
    top_k: int,
    min_p: float,
    enable_thinking: bool,
) -> None:
    values = {"trace": payload.get("trace"), "spans": payload.get("spans")}
    blob = json.dumps(values, default=str)
    models = [item for item in find_key_values(values, "model") if item]
    models.extend(find_key_values(values, "llm.model_name"))
    models.extend(find_key_values(values, "gen_ai.request.model"))
    top_ks = find_key_values(values, "top_k")
    min_ps = find_key_values(values, "min_p")
    thinking_flags = find_key_values(values, "enable_thinking")

    assert model in blob or model in models or any(model in str(item) for item in models), (
        f"Opik trace did not contain model={model!r}; found models={models!r}"
    )
    assert any(_numeric_equals(item, top_k) for item in top_ks) or re.search(
        rf'"top_k"\s*:\\?\s*{top_k}', blob
    ), f"Opik trace did not contain top_k={top_k}; found top_k={top_ks!r}"
    min_p_pattern = r'"min_p"\s*:\\?\s*0(\.0+)?'
    assert any(_numeric_equals(item, min_p) for item in min_ps) or re.search(
        min_p_pattern, blob
    ), f"Opik trace did not contain min_p={min_p}; found min_p={min_ps!r}"
    thinking_literal = "true" if enable_thinking else "false"
    assert any(_boolean_equals(item, enable_thinking) for item in thinking_flags) or re.search(
        rf'"enable_thinking"\s*:\\?\s*{thinking_literal}', blob, flags=re.IGNORECASE
    ), (
        "Opik trace did not contain "
        f"enable_thinking={enable_thinking}; found enable_thinking={thinking_flags!r}"
    )


def _numeric_equals(value: object, expected: float | int) -> bool:
    try:
        return float(value) == float(expected)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _boolean_equals(value: object, expected: bool) -> bool:
    if isinstance(value, bool):
        return value is expected
    if isinstance(value, str):
        return value.strip().lower() == str(expected).lower()
    return False


async def _probe_responses(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> tuple[bool, str]:
    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=0,
    )
    try:
        response = await client.responses.create(model=model, input="Say only: ok")
        text = LLMGatewayClient._extract_text(response)
        if text.strip():
            return True, ""
        return False, "empty textual output"
    except APIStatusError as exc:
        body = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                body = response.text[:300]
            except Exception:
                body = str(exc)
        return False, f"status={exc.status_code} body={body}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_llama_server_health() -> None:
    _require_services()
    assert _is_available("http://127.0.0.1:2067/v1/models")


@pytest.mark.asyncio
async def test_agent_router_health() -> None:
    _require_services()
    assert _is_available("http://127.0.0.1:1064/health")


@pytest.mark.asyncio
async def test_application_to_dummy_router_to_agent_router() -> None:
    _require_services()

    async with LLMGatewayClient.from_env() as client:
        result = await client.complete("1+1は？", model="Auto")

    assert result.strip()


@pytest.mark.asyncio
async def test_chat_completions_preserves_generation_options_end_to_end() -> None:
    _require_services()
    _require_opik()
    marker = f"opik-param-probe-{uuid4().hex}"
    environment = dict(os.environ)
    environment.update(
        {
            "LLM_API_STYLE": "chat_completions",
            "LLAMA_SERVER_ENABLE_THINKING": "false",
            "LLAMA_SERVER_TOP_K": "20",
            "LLAMA_SERVER_MIN_P": "0.0",
        }
    )
    config = LLMGatewayEnvConfig.from_env(environment)

    async with LLMGatewayClient.from_env(environment) as client:
        result = await client.complete(f"Say only: {marker}", model="Auto")

    assert result.strip()
    payload = wait_for_opik_payload(marker)
    _assert_contains_generation_options(
        payload,
        model=config.task_router_default_model,
        top_k=20,
        min_p=0.0,
        enable_thinking=False,
    )


@pytest.mark.asyncio
async def test_thinking_true_is_accepted_end_to_end() -> None:
    _require_services()
    environment = dict(os.environ)
    environment.update(
        {
            "LLM_API_STYLE": "chat_completions",
            "LLAMA_SERVER_ENABLE_THINKING": "true",
            "LLAMA_SERVER_TOP_K": "20",
            "LLAMA_SERVER_MIN_P": "0.0",
        }
    )
    marker = f"opik-thinking-probe-{uuid4().hex}"

    async with LLMGatewayClient.from_env(environment) as client:
        result = await client.complete(f"Say only: {marker}", model="Auto")

    assert result.strip()
    if _is_available(opik_base_url()):
        payload = wait_for_opik_payload(marker)
        _assert_contains_generation_options(
            payload,
            model=LLMGatewayEnvConfig.from_env(environment).task_router_default_model,
            top_k=20,
            min_p=0.0,
            enable_thinking=True,
        )


@pytest.mark.asyncio
async def test_responses_api_llama_server_direct() -> None:
    """Test A: Application → llama-server :2067/v1/responses."""
    _require_services()
    config = LLMGatewayEnvConfig.from_env()
    ok, error = await _probe_responses(
        base_url=config.llama_server_api_base_url,
        api_key=config.llama_server_api_key,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )
    if not ok and "status=404" in error:
        pytest.xfail(
            "Test A FAIL: llama-server :2067/v1/responses returned 404. "
            "This local server is Python aiohttp/exl3 and implements "
            "chat.completions, not the Responses API."
        )
    assert ok, f"Test A failed: llama-server /v1/responses did not succeed ({error})"


@pytest.mark.asyncio
async def test_responses_api_via_agent_router() -> None:
    """Test B: Application → Agent Router :1975/v1/responses → llama-server."""
    _require_services()
    environment = dict(os.environ)
    environment["LLM_API_STYLE"] = "responses"

    try:
        async with LLMGatewayClient.from_env(environment) as client:
            result = await client.complete("Say only: ok", model="Auto")
    except GatewayUpstreamError as exc:
        if "status=404" in str(exc):
            pytest.xfail(
                "Test B FAIL: Agent Router :1975/v1/responses returned 404. "
                "Compare with Test A; this local llama-server also 404s because "
                "the aiohttp/exl3 backend does not implement Responses."
            )
        raise

    assert result.strip()


@pytest.mark.asyncio
async def test_responses_api_isolates_agent_router_auto_config() -> None:
    """Test AとTest Bを並べ、404の切り分け結果を明示する。"""
    _require_services()
    config = LLMGatewayEnvConfig.from_env()
    test_a_ok, test_a_error = await _probe_responses(
        base_url=config.llama_server_api_base_url,
        api_key=config.llama_server_api_key,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )
    test_b_ok, test_b_error = await _probe_responses(
        base_url=config.agent_router_api_base_url,
        api_key=config.agent_router_api_key,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
    )

    if test_a_ok and not test_b_ok and "status=404" in test_b_error:
        pytest.xfail(
            "Test A PASS / Test B FAIL: llama-server accepts /v1/responses, "
            "but the Agent Router standalone auto-config path returns 404. "
            "This is not evidence that Agent Router 1.1 is Responses-incapable."
        )

    if (
        not test_a_ok
        and "status=404" in test_a_error
        and not test_b_ok
        and "status=404" in test_b_error
    ):
        pytest.xfail(
            "Test A FAIL / Test B FAIL: llama-server itself returns 404 for "
            "POST /v1/responses. Agent Router forwarded that backend 404 as "
            "OpenAIBackendError. This is not evidence that Agent Router 1.1 "
            "lacks Responses API support, and it is not isolated to the "
            "Standalone auto-config path."
        )

    assert test_a_ok, f"Test A failed: {test_a_error}"
    assert test_b_ok, f"Test B failed: {test_b_error}"


@pytest.mark.asyncio
async def test_opik_otel_endpoint_accepts_requests() -> None:
    _require_services()
    status = _opik_otel_status()
    if status == 404:
        pytest.xfail(
            "Port 5181 is reachable but does not expose the Opik OTLP endpoint"
        )
    assert status in {200, 400, 415}
