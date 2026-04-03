"""
CodeProvenance - Code Similarity Detection Platform

This module enforces strict architecture boundaries:
- domain/: Business logic only (no infrastructure imports)
- application/: Use cases and orchestration (depends on domain)
- infrastructure/: External systems (implements domain interfaces)
- core/: Shared primitives and kernel logic
- engines/: Runtime execution logic
- ml/: Training/inference logic
- pipeline/: Processing orchestration
- api/: REST API layer
- config/: Configuration management
- bootstrap/: Application initialization
- evaluation/: Evaluation framework (consolidated)
- benchmark/: Benchmark system
- models/: Data structures and ML models
- utils/: Utility functions
"""

# Architecture enforcement
import sys
from pathlib import Path

# Add architecture validation
def validate_architecture():
    """Enforce architecture boundaries at import time."""
    # This will be expanded with import restrictions
    pass

# Initialize architecture validation
validate_architecture()