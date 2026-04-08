"""
CodeProvenance Engine Registry.

Provides versioned engine registration for reproducible evaluations.
"""

from src.engines.similarity.codeprovenance.registry import (
    ENGINE_REGISTRY,
    get_engine,
    get_engine_class,
    get_registry_info,
    is_registered,
    list_engines,
    register_engine,
)
from src.engines.similarity.codeprovenance.base import BaseCodeProvenanceEngine
from src.engines.similarity.codeprovenance.v1 import CodeProvenanceV1
from src.engines.similarity.codeprovenance.v2 import CodeProvenanceV2
from src.engines.similarity.codeprovenance.v3 import CodeProvenanceV3

__all__ = [
    'ENGINE_REGISTRY',
    'BaseCodeProvenanceEngine',
    'get_engine',
    'get_engine_class',
    'get_registry_info',
    'is_registered',
    'list_engines',
    'register_engine',
    'CodeProvenanceV1',
    'CodeProvenanceV2',
    'CodeProvenanceV3',
]
