from __future__ import annotations

import pytest

from llm_gateway import LlamaServerEnvConfig as ExportedLlamaServerEnvConfig
from llm_gateway.client import call_llama_server
from llm_gateway.config import LLMGatewayEnvConfig, LlamaServerEnvConfig


def make_config(**overrides: str) -> LLMGatewayEnvConfig:
    values = {
        "AGENT_ROUTER_BASE_URL": "http://router:1975",
        "AGENT_ROUTER_API_KEY": "unused",
        "LLAMA_SERVER_ENABLE_THINKING": "false",
        "LLAMA_SERVER_MAX_RETRIES": "0",
    }
    values.update(overrides)
    return LLMGatewayEnvConfig.from_env(values)


class ForbiddenLegacyClient:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"legacy OpenAI client must not be used: {name}")


class FakeGatewayClient:
    def __init__(self, config: LLMGatewayEnvConfig, **kwargs: object) -> None:
        self.config = config
        self.kwargs = kwargs
        self.closed = False

    async def complete(self, prompt: str, *, model: str | None = None) -> str:
        return (
            f"prompt={prompt};model={model};"
            f"thinking={self.config.thinking};temperature={self.config.temperature}"
        )

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> FakeGatewayClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()


def test_llama_server_env_config_is_not_a_plain_alias() -> None:
    assert LlamaServerEnvConfig is not LLMGatewayEnvConfig
    assert ExportedLlamaServerEnvConfig is LlamaServerEnvConfig
    config = LlamaServerEnvConfig.from_env({"LLAMA_SERVER_ENABLE_THINKING": "true"})
    assert isinstance(config, LlamaServerEnvConfig)
    assert not isinstance(config, LLMGatewayEnvConfig)
    assert config.thinking is True


@pytest.mark.asyncio
async def test_legacy_llama_server_env_config_complete_uses_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[FakeGatewayClient] = []

    def factory(config: LLMGatewayEnvConfig, **kwargs: object) -> FakeGatewayClient:
        client = FakeGatewayClient(config, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr("llm_gateway.client.LLMGatewayClient", factory)

    cfg = LlamaServerEnvConfig.from_env(
        {
            "AGENT_ROUTER_BASE_URL": "http://router:1975",
            "LLM_DEFAULT_REQUEST_MODEL": "Auto",
        }
    )
    text = await cfg.complete("Hello")

    assert text == "prompt=Hello;model=Auto;thinking=False;temperature=None"
    assert created[0].closed is True


@pytest.mark.asyncio
async def test_call_llama_server_new_signature_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("llm_gateway.client.LLMGatewayClient", FakeGatewayClient)
    config = make_config()

    result = await call_llama_server("Hello", model="Auto", config=config)

    assert result == "prompt=Hello;model=Auto;thinking=False;temperature=None"


@pytest.mark.asyncio
async def test_call_llama_server_accepts_legacy_client_model_prompt_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("llm_gateway.client.LLMGatewayClient", FakeGatewayClient)

    result = await call_llama_server(
        ForbiddenLegacyClient(),
        "qwen3.8-27b-exl3-3.5bpw-wm",
        "Hello",
        enable_thinking=True,
        temperature=0.5,
        config=make_config(),
    )

    assert result == (
        "prompt=Hello;model=qwen3.8-27b-exl3-3.5bpw-wm;thinking=True;temperature=0.5"
    )


@pytest.mark.asyncio
async def test_call_llama_server_legacy_keyword_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("llm_gateway.client.LLMGatewayClient", FakeGatewayClient)

    result = await call_llama_server(
        ForbiddenLegacyClient(),
        model="legacy-model",
        prompt="Hi",
        enable_thinking=False,
        top_k=7,
        min_p=0.1,
        config=make_config(),
    )

    assert result.startswith("prompt=Hi;model=legacy-model;thinking=False")


@pytest.mark.asyncio
async def test_call_llama_server_accepts_legacy_timeout_and_retry_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[FakeGatewayClient] = []

    def factory(config: LLMGatewayEnvConfig, **kwargs: object) -> FakeGatewayClient:
        client = FakeGatewayClient(config, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr("llm_gateway.client.LLMGatewayClient", factory)

    result = await call_llama_server(
        ForbiddenLegacyClient(),
        "model",
        "Hello",
        timeout_seconds=30,
        max_retries=7,
        retry_base_delay_seconds=1.0,
        retry_max_delay_seconds=10.0,
        config=make_config(),
    )

    assert result.startswith("prompt=Hello;model=model;")
    assert created[0].config.timeout_seconds == 30.0
    assert created[0].config.max_retries == 7
    assert created[0].config.retry_base_seconds == 1.0
    assert created[0].config.retry_max_seconds == 10.0
