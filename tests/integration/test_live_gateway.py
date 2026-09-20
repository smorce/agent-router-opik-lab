from __future__ import annotations

import os
import urllib.request
from urllib.error import HTTPError

import pytest

from llm_gateway import GatewayUpstreamError, LLMGatewayClient

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
        "http://127.0.0.1:5181/api/v1/private/otel/v1/traces",
        data=b"",
        headers={
            "Content-Type": "application/x-protobuf",
            "projectName": "agent-router-local",
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
    environment = dict(os.environ)
    environment.update(
        {
            "LLM_API_STYLE": "chat_completions",
            "LLAMA_SERVER_ENABLE_THINKING": "false",
            "LLAMA_SERVER_TOP_K": "20",
            "LLAMA_SERVER_MIN_P": "0.0",
        }
    )

    async with LLMGatewayClient.from_env(environment) as client:
        result = await client.complete("Say only: ok", model="Auto")

    assert result.strip()


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

    async with LLMGatewayClient.from_env(environment) as client:
        result = await client.complete("Say only: ok", model="Auto")

    assert result.strip()


@pytest.mark.asyncio
async def test_responses_api_remains_selectable_end_to_end() -> None:
    _require_services()
    environment = dict(os.environ)
    environment["LLM_API_STYLE"] = "responses"

    try:
        async with LLMGatewayClient.from_env(environment) as client:
            result = await client.complete("Say only: ok", model="Auto")
    except GatewayUpstreamError as exc:
        if "status=404" in str(exc):
            pytest.xfail(
                "The current Agent Router auto-configured OpenAI-compatible backend "
                "returns 404 for /v1/responses"
            )
        raise

    assert result.strip()


@pytest.mark.asyncio
async def test_opik_otel_endpoint_accepts_requests() -> None:
    _require_services()
    status = _opik_otel_status()
    if status == 404:
        pytest.xfail(
            "Port 5181 is reachable but does not expose the Opik OTLP endpoint"
        )
    assert status in {200, 400, 415}
