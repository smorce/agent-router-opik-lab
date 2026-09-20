from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_MODEL = "qwen3.8-27b-exl3-3.5bpw-wm"


def normalize_openai_base_url(value: str) -> str:
    """Return an OpenAI-compatible base URL with exactly one trailing /v1."""
    normalized = value.strip().rstrip("/")
    if not normalized:
        raise ValueError("OpenAI base URL must not be empty")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def _parse_bool(value: str, name: str, default: bool) -> bool:
    if not value:
        return default
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{name} must be either 'true' or 'false'")


def _parse_float(value: str, name: str, default: float | None) -> float | None:
    if not value.strip():
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _parse_int(value: str, name: str, default: int) -> int:
    if not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _parse_optional_int(value: str, name: str, default: int | None) -> int | None:
    if not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class LLMGatewayEnvConfig:
    agent_router_base_url: str = "http://127.0.0.1:1975"
    agent_router_api_key: str = field(default="unused", repr=False)
    task_router_mode: str = "dummy"
    task_router_default_model: str = DEFAULT_MODEL
    llama_server_base_url: str = "http://127.0.0.1:2067"
    llama_server_api_key: str = field(default="sk-local-no-key-required", repr=False)
    model: str = DEFAULT_MODEL
    default_request_model: str = "Auto"
    api_style: str = "chat_completions"
    thinking: bool = False
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    max_tokens: int = 1000
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_base_seconds: float = 0.8
    retry_max_seconds: float = 8.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> LLMGatewayEnvConfig:
        env = os.environ if environ is None else environ
        model = env.get("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        task_router_default_model = (
            env.get("TASK_ROUTER_DEFAULT_MODEL", model).strip() or model
        )
        api_style = env.get("LLM_API_STYLE", "chat_completions").strip().lower()
        if api_style not in {"chat_completions", "responses"}:
            raise ValueError("LLM_API_STYLE must be 'chat_completions' or 'responses'")

        timeout_seconds = _parse_float(
            env.get("LLAMA_SERVER_TIMEOUT_SECONDS", "15"),
            "LLAMA_SERVER_TIMEOUT_SECONDS",
            15.0,
        )
        retry_base_seconds = _parse_float(
            env.get("LLAMA_SERVER_RETRY_BASE_SECONDS", "0.8"),
            "LLAMA_SERVER_RETRY_BASE_SECONDS",
            0.8,
        )
        retry_max_seconds = _parse_float(
            env.get("LLAMA_SERVER_RETRY_MAX_SECONDS", "8.0"),
            "LLAMA_SERVER_RETRY_MAX_SECONDS",
            8.0,
        )
        if timeout_seconds is None or timeout_seconds <= 0:
            raise ValueError("LLAMA_SERVER_TIMEOUT_SECONDS must be greater than zero")
        if retry_base_seconds is None or retry_base_seconds < 0:
            raise ValueError("LLAMA_SERVER_RETRY_BASE_SECONDS must not be negative")
        if retry_max_seconds is None or retry_max_seconds < 0:
            raise ValueError("LLAMA_SERVER_RETRY_MAX_SECONDS must not be negative")

        max_retries = _parse_int(
            env.get("LLAMA_SERVER_MAX_RETRIES", "3"),
            "LLAMA_SERVER_MAX_RETRIES",
            3,
        )
        if max_retries < 0:
            raise ValueError("LLAMA_SERVER_MAX_RETRIES must not be negative")

        return cls(
            agent_router_base_url=env.get(
                "AGENT_ROUTER_BASE_URL", "http://127.0.0.1:1975"
            ).strip(),
            agent_router_api_key=env.get("AGENT_ROUTER_API_KEY", "unused"),
            task_router_mode=env.get("TASK_ROUTER_MODE", "dummy").strip().lower(),
            task_router_default_model=task_router_default_model,
            llama_server_base_url=env.get(
                "LLAMA_SERVER_BASE_URL", "http://127.0.0.1:2067"
            ).strip(),
            llama_server_api_key=env.get(
                "LLAMA_SERVER_API_KEY", "sk-local-no-key-required"
            ),
            model=model,
            default_request_model=env.get(
                "LLM_DEFAULT_REQUEST_MODEL", "Auto"
            ).strip()
            or "Auto",
            api_style=api_style,
            thinking=_parse_bool(
                env.get("LLAMA_SERVER_ENABLE_THINKING", "false"),
                "LLAMA_SERVER_ENABLE_THINKING",
                False,
            ),
            temperature=_parse_float(
                env.get("LLAMA_SERVER_TEMPERATURE", ""),
                "LLAMA_SERVER_TEMPERATURE",
                None,
            ),
            top_p=_parse_float(
                env.get("LLAMA_SERVER_TOP_P", ""),
                "LLAMA_SERVER_TOP_P",
                None,
            ),
            top_k=_parse_optional_int(
                env.get("LLAMA_SERVER_TOP_K", ""),
                "LLAMA_SERVER_TOP_K",
                None,
            ),
            min_p=_parse_float(
                env.get("LLAMA_SERVER_MIN_P", ""),
                "LLAMA_SERVER_MIN_P",
                None,
            ),
            max_tokens=_parse_int(
                env.get("LLAMA_SERVER_MAX_TOKENS", "1000"),
                "LLAMA_SERVER_MAX_TOKENS",
                1000,
            ),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )

    @property
    def agent_router_api_base_url(self) -> str:
        return normalize_openai_base_url(self.agent_router_base_url)

    @property
    def llama_server_api_base_url(self) -> str:
        return normalize_openai_base_url(self.llama_server_base_url)

    def generation_parameters(self) -> dict[str, object]:
        if self.thinking:
            temperature = 1.0
            top_p = 0.95
        else:
            temperature = 0.7
            top_p = 0.8

        return {
            "temperature": self.temperature if self.temperature is not None else temperature,
            "top_p": self.top_p if self.top_p is not None else top_p,
            "top_k": self.top_k if self.top_k is not None else 20,
            "min_p": self.min_p if self.min_p is not None else 0.0,
            "max_tokens": self.max_tokens,
            "chat_template_kwargs": {"enable_thinking": self.thinking},
        }
