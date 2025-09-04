from dataclasses import dataclass
from typing import Protocol, Any


class LLMProvider(Protocol):
    def generate(self, prompt: str, **kwargs: Any) -> str:  # pragma: no cover - interface
        ...


@dataclass
class ProviderConfig:
    model: str
    max_tokens: int = 1024
    temperature: float = 0.2

