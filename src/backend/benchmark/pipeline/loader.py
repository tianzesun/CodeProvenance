"""Dataset loader contract.

All dataset loaders must implement the CanonicalDataset interface.
This ensures datasets are pluggable and comparable.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, field

# Re-export canonical definitions from schema.py
from src.backend.benchmark.datasets.schema import CodePair, CanonicalDataset


@dataclass
class CodeSample:
    """A single code sample from a dataset."""
    id: str
    code: str
    language: str = "java"
    metadata: Dict[str, Any] = field(default_factory=dict)


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
