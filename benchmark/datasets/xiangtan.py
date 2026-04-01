"""
Xiangtan University Dataset Loader.

A Java code clone detection dataset from Xiangtan University research.
Includes hand-labeled pairs with multiple clone types.

Reference: "Detecting Code Clones with Graph Neural Network and Flow-Augmented AST"
"""
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
import csv
from dataclasses import dataclass, field


@dataclass
class XTClonePair:
    """A clone pair from Xiangtan dataset."""
    id: str
    file1: str
    file2: str
    clone_type: str  # T1, T2, T3
    source1: str = ""
    source2: str = ""
    label: int = 1

    @property
    def normalized_type(self) -> int:
        type_map = {"T1": 1, "T2": 2, "T3": 3}
        return type_map.get(self.clone_type, 0)


class XiangtanDataset:
    """
    Loads and processes Xiangtan University code clone dataset.

    Dataset structure (expected):
        xiangtan/
        +-- source/       # Original Java files
        |   +-- T1/       # Type-1 clones (identical)
        |   +-- T2/       # Type-2 clones (renamed)
        |   +-- T3/       # Type-3 clones (restructured)
        +-- pairs.csv     # Clone pair definitions
        +-- ground_truth.json  # Labeled pairs
    """

    def __init__(self, data_dir: Path = Path("benchmark/data/xiangtan")):
        self.data_dir = data_dir
        self.source_dir = data_dir / "source"
        self.pairs_file = data_dir / "pairs.csv"
        self._pairs: List[XTClonePair] = []
        self._source_cache: Dict[str, str] = {}

    def load(self, clone_types: Optional[List[str]] = None,
             max_pairs: Optional[int] = None,
             load_sources: bool = True) -> List[XTClonePair]:
        """
        Load clone pairs from the dataset.

        Args:
            clone_types: Filter to specific clone types (T1, T2, T3)
            max_pairs: Maximum number of pairs to load
            load_sources: Whether to load source code for each pair

        Returns:
            List of XTClonePair objects
        """
        if self.pairs_file.exists():
            self._pairs = self._load_from_csv(clone_types, max_pairs)
        else:
            self._pairs = self._load_from_directory(clone_types, max_pairs)

        # Load source codes if requested
        if load_sources:
            for pair in self._pairs:
                if not pair.source1:
                    pair.source1 = self.get_source(pair.file1) or ""
                if not pair.source2:
                    pair.source2 = self.get_source(pair.file2) or ""

        return self._pairs

    def _load_from_csv(self, clone_types: Optional[List[str]] = None,
                       max_pairs: Optional[int] = None) -> List[XTClonePair]:
        """Load pairs from CSV file."""
        pairs = []
        with open(self.pairs_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_pairs and i >= max_pairs:
                    break

                ct = row.get('clone_type', 'T1').strip()
                if clone_types and ct not in clone_types:
                    continue

                pairs.append(XTClonePair(
                    id=row.get('id', str(i)),
                    file1=row.get('file1', '').strip(),
                    file2=row.get('file2', '').strip(),
                    clone_type=ct,
                    source1=row.get('source1', ''),
                    source2=row.get('source2', ''),
                ))

        return pairs

    def _load_from_directory(self, clone_types: Optional[List[str]] = None,
                             max_pairs: Optional[int] = None) -> List[XTClonePair]:
        """Load pairs by scanning source directories."""
        pairs = []
        type_dirs = []

        if clone_types:
            type_dirs = clone_types
        else:
            type_dirs = ['T1', 'T2', 'T3']

        pair_id = 0
        for type_dir in type_dirs:
            dir_path = self.source_dir / type_dir
            if not dir_path.exists():
                continue

            for code_file in dir_path.rglob("*.java"):
                if max_pairs and len(pairs) >= max_pairs:
                    break
                
                # Find matching pair files (e.g., A.java, A_clone.java)
                stem = code_file.stem
                clone_file = code_file.parent / f"{stem}_clone.java"
                
                if clone_file.exists():
                    pairs.append(XTClonePair(
                        id=str(pair_id),
                        file1=str(code_file.relative_to(self.source_dir)),
                        file2=str(clone_file.relative_to(self.source_dir)),
                        clone_type=type_dir,
                        source1=code_file.read_text(encoding='utf-8', errors='ignore'),
                        source2=clone_file.read_text(encoding='utf-8', errors='ignore'),
                    ))
                    pair_id += 1

        return pairs

    def get_source(self, file_path: str) -> Optional[str]:
        """Load source code for a file."""
        if file_path in self._source_cache:
            return self._source_cache[file_path]

        # Try relative to source_dir
        full_path = self.source_dir / file_path
        if not full_path.exists():
            # Try as absolute path
            full_path = Path(file_path)
            if not full_path.exists():
                return None

        try:
            code = full_path.read_text(encoding='utf-8', errors='ignore')
            self._source_cache[file_path] = code
            return code
        except Exception:
            return None

    def load_ground_truth_json(self) -> List[Dict[str, Any]]:
        """Load ground truth from JSON file if available."""
        gt_file = self.data_dir / "ground_truth.json"
        if not gt_file.exists():
            return []

        with open(gt_file, 'r') as f:
            return json.load(f).get("pairs", [])

    def to_ground_truth_format(self) -> Dict[str, Any]:
        """Convert loaded pairs to ground truth format."""
        pairs = []
        for p in self._pairs:
            pairs.append({
                "file1": p.file1,
                "file2": p.file2,
                "label": p.label,
                "clone_type": p.clone_type,
            })
        return {"pairs": pairs}

    def save_ground_truth(self, output_path: Path) -> None:
        """Save current pairs in ground truth format."""
        data = self.to_ground_truth_format()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        type_counts = {}
        for p in self._pairs:
            type_counts[p.clone_type] = type_counts.get(p.clone_type, 0) + 1

        return {
            "name": "Xiangtan University",
            "language": "Java",
            "source_dir": str(self.source_dir),
            "total_pairs": len(self._pairs),
            "clone_type_counts": type_counts,
        }

    def check_availability(self) -> Dict[str, bool]:
        """Check which parts of the dataset are available."""
        return {
            "data_dir": self.data_dir.exists(),
            "source_dir": self.source_dir.exists(),
            "pairs_csv": self.pairs_file.exists(),
        }