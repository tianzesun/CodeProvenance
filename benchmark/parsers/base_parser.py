"""Base parser for tool output normalization."""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Standard output format contract for ALL tools."""
    pairs: List[Dict[str, Any]]

    @staticmethod
    def make_pair(file1: str, file2: str, similarity: float) -> Dict[str, Any]:
        return {
            "file1": file1,
            "file2": file2,
            "similarity": similarity,
            "matches": [],
        }

    @staticmethod
    def add_match(pair: Dict[str, Any], start1: int, end1: int, start2: int, end2: int) -> Dict[str, Any]:
        pair["matches"].append({
            "start1": start1, "end1": end1,
            "start2": start2, "end2": end2,
        })
        return pair


class BaseToolParser(ABC):
    """Base class for tool output normalization."""
    @property
    @abstractmethod
    def tool_name(self) -> str:
        pass

    @abstractmethod
    def parse(self, output_path: Path) -> ToolResult:
        pass

    @staticmethod
    def to_dict(result: ToolResult) -> Dict[str, Any]:
        return {"pairs": result.pairs}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ToolResult:
        return ToolResult(pairs=data.get("pairs", []))
