import pytest

from llm_gateway.config import LLMGatewayEnvConfig, normalize_openai_base_url


def test_normalize_openai_base_url_adds_v1_once() -> None:
    assert normalize_openai_base_url("http://127.0.0.1:1975") == "http://127.0.0.1:1975/v1"
    assert normalize_openai_base_url("http://127.0.0.1:1975/") == "http://127.0.0.1:1975/v1"
    assert normalize_openai_base_url("http://127.0.0.1:1975/v1") == "http://127.0.0.1:1975/v1"
    assert normalize_openai_base_url("http://127.0.0.1:1975/v1/") == "http://127.0.0.1:1975/v1"


def test_environment_variables_are_parsed_without_secrets_in_repr() -> None:
    config = LLMGatewayEnvConfig.from_env(
        {
            "AGENT_ROUTER_BASE_URL": "http://router:1975",
            "AGENT_ROUTER_API_KEY": "local-secret",
            "TASK_ROUTER_DEFAULT_MODEL": "local-model",
            "LLAMA_SERVER_BASE_URL": "http://llama:2067/v1",
            "LLAMA_SERVER_API_KEY": "another-secret",
            "LLAMA_SERVER_ENABLE_THINKING": "true",
            "LLAMA_SERVER_TEMPERATURE": "0.4",
            "LLAMA_SERVER_TOP_P": "",
            "LLAMA_SERVER_TOP_K": "12",
            "LLAMA_SERVER_MIN_P": "0.1",
            "LLAMA_SERVER_MAX_TOKENS": "256",
            "LLAMA_SERVER_TIMEOUT_SECONDS": "7.5",
            "LLAMA_SERVER_MAX_RETRIES": "2",
            "LLAMA_SERVER_RETRY_BASE_SECONDS": "0.2",
            "LLAMA_SERVER_RETRY_MAX_SECONDS": "2.0",
        }
    )

    assert config.agent_router_api_base_url == "http://router:1975/v1"
    assert config.llama_server_api_base_url == "http://llama:2067/v1"
    assert config.default_request_model == "Auto"
    assert config.thinking is True
    assert config.generation_parameters() == {
        "temperature": 0.4,
        "top_p": 0.95,
        "top_k": 12,
        "min_p": 0.1,
        "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    rendered = repr(config)
    assert "local-secret" not in rendered
    assert "another-secret" not in rendered


def test_thinking_false_uses_existing_defaults() -> None:
    config = LLMGatewayEnvConfig.from_env({"LLAMA_SERVER_ENABLE_THINKING": "false"})

    assert config.generation_parameters() == {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0.0,
        "max_tokens": 1000,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def test_explicit_zero_top_k_is_preserved() -> None:
    config = LLMGatewayEnvConfig.from_env(
        {
            "LLAMA_SERVER_TOP_K": "0",
        }
    )

    assert config.generation_parameters()["top_k"] == 0


@pytest.mark.parametrize("value", ["maybe", "yes please", "2"])
def test_invalid_boolean_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="LLAMA_SERVER_ENABLE_THINKING"):
        LLMGatewayEnvConfig.from_env({"LLAMA_SERVER_ENABLE_THINKING": value})


def test_invalid_api_style_is_rejected() -> None:
    with pytest.raises(ValueError, match="LLM_API_STYLE"):
        LLMGatewayEnvConfig.from_env({"LLM_API_STYLE": "legacy"})
