"""Base engine class for all similarity detection engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EngineResult:
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class BaseEngine(ABC):
    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    @abstractmethod
    def compare(
        self, code_a: str, code_b: str, language: str = "auto", **kwargs
    ) -> EngineResult:
        pass

    def get_name(self) -> str:
        return self.name

    def get_weight(self) -> float:
        return self.weight

    def set_weight(self, weight: float) -> None:
        self.weight = max(0.0, min(1.0, weight))

    def supports_language(self, language: str) -> bool:
        return True

    def get_config(self) -> dict[str, Any]:
        return {"name": self.name, "weight": self.weight}
