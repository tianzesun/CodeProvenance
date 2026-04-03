"""Dataset loader contract.

All dataset loaders must implement the CanonicalDataset interface.
This ensures datasets are pluggable and comparable.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class CodeSample:
    """A single code sample from a dataset."""
    id: str
    code: str
    language: str = "java"
    metadata: Dict[str, Any] = None


@dataclass
class CodePair:
    """A pair of code samples with ground truth label."""
    id_a: str
    code_a: str
    id_b: str
    code_b: str
    label: int  # 1 = clone/plagiarism, 0 = non-clone
    clone_type: int = 0  # 1-4 for BigCloneBench, 0 otherwise
    metadata: Dict[str, Any] = field(default_factory=dict)


class CanonicalDataset:
    """Canonical dataset format for the pipeline.
    
    All dataset loaders must convert to this format.
    """
    def __init__(
        self,
        name: str,
        version: str,
        pairs: List[CodePair],
        submissions: Optional[List[CodeSample]] = None
    ):
        self.name = name
        self.version = version
        self.pairs = pairs
        self.submissions = submissions or []
    
    def __len__(self) -> int:
        return len(self.pairs)
    
    def get_ground_truth(self) -> Dict[Tuple[str, str], int]:
        """Get ground truth as (id_a, id_b) -> label mapping.
        
        Returns:
            Ground truth dictionary.
        """
        return {
            (p.id_a, p.id_b): p.label
            for p in self.pairs
        }
    
    def get_query_results(self) -> Dict[str, List[Tuple[str, float, int]]]:
        """Get data formatted for ranking evaluation.
        
        Returns:
            Dict mapping query_id to list of (doc_id, score, relevance).
        """
        queries = {}
        for pair in self.pairs:
            if pair.id_a not in queries:
                queries[pair.id_a] = []
            queries[pair.id_a].append((pair.id_b, 0.0, pair.label))
        return queries

    def get_clone_type_map(self) -> Dict[Tuple[str, str], int]:
        """Get mapping of pair IDs to clone type.
        
        Returns:
            Dict mapping (id_a, id_b) -> clone_type.
        """
        return {
            (p.id_a, p.id_b): p.clone_type
            for p in self.pairs
        }


class DatasetLoader(ABC):
    """Abstract base class for all dataset loaders.
    
    All dataset loaders must implement this interface.
    This ensures datasets are pluggable and comparable.
    
    Usage:
        class MyDatasetLoader(DatasetLoader):
            def name(self) -> str:
                return "my_dataset"
            
            def version(self) -> str:
                return "1.0"
            
            def load(self, path) -> CanonicalDataset:
                ...
    """
    
    @abstractmethod
    def name(self) -> str:
        """Return dataset name."""
        pass
    
    @abstractmethod
    def version(self) -> str:
        """Return dataset version."""
        pass
    
    @abstractmethod
    def load(self, path: str) -> CanonicalDataset:
        """Load dataset from path.
        
        Args:
            path: Path to dataset.
            
        Returns:
            CanonicalDataset with pairs and/or submissions.
        """
        pass
    
    def load_submissions(self, path: str) -> List[CodeSample]:
        """Load individual submissions (optional).
        
        Args:
            path: Path to submissions.
            
        Returns:
            List of CodeSample objects.
        """
        return []
    
    def load_pairs(self, path: str) -> List[CodePair]:
        """Load code pairs with labels.
        
        Args:
            path: Path to pairs.
            
        Returns:
            List of CodePair objects.
        """
        return []