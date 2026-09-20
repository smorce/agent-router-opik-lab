from typing import Protocol

from .models import RouteDecision


class TaskRouter(Protocol):
    async def route(
        self,
        *,
        requested_model: str,
        prompt: str,
    ) -> RouteDecision:
        """Resolve an application model request without performing HTTP."""
