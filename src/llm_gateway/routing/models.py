from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteDecision:
    model: str
    provider: str
    reason: str

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("RouteDecision.model must not be empty")
        if not self.provider.strip():
            raise ValueError("RouteDecision.provider must not be empty")
        if not self.reason.strip():
            raise ValueError("RouteDecision.reason must not be empty")
