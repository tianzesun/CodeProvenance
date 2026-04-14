"""
Base CodeProvenance Engine.

Defines the abstract interface for all CodeProvenance engine versions.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from src.backend.core.ir.base_ir import BaseIR


class BaseCodeProvenanceEngine(ABC):
    """Abstract base class for CodeProvenance engines.
    
    All engine versions must implement this interface to ensure
    consistent behavior and reproducible evaluations.
    """
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Engine version identifier (e.g., 'codeprovenance:v1')."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name."""
        pass
    
    @property
    def description(self) -> str:
        """Engine description."""
        return f"CodeProvenance Engine {self.version}"
    
    @abstractmethod
    def compare(self, code_a: str, code_b: str, **kwargs) -> float:
        """Compare two code snippets and return similarity score.
        
        Args:
            code_a: First code snippet
            code_b: Second code snippet
            **kwargs: Additional parameters
            
        Returns:
            Similarity score in [0.0, 1.0]
        """
        pass
    
    def compare_ir(self, ir_a: BaseIR, ir_b: BaseIR, **kwargs) -> float:
        """Compare two IR representations.
        
        Default implementation converts IR to source and compares.
        Subclasses can override for more efficient IR-based comparison.
        
        Args:
            ir_a: First IR representation
            ir_b: Second IR representation
            **kwargs: Additional parameters
            
        Returns:
            Similarity score in [0.0, 1.0]
        """
        # Default: convert IR to source (if available)
        # This is a fallback - subclasses should override for efficiency
        raise NotImplementedError(
            f"IR comparison not implemented for {self.version}. "
            "Use compare() with source code instead."
        )
    
    def get_config(self) -> Dict[str, Any]:
        """Get engine configuration.
        
        Returns:
            Dictionary of engine configuration parameters
        """
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
        }
    
    def __repr__(self) -> str:
        """String representation of engine."""
        return f"{self.__class__.__name__}(version={self.version})"
    
    def __str__(self) -> str:
        """String representation of engine."""
        return f"{self.name} ({self.version})"
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on version."""
        if not isinstance(other, BaseCodeProvenanceEngine):
            return False
        return self.version == other.version
    
    def __hash__(self) -> int:
        """Hash based on version."""
        return hash(self.version)