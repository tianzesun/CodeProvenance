"""
Core module for CodeProvenance.

Provides intermediate representations (IR) for code analysis.
"""

from src.core.ir import BaseIR, ASTIR, TokenIR, GraphIR, IRMetadata

__all__ = [
    'BaseIR',
    'ASTIR', 
    'TokenIR',
    'GraphIR',
    'IRMetadata',
]