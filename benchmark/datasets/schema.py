"""Dataset Contract Schema for CodeProvenance.

Provides formal metadata contracts for cross-dataset comparison:
- DatasetMetadata: Contract for dataset metadata
- DatasetContract: Base class for all dataset loaders
- CloneType: Standardized clone types
- Difficulty: Dataset difficulty levels

This module enables:
- Consistent metadata across datasets
- Cross-dataset comparison
- Validation catches issues early
- Documentation becomes self-describing

Usage:
    from benchmark.datasets.schema import DatasetContract, DatasetMetadata, CloneType, Difficulty

    class MyDataset(DatasetContract):
        @property
        def metadata(self) -> DatasetMetadata:
            return DatasetMetadata(...)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CloneType(Enum):
    """Standardized clone types.
    
    Based on the four-type clone classification:
    - TYPE_1: Identical code (only whitespace/formatting differences)
    - TYPE_2: Renamed identifiers (same structure, different names)
    - TYPE_3: Restructured code (same logic, different structure)
    - TYPE_4: Semantic clones (same meaning, different syntax)
    """
    TYPE_1 = "type1"  # Identical
    TYPE_2 = "type2"  # Renamed
    TYPE_3 = "type3"  # Restructured
    TYPE_4 = "type4"  # Semantic


class Difficulty(Enum):
    """Dataset difficulty levels.
    
    - EASY: Simple clones, high detector accuracy expected
    - MEDIUM: Moderate complexity
    - HARD: Complex clones, challenging for detectors
    - EXPERT: Extremely difficult, state-of-the-art detectors struggle
    """
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class DatasetMetadata:
    """Contract for dataset metadata.
    
    All datasets must provide this metadata for cross-dataset comparison.
    
    Attributes:
        name: Dataset name (e.g., "BigCloneBench").
        version: Dataset version (e.g., "bceval_2024").
        language: Programming language (e.g., "java").
        clone_types: List of clone types present in dataset.
        difficulty: Dataset difficulty level.
        size: Number of pairs in dataset.
        source: Where the dataset came from (URL, paper, etc.).
        license: License for the dataset.
        ground_truth_format: Format of ground truth ("binary", "continuous", "multi-class").
        description: Human-readable description of the dataset.
    """
    name: str
    version: str
    language: str
    clone_types: List[CloneType]
    difficulty: Difficulty
    size: int  # Number of pairs
    source: str  # Where it came from
    license: str
    ground_truth_format: str  # "binary", "continuous", "multi-class"
    description: str
    
    def validate(self) -> bool:
        """Validate metadata completeness.
        
        Returns:
            True if all required fields are present and valid.
        """
        required = [
            self.name,
            self.version,
            self.language,
            self.clone_types,
            self.size > 0,
            self.source,
            self.ground_truth_format,
        ]
        return all(required)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "name": self.name,
            "version": self.version,
            "language": self.language,
            "clone_types": [ct.value for ct in self.clone_types],
            "difficulty": self.difficulty.value,
            "size": self.size,
            "source": self.source,
            "license": self.license,
            "ground_truth_format": self.ground_truth_format,
            "description": self.description,
        }


@dataclass
class CodePair:
    """A pair of code snippets with ground truth.
    
    Attributes:
        id_a: Identifier for first code snippet.
        id_b: Identifier for second code snippet.
        code_a: First code snippet.
        code_b: Second code snippet.
        label: Ground truth label (1 for clone, 0 for non-clone).
        clone_type: Clone type (1-4 for clones, 0 for non-clone).
    """
    id_a: str
    id_b: str
    code_a: str
    code_b: str
    label: int
    clone_type: int = 0


@dataclass
class CanonicalDataset:
    """Canonical dataset representation.
    
    Attributes:
        name: Dataset name.
        version: Dataset version.
        pairs: List of code pairs.
        metadata: Dataset metadata.
    """
    name: str
    version: str
    pairs: List[CodePair] = field(default_factory=list)
    metadata: Optional[DatasetMetadata] = None
    
    def get_ground_truth(self) -> Dict[tuple, int]:
        """Get ground truth mapping.
        
        Returns:
            Dictionary mapping (id_a, id_b) to label.
        """
        return {(p.id_a, p.id_b): p.label for p in self.pairs}
    
    def get_clone_type_map(self) -> Dict[tuple, int]:
        """Get clone type mapping.
        
        Returns:
            Dictionary mapping (id_a, id_b) to clone_type.
        """
        return {(p.id_a, p.id_b): p.clone_type for p in self.pairs}


class DatasetContract(ABC):
    """Base class for all dataset loaders.
    
    All dataset loaders must implement this contract to ensure
    consistent metadata and loading behavior.
    
    Usage:
        class MyDataset(DatasetContract):
            @property
            def metadata(self) -> DatasetMetadata:
                return DatasetMetadata(
                    name="MyDataset",
                    version="1.0",
                    ...
                )
            
            def load(self, **kwargs) -> CanonicalDataset:
                # Load dataset
                ...
    """
    
    @property
    @abstractmethod
    def metadata(self) -> DatasetMetadata:
        """Return dataset metadata.
        
        Returns:
            DatasetMetadata with all required fields.
        """
        pass
    
    @abstractmethod
    def load(self, **kwargs) -> CanonicalDataset:
        """Load dataset.
        
        Args:
            **kwargs: Additional arguments for loading.
            
        Returns:
            CanonicalDataset with loaded pairs.
        """
        pass
    
    def validate(self) -> bool:
        """Validate dataset integrity.
        
        Returns:
            True if dataset is valid.
        """
        return self.metadata.validate()
    
    def info(self) -> Dict[str, Any]:
        """Get dataset information.
        
        Returns:
            Dictionary with dataset information.
        """
        return self.metadata.to_dict()