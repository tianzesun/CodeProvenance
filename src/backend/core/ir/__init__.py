"""
Public IR exports.

The repo carries concrete IR implementations in dedicated modules. This package
re-exports those stable public types so callers can keep importing from
``src.backend.core.ir``.
"""

from .ast_ir import ASTIR, ASTNode
from .base_ir import SUPPORTED_LANGUAGES, BaseIR, IRMetadata, normalize_language
from .graph_ir import GraphEdge, GraphIR, GraphNode
from .ir_converter import IRConverter
from .token_ir import Token, TokenIR

__all__ = [
    "ASTIR",
    "SUPPORTED_LANGUAGES",
    "ASTNode",
    "BaseIR",
    "GraphEdge",
    "GraphIR",
    "GraphNode",
    "IRConverter",
    "IRMetadata",
    "Token",
    "TokenIR",
    "normalize_language",
]
