class LLMGatewayError(Exception):
    """Base class for errors raised by the LLM gateway client."""


class TaskRoutingError(LLMGatewayError):
    """The task router could not produce a usable route."""


class GatewayConnectionError(LLMGatewayError):
    """The application could not connect to Agent Router."""


class GatewayTimeoutError(LLMGatewayError):
    """Agent Router did not respond before the configured timeout."""


class GatewayUpstreamError(LLMGatewayError):
    """Agent Router or its upstream provider returned an error."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class InvalidGatewayResponseError(LLMGatewayError):
    """Agent Router returned an unusable response payload."""
