"""
Base Parser - Abstract interface for tool output normalization.

All parsers must output the same semantic model (StandardOutput).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class StandardOutput:
    """
    Unified semantic model for ALL tool outputs.
    
    Standard JSON format:
    {
        "tool": "jplag",
        "dataset": "bigclonebench",
        "pairs": [
            {
                "file1": "student1/A.java",
                "file2": "student2/A.java",
                "similarity": 0.87,
                "matches": [{"start1": 10, "end1": 30, "start2": 12, "end2": 32}]
            }
        ]
    }
    """
    tool: str
    dataset: str = ""
    pairs: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "dataset": self.dataset, "pairs": self.pairs}


class BaseToolParser(ABC):
    """Abstract base class for tool output normalization."""
    
    def __init__(self, dataset: str = ""):
        self.dataset = dataset
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        pass
    
    @abstractmethod
    def parse(self, input_path: Path) -> StandardOutput:
        pass
    
    def normalize_path(self, path: str) -> str:
        """Normalize file path to relative format."""
        if not path:
            return ""
        path = path.replace("\\", "/")
        for prefix in ["/home/", "/tmp/", "/var/", "/opt/", "/usr/"]:
            if path.startswith(prefix):
                parts = path.split("/")
                for i, part in enumerate(parts):
                    if part and i > 1:
                        return "/".join(parts[i:])
        path = path.lstrip("./ ")
        while "//" in path:
            path = path.replace("//", "/")
        return path.strip()
    
    def canonicalize_pair(self, file1: str, file2: str) -> tuple:
        """Canonicalize pair to sorted tuple (A,B) where A <= B."""
        return tuple(sorted([self.normalize_path(file1), self.normalize_path(file2)]))
    
    def normalize_similarity(self, raw_sim: float, tool_max: float = 100.0) -> float:
        """Normalize similarity to 0.0-1.0 range."""
        if raw_sim <= 0 or tool_max <= 0:
            return min(1.0, max(0.0, raw_sim))
        return min(1.0, max(0.0, raw_sim / tool_max))
    
    def make_pair(self, file1: str, file2: str, similarity: float) -> Dict[str, Any]:
        """Create normalized pair dict."""
        f1, f2 = self.canonicalize_pair(file1, file2)
        return {"file1": f1, "file2": f2, "similarity": round(similarity, 4), "matches": []}
    
    def deduplicate_pairs(self, pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate pairs, keep highest similarity per pair."""
        seen = {}
        for p in pairs:
            key = tuple(sorted([p.get("file1", ""), p.get("file2", "")]))
            sim = p.get("similarity", 0)
            if key not in seen or sim > seen[key].get("similarity", 0):
                seen[key] = p
        return list(seen.values())
    
    def filter_pairs(self, pairs: List[Dict[str, Any]], min_sim: float = 0.0) -> List[Dict[str, Any]]:
        """Filter pairs by min similarity."""
        return [p for p in pairs if p.get("similarity", 0) >= min_sim]


class ParserError(Exception):
    """Error during tool output parsing."""
    pass
