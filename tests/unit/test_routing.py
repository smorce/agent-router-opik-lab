import pytest

from llm_gateway.routing.base import TaskRouter
from llm_gateway.routing.dummy import DummyTaskRouter
from llm_gateway.routing.models import RouteDecision


@pytest.mark.asyncio
async def test_dummy_router_resolves_auto_to_configured_local_model() -> None:
    router: TaskRouter = DummyTaskRouter(
        default_model="qwen3.8-27b-exl3-3.5bpw-wm"
    )

    decision = await router.route(requested_model="Auto", prompt="Hello")

    assert decision == RouteDecision(
        model="qwen3.8-27b-exl3-3.5bpw-wm",
        provider="local",
        reason="dummy_default_route",
    )


@pytest.mark.asyncio
async def test_dummy_router_preserves_explicit_model_for_future_providers() -> None:
    router = DummyTaskRouter(default_model="default-model")

    decision = await router.route(requested_model="other-model", prompt="Hello")

    assert decision == RouteDecision(
        model="other-model",
        provider="local",
        reason="explicit_model",
    )


def test_route_decision_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="model"):
        RouteDecision(model="", provider="local", reason="test")

    with pytest.raises(ValueError, match="provider"):
        RouteDecision(model="model", provider="", reason="test")
