from .models import RouteDecision


class DummyTaskRouter:
    """交換可能なTask Routerの最小実装。HTTP通信は担当しない。

    将来は Classifier / LLM / Jev ベースの実装へ差し替える想定。
    Jevは文章を生成せず判断データのみを返すモデルで、ルーティング判定に向く。
    """

    def __init__(self, default_model: str) -> None:
        if not default_model.strip():
            raise ValueError("default_model must not be empty")
        self._default_model = default_model

    async def route(
        self,
        *,
        requested_model: str,
        prompt: str,
    ) -> RouteDecision:
        del prompt
        requested_model = requested_model.strip()
        if not requested_model:
            raise ValueError("requested_model must not be empty")

        if requested_model.lower() == "auto":
            return RouteDecision(
                model=self._default_model,
                provider="local",
                reason="dummy_default_route",
            )

        return RouteDecision(
            model=requested_model,
            provider="local",
            reason="explicit_model",
        )
