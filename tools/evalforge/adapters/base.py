"""Base tool adapter."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Tuple


class ToolAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def predict(self, pairs: List[Tuple[str, str]]) -> List[float]:
        pass
