"""Code normalization and canonicalization module.

Provides:
- canonicalizer.py: Identifier normalization, literal abstraction, whitespace removal
  This is the critical layer that fixes Type-2 (renamed) clone detection.
"""
from benchmark.normalization.canonicalizer import (
    Canonicalizer,
    CanonicalComparePipeline,
    CanonicalizationConfig,
    CanonicalizationResult,
    create_canonical_engines,
)

__all__ = [
    "Canonicalizer",
    "CanonicalComparePipeline",
    "CanonicalizationConfig",
    "CanonicalizationResult",
    "create_canonical_engines",
]