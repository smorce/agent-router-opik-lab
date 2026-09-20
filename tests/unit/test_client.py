from types import SimpleNamespace

import pytest

from llm_gateway.client import LLMGatewayClient, is_retryable_gateway_error
from llm_gateway.config import LLMGatewayEnvConfig
from llm_gateway.errors import (
    GatewayConnectionError,
    GatewayTimeoutError,
    GatewayUpstreamError,
)


def make_config(**overrides: str) -> LLMGatewayEnvConfig:
    values = {
        "AGENT_ROUTER_BASE_URL": "http://router:1975",
        "AGENT_ROUTER_API_KEY": "unused",
        "LLAMA_SERVER_ENABLE_THINKING": "false",
        "LLAMA_SERVER_MAX_RETRIES": "2",
    }
    values.update(overrides)
    return LLMGatewayEnvConfig.from_env(values)


class FakeChatCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.response


class FakeOpenAIClient:
    def __init__(
        self,
        chat_completions: FakeChatCompletions,
        responses: FakeResponses | None = None,
    ) -> None:
        self.chat = SimpleNamespace(completions=chat_completions)
        self.responses = responses or FakeResponses(SimpleNamespace(output_text=""))

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_complete_routes_auto_and_preserves_llama_parameters() -> None:
    chat = FakeChatCompletions(
        [SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="2"))])]
    )
    client = LLMGatewayClient(
        make_config(),
        openai_client=FakeOpenAIClient(chat),
        sleeper=lambda _: _noop(),
    )

    result = await client.complete("1+1は？", model="Auto", request_id="req-1")

    assert result == "2"
    request = chat.calls[0]
    assert request["model"] == "qwen3.8-27b-exl3-3.5bpw-wm"
    assert request["max_tokens"] == 1000
    assert request["temperature"] == 0.7
    assert request["top_p"] == 0.8
    assert request["extra_body"] == {
        "top_k": 20,
        "min_p": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    assert request["extra_headers"] == {"X-Request-ID": "req-1"}


@pytest.mark.asyncio
async def test_responses_api_remains_available() -> None:
    chat = FakeChatCompletions([])
    responses = FakeResponses(SimpleNamespace(output_text="response text"))
    fake = FakeOpenAIClient(chat, responses)
    client = LLMGatewayClient(
        make_config(LLM_API_STYLE="responses"),
        openai_client=fake,
        sleeper=lambda _: _noop(),
    )

    result = await client.complete("Hello", model="explicit-model")

    assert result == "response text"
    assert responses.calls[0]["model"] == "explicit-model"
    assert responses.calls[0]["max_output_tokens"] == 1000


@pytest.mark.asyncio
async def test_retry_is_limited_and_does_not_use_sdk_retries() -> None:
    chat = FakeChatCompletions(
        [
            GatewayTimeoutError("temporary timeout"),
            GatewayTimeoutError("temporary timeout"),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            ),
        ]
    )
    fake = FakeOpenAIClient(chat)
    client = LLMGatewayClient(
        make_config(LLAMA_SERVER_MAX_RETRIES="2"),
        openai_client=fake,
        sleeper=lambda _: _noop(),
    )

    assert await client.complete("Hello") == "ok"
    assert len(chat.calls) == 3


@pytest.mark.asyncio
async def test_non_retryable_error_is_not_retried() -> None:
    chat = FakeChatCompletions([GatewayUpstreamError("bad request")])
    client = LLMGatewayClient(
        make_config(LLAMA_SERVER_MAX_RETRIES="2"),
        openai_client=FakeOpenAIClient(chat),
        sleeper=lambda _: _noop(),
    )

    with pytest.raises(GatewayUpstreamError):
        await client.complete("Hello")

    assert len(chat.calls) == 1


def test_retry_policy_only_retries_transport_timeout_and_upstream_errors() -> None:
    assert is_retryable_gateway_error(GatewayConnectionError("connection"))
    assert is_retryable_gateway_error(GatewayTimeoutError("timeout"))
    assert is_retryable_gateway_error(GatewayUpstreamError("upstream", retryable=True))


async def _noop() -> None:
    return None
