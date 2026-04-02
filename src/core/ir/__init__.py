"""
Intermediate Representation (IR) module.

Provides formal data structures for code representation between
parser/normalizer/similarity modules.
"""

from src.core.ir.base_ir import BaseIR, IRMetadata
from src.core.ir.ast_ir import ASTIR, ASTNode
from src.core.ir.token_ir import TokenIR, Token
from src.core.ir.graph_ir import GraphIR, GraphNode, GraphEdge
from src.core.ir.ir_converter import IRConverter

__all__ = [
    'BaseIR',
    'IRMetadata',
    'ASTIR',
    'ASTNode',
    'TokenIR',
    'Token',
    'GraphIR',
    'GraphNode',
    'GraphEdge',
    'IRConverter',
]