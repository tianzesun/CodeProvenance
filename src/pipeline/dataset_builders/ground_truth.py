"""Ground truth standard format."""
from typing import Set, Tuple
from pathlib import Path
import json


GROUND_TRUTH_SCHEMA = {
    "pairs": [
        {
            "file1": "student1/A.java",
            "file2": "student2/B.java",
            "label": 1  # 1 = clone/plagiarism, 0 = non-clone
        }
    ]
}


class GroundTruth:
    """
    Manages ground truth data for evaluation.
    
    Standard format:
    {
        "pairs": [
            {"file1": "A.java", "file2": "B.java", "label": 1},
            {"file1": "C.java", "file2": "D.java", "label": 0}
        ]
    }
    """
    
    def __init__(self):
        self.clones: Set[Tuple[str, str]] = set()
        self.non_clones: Set[Tuple[str, str]] = set()
    
    def add_pair(self, file1: str, file2: str, label: int) -> None:
        key = self._normalize_pair(file1, file2)
        if label == 1:
            self.clones.add(key)
        else:
            self.non_clones.add(key)
    
    @staticmethod
    def _normalize_pair(f1: str, f2: str) -> Tuple[str, str]:
        return tuple(sorted([f1, f2]))
    
    @classmethod
    def from_file(cls, path: Path) -> 'GroundTruth':
        gt = cls()
        with open(path) as f:
            data = json.load(f)
        for p in data.get("pairs", []):
            gt.add_pair(p.get("file1", ""), p.get("file2", ""), p.get("label", 0))
        return gt
    
    def save(self, path: Path) -> None:
        data = {"pairs": []}
        for f1, f2 in self.clones:
            data["pairs"].append({"file1": f1, "file2": f2, "label": 1})
        for f1, f2 in self.non_clones:
            data["pairs"].append({"file1": f1, "file2": f2, "label": 0})
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def __contains__(self, pair: Tuple[str, str]) -> bool:
        return self._normalize_pair(*pair) in self.clones