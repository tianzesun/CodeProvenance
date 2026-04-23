"""
Advanced Clone Type Generators for Code Plagiarism Detection

This package provides generators for Type 5 (Adversarial Obfuscation) and
Type 6 (LLM Rewrite) clone pairs that represent modern cheating techniques
not covered by traditional benchmarks.
"""

__version__ = "1.0.0"
__author__ = "IntegrityDesk"
__license__ = "MIT"

from .generators import (
    generate_adversarial_clone,
    generate_llm_clone,
    validate_clone_pair,
    CloneType,
)

__all__ = [
    "generate_adversarial_clone",
    "generate_llm_clone",
    "validate_clone_pair",
    "CloneType",
]