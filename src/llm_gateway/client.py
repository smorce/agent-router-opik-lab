from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import uuid4

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from .config import LLMGatewayEnvConfig
from .errors import (
    GatewayConnectionError,
    GatewayTimeoutError,
    GatewayUpstreamError,
    InvalidGatewayResponseError,
    LLMGatewayError,
    TaskRoutingError,
)
from .routing import DummyTaskRouter, TaskRouter
from .routing.models import RouteDecision

Logger = logging.Logger
Sleeper = Callable[[float], Awaitable[None]]


def is_retryable_gateway_error(error: Exception) -> bool:
    if isinstance(error, (GatewayConnectionError, GatewayTimeoutError)):
        return True
    return isinstance(error, GatewayUpstreamError) and error.retryable


def translate_gateway_exception(error: Exception) -> LLMGatewayError | None:
    if isinstance(error, LLMGatewayError):
        return error
    if isinstance(error, (APITimeoutError, asyncio.TimeoutError, TimeoutError)):
        return GatewayTimeoutError("Agent Router request timed out")
    if isinstance(error, (APIConnectionError, ConnectionError)):
        return GatewayConnectionError("Could not connect to Agent Router")
    if isinstance(error, APIStatusError):
        status_code = getattr(error, "status_code", None)
        return GatewayUpstreamError(
            f"Agent Router returned an upstream error (status={status_code})",
            retryable=isinstance(status_code, int) and 500 <= status_code < 600,
        )
    if isinstance(error, APIError):
        return GatewayUpstreamError("Agent Router returned an API error")
    return None


class LLMGatewayClient:
    """Application-facing client that routes requests through Agent Router."""

    def __init__(
        self,
        config: LLMGatewayEnvConfig,
        *,
        task_router: TaskRouter | None = None,
        openai_client: Any | None = None,
        sleeper: Sleeper = asyncio.sleep,
        logger: Logger | None = None,
    ) -> None:
        self.config = config
        if task_router is None:
            if config.task_router_mode != "dummy":
                raise ValueError(
                    f"Unsupported TASK_ROUTER_MODE: {config.task_router_mode}"
                )
            task_router = DummyTaskRouter(config.task_router_default_model)
        self.task_router = task_router
        self._client = openai_client or AsyncOpenAI(
            base_url=config.agent_router_api_base_url,
            api_key=config.agent_router_api_key,
            timeout=config.timeout_seconds,
            max_retries=0,
        )
        self._sleeper = sleeper
        self._logger = logger or logging.getLogger(__name__)

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> LLMGatewayClient:
        return cls(LLMGatewayEnvConfig.from_env(environ), **kwargs)

    async def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        request_id = request_id or uuid4().hex
        requested_model = model if model is not None else self.config.default_request_model
        try:
            decision = await self.task_router.route(
                requested_model=requested_model,
                prompt=prompt,
            )
        except Exception as exc:
            if isinstance(exc, TaskRoutingError):
                raise
            raise TaskRoutingError("Task Router failed to produce a route") from exc

        headers = {"X-Request-ID": request_id}
        if session_id:
            headers["X-Session-ID"] = session_id

        started_at = time.monotonic()
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await self._complete_once(
                    decision,
                    prompt,
                    headers,
                )
                text = self._extract_text(response)
            except Exception as exc:
                translated = translate_gateway_exception(exc)
                if translated is None:
                    raise
                if is_retryable_gateway_error(translated) and attempt < self.config.max_retries:
                    delay = min(
                        self.config.retry_base_seconds * (2**attempt),
                        self.config.retry_max_seconds,
                    )
                    self._logger.warning(
                        "llm_request_retry request_id=%s requested_model=%s "
                        "resolved_model=%s router_type=%s route_reason=%s "
                        "gateway_endpoint=%s retry_count=%s error_type=%s",
                        request_id,
                        requested_model,
                        decision.model,
                        type(self.task_router).__name__,
                        decision.reason,
                        self.config.agent_router_api_base_url,
                        attempt + 1,
                        type(translated).__name__,
                    )
                    await self._sleeper(delay)
                    continue

                self._logger.error(
                    "llm_request_failed request_id=%s requested_model=%s "
                    "resolved_model=%s router_type=%s route_reason=%s "
                    "gateway_endpoint=%s elapsed_ms=%s retry_count=%s error_type=%s",
                    request_id,
                    requested_model,
                    decision.model,
                    type(self.task_router).__name__,
                    decision.reason,
                    self.config.agent_router_api_base_url,
                    round((time.monotonic() - started_at) * 1000),
                    attempt,
                    type(translated).__name__,
                )
                raise translated from exc

            self._logger.info(
                "llm_request_completed request_id=%s requested_model=%s "
                "resolved_model=%s router_type=%s route_reason=%s "
                "gateway_endpoint=%s elapsed_ms=%s retry_count=%s error_type=none",
                request_id,
                requested_model,
                decision.model,
                type(self.task_router).__name__,
                decision.reason,
                self.config.agent_router_api_base_url,
                round((time.monotonic() - started_at) * 1000),
                attempt,
            )
            return text

        raise AssertionError("Retry loop ended without a result or exception")

    async def _complete_once(
        self,
        decision: RouteDecision,
        prompt: str,
        headers: dict[str, str],
    ) -> Any:
        generation = self.config.generation_parameters()
        extra_body = {
            "top_k": generation["top_k"],
            "min_p": generation["min_p"],
            "chat_template_kwargs": generation["chat_template_kwargs"],
        }

        if self.config.api_style == "responses":
            return await self._client.responses.create(
                model=decision.model,
                input=prompt,
                temperature=generation["temperature"],
                top_p=generation["top_p"],
                max_output_tokens=generation["max_tokens"],
                extra_body=extra_body,
                extra_headers=headers,
            )

        return await self._client.chat.completions.create(
            model=decision.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=generation["temperature"],
            top_p=generation["top_p"],
            max_tokens=generation["max_tokens"],
            extra_body=extra_body,
            extra_headers=headers,
        )

    @staticmethod
    def _extract_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str):
            return output_text

        choices = getattr(response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content

        raise InvalidGatewayResponseError(
            "Agent Router response did not contain textual output"
        )

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()

    async def __aenter__(self) -> LLMGatewayClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.close()


async def call_llama_server(
    prompt: str,
    *,
    model: str = "Auto",
    config: LLMGatewayEnvConfig | None = None,
) -> str:
    """Compatibility wrapper retaining the historical function name."""
    client = LLMGatewayClient(config or LLMGatewayEnvConfig.from_env())
    try:
        return await client.complete(prompt, model=model)
    finally:
        await client.close()
