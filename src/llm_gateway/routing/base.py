from typing import Protocol

from .models import RouteDecision


class TaskRouter(Protocol):
    """モデル解決の差し替え点。Dummy / Classifier / LLM / Jev 等を想定。"""

    async def route(
        self,
        *,
        requested_model: str,
        prompt: str,
    ) -> RouteDecision:
        """Resolve an application model request without performing HTTP."""
