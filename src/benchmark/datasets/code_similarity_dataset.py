"""
CodeSimilarityDataset Loader.

Loads CodeSimilarityDataset with 100 Python code snippets across 5 algorithms.
Each algorithm has multiple implementations with similarity labels.

Dataset structure:
    CodeSimilarityDataset/
    ├── full_metadata.csv
    ├── fibonacci/
    │   ├── metadata.csv
    │   ├── ReadMe.txt
    │   └── snippets/
    ├── is_palindrome/
    ├── is_prime/
    ├── max_in_list/
    └── reverse_string/
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
import csv


@dataclass
class SimilarityPair:
    """A pair of code snippets with similarity label."""
    id: str
    algorithm: str
    file1: str
    file2: str
    source1: str = ""
    source2: str = ""
    label: int = 0  # 1=plagiarized, 0=original


class CodeSimilarityDataset:
    """
    Loads CodeSimilarityDataset.
    
    Contains 100 Python snippets across 5 algorithms:
    - fibonacci
    - is_palindrome
    - is_prime
    - max_in_list
    - reverse_string
    """
    
    ALGORITHMS = [
        "fibonacci",
        "is_palindrome",
        "is_prime",
        "max_in_list",
        "reverse_string",
    ]
    
    def __init__(self, data_dir: Path = Path("benchmark/data/CodeSimilarityDataset")):
        self.data_dir = data_dir
        self._pairs: List[SimilarityPair] = []
        self._source_cache: Dict[str, str] = {}
    
    def load(
        self,
        algorithms: Optional[List[str]] = None,
        max_pairs: Optional[int] = None
    ) -> List[SimilarityPair]:
        """
        Load similarity pairs from the dataset.
        
        Args:
            algorithms: Specific algorithms to load. If None, loads all.
            max_pairs: Maximum number of pairs to load
            
        Returns:
            List of SimilarityPair objects
        """
        pairs = []
        pair_id = 0
        
        # Load from full_metadata.csv if available
        full_metadata = self.data_dir / "full_metadata.csv"
        if full_metadata.exists():
            pairs.extend(self._load_from_full_metadata(full_metadata, algorithms, max_pairs))
        
        # Also load from individual algorithm directories
        for algo in (algorithms or self.ALGORITHMS):
            algo_dir = self.data_dir / algo
            if not algo_dir.exists():
                continue
            
            metadata_file = algo_dir / "metadata.csv"
            if metadata_file.exists():
                algo_pairs = self._load_from_algorithm_metadata(
                    metadata_file, algo, max_pairs
                )
                pairs.extend(algo_pairs)
        
        # Remove duplicates based on file1+file2 combination
        seen = set()
        unique_pairs = []
        for p in pairs:
            key = (p.file1, p.file2)
            if key not in seen:
                seen.add(key)
                unique_pairs.append(p)
        
        if max_pairs:
            unique_pairs = unique_pairs[:max_pairs]
        
        self._pairs = unique_pairs
        return unique_pairs
    
    def _load_from_full_metadata(
        self,
        metadata_file: Path,
        algorithms: Optional[List[str]] = None,
        max_pairs: Optional[int] = None
    ) -> List[SimilarityPair]:
        """Load pairs from full_metadata.csv."""
        pairs = []
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_pairs and len(pairs) >= max_pairs:
                    break
                
                algo = row.get('algorithm', '').strip()
                if algorithms and algo not in algorithms:
                    continue
                
                file1 = row.get('file1', '').strip()
                file2 = row.get('file2', '').strip()
                
                # Load source code
                source1 = self._load_source(algo, file1)
                source2 = self._load_source(algo, file2)
                
                pair = SimilarityPair(
                    id=f"csd_{i}",
                    algorithm=algo,
                    file1=file1,
                    file2=file2,
                    source1=source1,
                    source2=source2,
                    label=int(row.get('label', 0)),
                )
                pairs.append(pair)
        
        return pairs
    
    def _load_from_algorithm_metadata(
        self,
        metadata_file: Path,
        algorithm: str,
        max_pairs: Optional[int] = None
    ) -> List[SimilarityPair]:
        """Load pairs from algorithm-specific metadata.csv."""
        pairs = []
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_pairs and len(pairs) >= max_pairs:
                    break
                
                file1 = row.get('file1', '').strip()
                file2 = row.get('file2', '').strip()
                
                source1 = self._load_source(algorithm, file1)
                source2 = self._load_source(algorithm, file2)
                
                pair = SimilarityPair(
                    id=f"csd_{algorithm}_{i}",
                    algorithm=algorithm,
                    file1=file1,
                    file2=file2,
                    source1=source1,
                    source2=source2,
                    label=int(row.get('label', 0)),
                )
                pairs.append(pair)
        
        return pairs
    
    def _load_source(self, algorithm: str, filename: str) -> str:
        """Load source code for a file."""
        cache_key = f"{algorithm}/{filename}"
        if cache_key in self._source_cache:
            return self._source_cache[cache_key]
        
        snippets_dir = self.data_dir / algorithm / "snippets"
        if not snippets_dir.exists():
            return ""
        
        # Try different extensions
        for ext in [".py", ""]:
            file_path = snippets_dir / f"{filename}{ext}"
            if file_path.exists():
                try:
                    code = file_path.read_text(encoding='utf-8', errors='ignore')
                    self._source_cache[cache_key] = code
                    return code
                except Exception:
                    continue
        
        return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        stats = {
            "name": "CodeSimilarityDataset",
            "language": "python",
            "total_algorithms": len(self.ALGORITHMS),
            "algorithms": self.ALGORITHMS,
            "pairs_loaded": len(self._pairs),
        }
        
        if self._pairs:
            # Count by algorithm
            algo_counts = {}
            for p in self._pairs:
                algo_counts[p.algorithm] = algo_counts.get(p.algorithm, 0) + 1
            stats["pairs_by_algorithm"] = algo_counts
            
            # Count by label
            label_counts = {}
            for p in self._pairs:
                label_counts[p.label] = label_counts.get(p.label, 0) + 1
            stats["pairs_by_label"] = label_counts
        
        return stats
    
    def check_availability(self) -> Dict[str, bool]:
        """Check dataset availability."""
        availability = {
            "data_dir": self.data_dir.exists(),
            "full_metadata": (self.data_dir / "full_metadata.csv").exists(),
        }
        
        for algo in self.ALGORITHMS:
            algo_dir = self.data_dir / algo
            availability[f"algorithm_{algo}"] = algo_dir.exists()
            if algo_dir.exists():
                availability[f"{algo}_snippets"] = (algo_dir / "snippets").exists()
                availability[f"{algo}_metadata"] = (algo_dir / "metadata.csv").exists()
        
        return availability