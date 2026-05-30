"""File-type dependent weighting rules for similarity detection.

This module defines how different file types should be weighted
during similarity scoring to prevent false positives in configuration
files, build artifacts, and other non-CODE content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.backend.engines.file_type_classifier import FileType


@dataclass
class FileTypeWeights:
    """Weight configuration for a specific file type.

    Attributes:
        embedding: Weight for embedding similarity (should be near-zero for CONFIG)
        ast: Weight for AST/structural similarity
        fingerprint: Weight for token/fingerprint similarity
        ngram: Weight for n-gram similarity
        winnowing: Weight for winnowing similarity
        graph: Weight for graph-based similarity
        static_rules: Weight for static analysis rules
        sklearn_cosine: Weight for TF-IDF cosine similarity
    """

    embedding: float = 1.0
    ast: float = 1.0
    fingerprint: float = 1.0
    ngram: float = 1.0
    winnowing: float = 1.0
    graph: float = 1.0
    static_rules: float = 1.0
    sklearn_cosine: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "embedding": self.embedding,
            "ast": self.ast,
            "fingerprint": self.fingerprint,
            "ngram": self.ngram,
            "winnowing": self.winnowing,
            "graph": self.graph,
            "static_rules": self.static_rules,
            "sklearn_cosine": self.sklearn_cosine,
        }


# Default weights for CODE files - balanced multi-signal evaluation
CODE_WEIGHTS = FileTypeWeights(
    embedding=1.0,  # Can be used as primary signal for code
    ast=1.0,  # Structural similarity is dominant
    fingerprint=1.0,  # Token matching is relevant
    ngram=1.0,  # N-gram similarity is relevant
    winnowing=1.0,  # Winnowing is relevant
    graph=1.0,  # Graph similarity is relevant
    static_rules=1.0,  # Static rules are relevant
    sklearn_cosine=1.0,  # TF-IDF is relevant
)

# CONFIG file weights - embedding MUST be near-zero
# Structural similarity dominates, key overlap is NOT plagiarism
CONFIG_WEIGHTS = FileTypeWeights(
    embedding=0.0,  # NEAR-ZERO: Embedding similarity must NOT be used
    ast=1.0,  # Structural comparison IS relevant
    fingerprint=0.3,  # Token matching interpreted cautiously
    ngram=0.3,  # N-gram similarity interpreted cautiously
    winnowing=0.3,  # Winnowing interpreted cautiously
    graph=0.5,  # Graph similarity with caution
    static_rules=0.5,  # Static rules with caution
    sklearn_cosine=0.3,  # TF-IDF with caution
)

# SCRIPT file weights - similar to CONFIG but with more structural emphasis
SCRIPT_WEIGHTS = FileTypeWeights(
    embedding=0.1,  # Very low - scripts often have similar patterns
    ast=0.8,  # Structural similarity is relevant
    fingerprint=0.5,  # Token matching with caution
    ngram=0.5,  # N-gram similarity with caution
    winnowing=0.5,  # Winnowing with caution
    graph=0.5,  # Graph similarity with caution
    static_rules=0.8,  # Static rules are relevant
    sklearn_cosine=0.3,  # TF-IDF with caution
)

# DATA file weights - key/value similarity must NOT be treated as plagiarism
DATA_WEIGHTS = FileTypeWeights(
    embedding=0.0,  # NEAR-ZERO: Semantic similarity not relevant
    ast=0.1,  # AST not relevant for data
    fingerprint=0.2,  # Token matching with caution
    ngram=0.2,  # N-gram similarity with caution
    winnowing=0.2,  # Winnowing with caution
    graph=0.1,  # Graph similarity not relevant
    static_rules=0.1,  # Static rules not relevant
    sklearn_cosine=0.1,  # TF-IDF with extreme caution
)

# MIXED file weights - default balanced approach
MIXED_WEIGHTS = FileTypeWeights(
    embedding=0.5,  # Moderate weight
    ast=1.0,  # Structural similarity is relevant
    fingerprint=0.8,  # Token matching with caution
    ngram=0.8,  # N-gram similarity with caution
    winnowing=0.8,  # Winnowing with caution
    graph=0.8,  # Graph similarity with caution
    static_rules=0.8,  # Static rules with caution
    sklearn_cosine=0.5,  # TF-IDF with caution
)


# Mapping from file type to weights
FILE_TYPE_WEIGHTS: Dict[FileType, FileTypeWeights] = {
    FileType.CODE: CODE_WEIGHTS,
    FileType.CONFIG: CONFIG_WEIGHTS,
    FileType.SCRIPT: SCRIPT_WEIGHTS,
    FileType.DATA: DATA_WEIGHTS,
    FileType.MIXED: MIXED_WEIGHTS,
}


def get_weights_for_file_type(file_type: FileType) -> FileTypeWeights:
    """Get the weight configuration for a file type.

    Args:
        file_type: The classification of the file pair.

    Returns:
        FileTypeWeights appropriate for the file type.
    """
    return FILE_TYPE_WEIGHTS.get(file_type, MIXED_WEIGHTS)


def apply_weights(
    raw_scores: Dict[str, float],
    file_type: FileType,
) -> Dict[str, float]:
    """Apply file-type dependent weights to raw scores.

    Args:
        raw_scores: Dictionary of engine names to raw similarity scores.
        file_type: The classification of the file pair.

    Returns:
        Dictionary of weighted scores.
    """
    weights = get_weights_for_file_type(file_type)
    weight_dict = weights.to_dict()

    return {
        engine: score * weight_dict.get(engine, 1.0)
        for engine, score in raw_scores.items()
    }


# Threshold for considering embedding as a decisive signal
EMBEDDING_DECISIVE_THRESHOLD = 0.95

# Domains where embedding should never be decisive
EMBEDDING_VETO_DOMAINS = {
    "tailwind",
    "postcss",
    "babel",
    "eslint",
    "prettier",
    "vite",
    "webpack",
    "next",
    "nuxt",
    "angular",
}


def should_veto_embedding(file_type: FileType, domain: str = None) -> bool:
    """Determine if embedding similarity should be vetoed.

    Args:
        file_type: The classification of the file pair.
        domain: Optional domain identifier for config files.

    Returns:
        True if embedding should be heavily discounted or vetoed.
    """
    # Veto for CONFIG files
    if file_type == FileType.CONFIG:
        return True

    # Veto for specific domains
    if domain and domain in EMBEDDING_VETO_DOMAINS:
        return True

    return False
