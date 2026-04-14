"""
Core Module - Strict Invariants and Primitives

This module contains strict invariants and primitives only.
It does NOT contain business logic or utilities.

Responsibility: Base classes, interfaces, constants, mathematical primitives
"""

from typing import Dict, Any, Optional, List, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import hashlib
import json


# ============================================================================
# CONSTANTS
# ============================================================================

# Mathematical constants
PI = 3.14159265359
E = 2.71828182846

# System constants
MAX_BATCH_SIZE = 1000
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3

# Similarity thresholds
SIMILARITY_THRESHOLDS = {
    "identical": 1.0,
    "very_similar": 0.9,
    "similar": 0.7,
    "somewhat_similar": 0.5,
    "different": 0.3,
    "very_different": 0.0
}


# ============================================================================
# INTERFACES (Protocol-based)
# ============================================================================

class Serializable(Protocol):
    """Interface for serializable objects."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        ...
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load from dictionary."""
        ...


class Validatable(Protocol):
    """Interface for validatable objects."""
    
    def validate(self) -> List[str]:
        """Validate and return list of errors."""
        ...


class Hashable(Protocol):
    """Interface for hashable objects."""
    
    def compute_hash(self) -> str:
        """Compute hash of the object."""
        ...


# ============================================================================
# BASE CLASSES
# ============================================================================

@dataclass
class BaseValueObject:
    """Base class for value objects."""
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))


@dataclass
class BaseEntity:
    """Base class for entities."""
    
    id: str
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)


class BaseEnum(Enum):
    """Base class for enums with validation."""
    
    @classmethod
    def from_string(cls, value: str) -> 'BaseEnum':
        """Create enum from string."""
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid {cls.__name__}: {value}")
    
    def to_string(self) -> str:
        """Convert to string."""
        return self.value


# ============================================================================
# MATHEMATICAL PRIMITIVES
# ============================================================================

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have same length")
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


# ============================================================================
# HASHING UTILITIES
# ============================================================================

def compute_hash(data: Any) -> str:
    """Compute SHA-256 hash of data."""
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    elif isinstance(data, bytes):
        data_bytes = data
    else:
        data_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
    
    return hashlib.sha256(data_bytes).hexdigest()


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


# ============================================================================
# VALIDATION PRIMITIVES
# ============================================================================

def validate_non_empty(value: Any, field_name: str) -> List[str]:
    """Validate that value is not empty."""
    errors = []
    
    if value is None:
        errors.append(f"{field_name} cannot be None")
    elif isinstance(value, str) and not value.strip():
        errors.append(f"{field_name} cannot be empty")
    elif isinstance(value, (list, dict)) and not value:
        errors.append(f"{field_name} cannot be empty")
    
    return errors


def validate_positive(value: float, field_name: str) -> List[str]:
    """Validate that value is positive."""
    errors = []
    
    if value <= 0:
        errors.append(f"{field_name} must be positive")
    
    return errors


def validate_range(value: float, min_val: float, max_val: float, field_name: str) -> List[str]:
    """Validate that value is within range."""
    errors = []
    
    if value < min_val or value > max_val:
        errors.append(f"{field_name} must be between {min_val} and {max_val}")
    
    return errors