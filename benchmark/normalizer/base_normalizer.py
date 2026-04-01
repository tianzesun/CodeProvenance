"""Base Normalizer interface."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from pathlib import Path

class BaseNormalizer(ABC):
    @property
    @abstractmethod
    def tool_name(self) -> str:
        pass
    @abstractmethod
    def normalize(self, output_path: Path) -> List[Dict[str, Any]]:
        pass
    @staticmethod
    def canonicalize_pair(f1: str, f2: str) -> Tuple[str, str]:
        return tuple(sorted([f1.strip(), f2.strip()]))
    @staticmethod
    def deduplicate_pairs(predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = {}
        for p in predictions:
            f1, f2 = p.get("file1",""), p.get("file2","")
            if f1 and f2:
                key = BaseNormalizer.canonicalize_pair(f1, f2)
                sim = p.get("similarity", 0)
                if key not in seen or sim > seen[key].get("similarity", 0):
                    seen[key] = p
        return list(seen.values())
