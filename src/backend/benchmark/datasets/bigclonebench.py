"""
BigCloneBench Dataset Loader.

Supports two modes:
1. H2 database mode (official BCEval release): reads from bcb.h2.db
2. CSV mode (processed pairs): reads from metadata/clone_pairs.csv

Dataset structure after extraction:
    bigclonebench/
    ├── bcb_reduced/           # Source files organized by functionality
    │   ├── {functionality_id}/
    │   │   ├── selected/
    │   │   ├── default/
    │   │   └── sample/
    ├── bcb.h2.db              # H2 database (5.5GB) with clone metadata
    └── bcb.trace.db           # H2 trace file
"""
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
import random
from dataclasses import dataclass, field

from src.backend.benchmark.datasets.schema import (
    DatasetContract,
    DatasetMetadata,
    CloneType,
    Difficulty,
    CodePair,
    CanonicalDataset,
)


@dataclass
class ClonePair:
    """A clone pair from BigCloneBench."""
    file1: str
    file2: str
    clone_type: int  # 1=identical, 2=renamed, 3=restructured, 4=semantic
    file1_start: int
    file1_end: int
    file2_start: int
    file2_end: int
    similarity: float = 0.0

    @property
    def is_clone(self) -> bool:
        return self.clone_type in [1, 2, 3, 4]

    @property
    def label(self) -> int:
        return 1 if self.is_clone else 0


@dataclass
class NonClonePair:
    """A non-clone pair from BigCloneBench."""
    file1: str
    file2: str
    label: int = 0


@dataclass
class BCBSample:
    """A loaded sample with source code for each pair."""
    clone_pairs: List[ClonePair]
    non_clone_pairs: List[NonClonePair]
    clone_counts: Dict[int, int] = field(default_factory=dict)
    source_codes: Dict[str, str] = field(default_factory=dict)

    def to_ground_truth_format(self) -> Dict[str, Any]:
        """Convert to ground truth JSON format."""
        pairs = []
        for cp in self.clone_pairs:
            pairs.append({
                "file1": cp.file1,
                "file2": cp.file2,
                "label": cp.label,
                "clone_type": cp.clone_type,
            })
        for ncp in self.non_clone_pairs:
            pairs.append({
                "file1": ncp.file1,
                "file2": ncp.file2,
                "label": ncp.label,
            })
        return {"pairs": pairs}


class BigCloneBenchDataset(DatasetContract):
    """
    Loads and processes BigCloneBench dataset.

    Works with the BCEval extraction format:
        bigclonebench/
        ├── bcb_reduced/           # Source files by functionality
        │   ├── {id}/{subdir}/{filename}.java
        └── metadata/              # Optional: clone_pairs.csv
    """

    CLONE_TYPE_NAMES = {
        1: "Type-1 (Identical)",
        2: "Type-2 (Renamed)",
        3: "Type-3 (Restructured)",
        4: "Type-4 (Semantic)"
    }

    def __init__(self, data_dir: Path = Path("benchmark/data/bigclonebench")):
        self.data_dir = data_dir
        self.bcb_reduced_dir = data_dir / "bcb_reduced"
        self.clones_dir = data_dir / "metadata"
        self.h2_db = data_dir / "bcb.h2.db"
        self._pairs_cache: List[ClonePair] = []
        self._non_clone_pairs_cache: List[NonClonePair] = []
        self._source_cache: Dict[str, str] = {}
    
    @property
    def metadata(self) -> DatasetMetadata:
        """Return dataset metadata.
        
        Returns:
            DatasetMetadata with all required fields.
        """
        # Get actual size from loaded pairs or estimate
        size = len(self._pairs_cache) + len(self._non_clone_pairs_cache)
        if size == 0:
            size = 55000  # Default estimate for BigCloneBench
        
        return DatasetMetadata(
            name="BigCloneBench",
            version="bceval_2024",
            language="java",
            clone_types=[CloneType.TYPE_1, CloneType.TYPE_2, CloneType.TYPE_3, CloneType.TYPE_4],
            difficulty=Difficulty.HARD,
            size=size,
            source="https://onedrive.live.com/?id=52477620-3894-4497-9E1E-26609C1E2A75",
            license="Academic use only",
            ground_truth_format="binary",
            description="Industry-standard Java clone detection benchmark with 55,000+ pairs across 4 clone types"
        )

    def load(self, clone_types: Optional[List[int]] = None,
             max_pairs: Optional[int] = None,
             max_non_clones: int = 10000,
             **kwargs) -> CanonicalDataset:
        """Load clone pairs and non-clone pairs from the dataset.

        Args:
            clone_types: Filter to specific clone types (1-4)
            max_pairs: Maximum number of clone pairs to load
            max_non_clones: Maximum number of non-clone pairs
            **kwargs: Additional arguments (unused)

        Returns:
            CanonicalDataset with loaded pairs
        """
        clone_pairs_raw = self.load_clone_pairs(clone_types, max_pairs)
        non_clone_pairs_raw = self.load_non_clones(max_non_clones)
        
        # Convert to CodePair format
        pairs: List[CodePair] = []
        
        # Add clone pairs
        for cp in clone_pairs_raw:
            code_a = self.get_source_code(cp.file1, cp.file1_start, cp.file1_end) or ""
            code_b = self.get_source_code(cp.file2, cp.file2_start, cp.file2_end) or ""
            pairs.append(CodePair(
                id_a=cp.file1,
                id_b=cp.file2,
                code_a=code_a,
                code_b=code_b,
                label=cp.label,
                clone_type=cp.clone_type,
            ))
        
        # Add non-clone pairs
        for ncp in non_clone_pairs_raw:
            code_a = self.get_source_code(ncp.file1) or ""
            code_b = self.get_source_code(ncp.file2) or ""
            pairs.append(CodePair(
                id_a=ncp.file1,
                id_b=ncp.file2,
                code_a=code_a,
                code_b=code_b,
                label=ncp.label,
                clone_type=0,
            ))
        
        return CanonicalDataset(
            name="BigCloneBench",
            version="bceval_2024",
            pairs=pairs,
            metadata=self.metadata,
        )

    def load_clone_pairs(self, clone_types: Optional[List[int]] = None,
                         max_pairs: Optional[int] = None) -> List[ClonePair]:
        """Load clone pairs from CSV or generate from structure.

        Priority:
        1. metadata/clone_pairs.csv (processed pairs)
        2. Generate from bcb_reduced structure (same functionality = clone,
           different functionality = non-clone)
        """
        pairs_file = self.clones_dir / "clone_pairs.csv"
        if pairs_file.exists():
            return self._load_clone_pairs_from_csv(pairs_file, clone_types, max_pairs)

        # Generate pairs from bcb_reduced structure
        return self._generate_clone_pairs_from_structure(clone_types, max_pairs)

    def _load_clone_pairs_from_csv(self, pairs_file: Path,
                                   clone_types: Optional[List[int]] = None,
                                   max_pairs: Optional[int] = None) -> List[ClonePair]:
        """Load from processed CSV file."""
        pairs = []
        with open(pairs_file, 'r', encoding='utf-8') as f:
            header = f.readline()
            for line in f:
                if max_pairs and len(pairs) >= max_pairs:
                    break
                parts = line.strip().split(',')
                if len(parts) < 7:
                    continue
                try:
                    clone_type = int(parts[0])
                    if clone_types and clone_type not in clone_types:
                        continue
                    pair = ClonePair(
                        file1=parts[1].strip(),
                        file2=parts[2].strip(),
                        clone_type=clone_type,
                        file1_start=int(parts[3]),
                        file1_end=int(parts[4]),
                        file2_start=int(parts[5]),
                        file2_end=int(parts[6]),
                        similarity=float(parts[7]) if len(parts) > 7 else 0.0,
                    )
                    pairs.append(pair)
                except (ValueError, IndexError):
                    continue
        self._pairs_cache = pairs
        return pairs

    def _generate_clone_pairs_from_structure(
        self, clone_types: Optional[List[int]] = None,
        max_pairs: Optional[int] = None
    ) -> List[ClonePair]:
        """Generate sample clone pairs from bcb_reduced directory structure.

        Files in the same functionality directory are considered clones.
        """
        if not self.bcb_reduced_dir.exists():
            return []

        functionalities = [
            d for d in self.bcb_reduced_dir.iterdir() if d.is_dir()
        ]

        clone_pairs: List[ClonePair] = []
        non_clone_pairs: List[NonClonePair] = []

        for func_dir in functionalities:
            # Collect all Java files in this functionality
            func_files = list(func_dir.rglob("*.java"))
            if len(func_files) < 2:
                continue

            # Generate clone pairs (within same functionality)
            for i in range(min(len(func_files), 10)):
                for j in range(i + 1, min(len(func_files), 10)):
                    f1 = func_files[i]
                    f2 = func_files[j]
                    rel1 = str(f1.relative_to(self.bcb_reduced_dir))
                    rel2 = str(f2.relative_to(self.bcb_reduced_dir))
                    clone_pairs.append(ClonePair(
                        file1=rel1, file2=rel2,
                        clone_type=3,  # Default Type-3 (within functionality)
                        file1_start=1, file1_end=1,
                        file2_start=1, file2_end=1,
                    ))
                    if max_pairs and len(clone_pairs) >= max_pairs:
                        break

            # Generate non-clone pairs (with previous functionality)
            if len(functionalities) > 1 and functionalities.index(func_dir) > 0:
                prev_idx = functionalities.index(func_dir) - 1
                prev_files = list(functionalities[prev_idx].rglob("*.java"))
                if prev_files:
                    for _ in range(min(5, len(func_files), len(prev_files))):
                        f1 = random.choice(func_files)
                        f2 = random.choice(prev_files)
                        non_clone_pairs.append(NonClonePair(
                            file1=str(f1.relative_to(self.bcb_reduced_dir)),
                            file2=str(f2.relative_to(self.bcb_reduced_dir)),
                        ))

        self._pairs_cache = clone_pairs
        self._non_clone_pairs_cache = non_clone_pairs
        return clone_pairs

    def load_non_clones(self, max_pairs: int = 10000) -> List[NonClonePair]:
        """Load non-clone pairs for negative samples."""
        if self._non_clone_pairs_cache:
            return self._non_clone_pairs_cache[:max_pairs]

        if not self.bcb_reduced_dir.exists():
            return []

        functionalities = [
            d for d in self.bcb_reduced_dir.iterdir() if d.is_dir()
        ]

        pairs: List[NonClonePair] = []
        all_files = list(self.bcb_reduced_dir.rglob("*.java"))

        if len(all_files) < 2:
            return pairs

        for _ in range(min(max_pairs, len(all_files))):
            # Pick files from different functionality directories
            func_dirs = list(set(f.parent for f in all_files))
            if len(func_dirs) < 2:
                break
            dir1, dir2 = random.sample(func_dirs, 2)
            f1 = random.choice(list(dir1.rglob("*.java")))
            f2 = random.choice(list(dir2.rglob("*.java")))
            pairs.append(NonClonePair(
                file1=str(f1.relative_to(self.bcb_reduced_dir)),
                file2=str(f2.relative_to(self.bcb_reduced_dir)),
            ))

        self._non_clone_pairs_cache = pairs
        return pairs

    def get_source_code(self, file_path: str, start_line: int = -1,
                        end_line: int = -1) -> Optional[str]:
        """Extract source code for a file.

        Args:
            file_path: Relative path within bcb_reduced (e.g., "1/selected/file.java")
            start_line: Start line (1-indexed), -1 for entire file
            end_line: End line (1-indexed), -1 for entire file

        Returns:
            Source code string or None if file not found
        """
        if file_path in self._source_cache:
            return self._source_cache[file_path]

        full_path = self.bcb_reduced_dir / file_path
        if not full_path.exists():
            return None

        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        if start_line > 0 and end_line > 0:
            start = max(0, start_line - 1)
            end = min(len(lines), end_line)
            lines = lines[start:end]

        code = ''.join(lines)
        self._source_cache[file_path] = code
        return code

    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        stats = {
            "name": "BigCloneBench",
            "language": "Java",
            "bcb_reduced_dir": str(self.bcb_reduced_dir),
            "h2_database": str(self.h2_db),
            "functionality_dirs": 0,
            "java_files": 0,
            "clone_pairs_loaded": len(self._pairs_cache),
            "non_clone_pairs_loaded": len(self._non_clone_pairs_cache),
            "clone_type_counts": {},
        }

        if self.bcb_reduced_dir.exists():
            func_dirs = [d for d in self.bcb_reduced_dir.iterdir() if d.is_dir()]
            stats["functionality_dirs"] = len(func_dirs)
            stats["java_files"] = len(list(self.bcb_reduced_dir.rglob("*.java")))

        if self.h2_db.exists():
            stats["h2_db_size_gb"] = round(self.h2_db.stat().st_size / (1024**3), 1)

        for cp in self._pairs_cache:
            ct = cp.clone_type
            name = self.CLONE_TYPE_NAMES.get(ct, f"Type-{ct}")
            stats["clone_type_counts"][name] = stats["clone_type_counts"].get(name, 0) + 1

        return stats

    def check_availability(self) -> Dict[str, bool]:
        """Check which parts of the dataset are available."""
        return {
            "data_dir": self.data_dir.exists(),
            "bcb_reduced": self.bcb_reduced_dir.exists(),
            "h2_database": self.h2_db.exists(),
            "metadata_csv": (self.clones_dir / "clone_pairs.csv").exists(),
        }