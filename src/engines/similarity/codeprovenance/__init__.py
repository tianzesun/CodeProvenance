"""
CodeProvenance Engine Registry.

Provides versioned engine registration for reproducible evaluations.
"""

from src.engines.similarity.codeprovenance.registry import (
    ENGINE_REGISTRY,
    register_engine,
    get_engine,
    list_engines,
)
from src.engines.similarity.codeprovenance.base import BaseCodeProvenanceEngine

__all__ = [
    'ENGINE_REGISTRY',
    'register_engine',
    'get_engine',
    'list_engines',
    'BaseCodeProvenanceEngine',
]