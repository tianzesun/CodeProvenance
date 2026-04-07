"""Python AST → Graph Builder (CFG + DFG) for CodeProvenance PRL v4.

Implements:
1. CFG (Control Flow Graph): Entry → Blocks → Exit with edges
2. DFG (Data Flow Graph): Variable definitions → uses → redefinitions

Usage:
    from src.benchmark.adapters.python_graph_builder import build_python_graph
    cfg, dfg = build_python_graph(source_code)
    print(f"CFG nodes: {len(cfg_nodes)}, edges: {len(cfg_edges)}")
    print(f"DFG definitions: {len(dfg_defs)}, uses: {len(dfg_uses)}")
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# CFG Data Structures
# =============================================================================

@dataclass
class BasicBlock:
    """A basic block in the Control Flow Graph."""
    id: int
    statements: List[str] = field(default_factory=list)
    ast_nodes: List[ast.AST] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    predecessors: List[int] = field(default_factory=list)
    block_type: str = "block"  # entry, exit, block, branch, loop, call, return

    @property
    def has_branch(self) -> bool:
        return len(self.successors) >= 2

    @property
    def is_exit(self) -> bool:
        return self.block_type == "exit"

    @property
    def is_entry(self) -> bool:
        return self.block_type == "entry"


@dataclass
class CFG:
    """Complete Control Flow Graph."""
    nodes: Dict[int, BasicBlock] = field(default_factory=dict)
    edges: List[Tuple[int, int, str]] = field(default_factory=list)
    entry: int = 0
    exit_block: int = 1

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


# =============================================================================
# DFG Data Structures
# =============================================================================

@dataclass
class VarDef: