"""Kaggle Student Code Similarity & Plagiarism Dataset Loader.

Dataset: https://www.kaggle.com/datasets/ehsankhani/student-code-similarity-and-plagiarism-labels

Expected structure after download:
    benchmark/data/kaggle_student_code/
    ├── train.csv            # Training data with labels
    ├── test.csv             # Test data
    └── code/                # Source code files

Usage:
    from src.benchmark.datasets.kaggle_student_code import KaggleStudentCodeDataset

    ds = KaggleStudentCodeDataset()
    print(ds.get_stats())
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class KagglePair:
    """A student code pair with similarity label."""
    id: str
    file1: str
    file2: str
    source1: str = ""
    source2: str = ""
    label: float = 0.0  # Similarity score (0.0 - 1.0)


class KaggleStudentCodeDataset:
    """Loads Kaggle Student Code Similarity dataset.
    
    Download from: https://www.kaggle.com/datasets/ehsankhani/student-code-similarity-and-plagiarism-labels
    """
    
    def __init__(self, data_dir: Path = Path("benchmark/data/kaggle_student_code")):
        self.data_dir = data_dir
        self.cheating_file = data_dir / "cheating_dataset.csv"
        self.features_file = data_dir / "cheating_features_dataset.csv"
        self._pairs_cache: List[KagglePair] = []

    def load(self, max_pairs: Optional[int] = None) -> List[KagglePair]:
        """Load student code pairs with similarity labels.
        
        Args:
            max_pairs: Maximum pairs to load.
            
        Returns:
            List of KagglePair objects.
        """
        if not self.cheating_file.exists():
            raise FileNotFoundError(
                f"cheating_dataset.csv not found at {self.cheating_file}\n"
                "Download from: https://www.kaggle.com/datasets/ehsankhani/student-code-similarity-and-plagiarism-labels"
            )
        
        import csv
        pairs = []
        with open(self.cheating_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_pairs and i >= max_pairs:
                    break
                file1 = row.get('File_1', '').strip()
                file2 = row.get('File_2', '').strip()
                
                # Load source code from submission files
                code1, code2 = "", ""
                if file1:
                    f1_path = self.data_dir / file1
                    if f1_path.exists():
                        code1 = f1_path.read_text(encoding='utf-8', errors='ignore')
                if file2:
                    f2_path = self.data_dir / file2
                    if f2_path.exists():
                        code2 = f2_path.read_text(encoding='utf-8', errors='ignore')
                
                pair = KagglePair(
                    id=str(i),
                    file1=file1,
                    file2=file2,
                    source1=code1,
                    source2=code2,
                    label=float(row.get('Label', 0)),
                )
                pairs.append(pair)
        
        self._pairs_cache = pairs
        return pairs
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        stats = {
            "name": "Kaggle Student Code Similarity",
            "cheating_dataset": self.cheating_file.exists(),
            "features_dataset": self.features_file.exists(),
            "pairs_loaded": len(self._pairs_cache),
        }
        if self._pairs_cache:
            labels = [p.label for p in self._pairs_cache]
            stats["label_range"] = (min(labels), max(labels))
            stats["avg_label"] = sum(labels) / len(labels)
            positives = sum(1 for l in labels if l == 1)
            stats["positive_pairs"] = positives
            stats["negative_pairs"] = len(labels) - positives
        return stats
    
    def check_availability(self) -> Dict[str, bool]:
        """Check available files."""
        return {
            "data_dir": self.data_dir.exists(),
            "cheating_dataset": self.cheating_file.exists(),
            "features_dataset": self.features_file.exists(),
        }
