"""Adapter for our detection engines."""
from __future__ import annotations
from typing import List, Tuple
from evalforge.adapters.base import ToolAdapter
from benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine


class OurTokenAdapter(ToolAdapter):
    def __init__(self):
        self._engine = TokenWinnowingEngine()
    @property
    def name(self) -> str: return "our_token"
    def predict(self, pairs): return [self._engine.compare(a, b) for a, b in pairs]


class OurASTAdapter(ToolAdapter):
    def __init__(self):
        self._engine = ASTEngine()
    @property
    def name(self) -> str: return "our_ast"
    def predict(self, pairs): return [self._engine.compare(a, b) for a, b in pairs]


class OurHybridAdapter(ToolAdapter):
    def __init__(self):
        self._engine = HybridEngine()
    @property
    def name(self) -> str: return "our_hybrid"
    def predict(self, pairs): return [self._engine.compare(a, b) for a, b in pairs]


TOOL_REGISTRY = {
    "our_token": OurTokenAdapter,
    "our_ast": OurASTAdapter,
    "our_hybrid": OurHybridAdapter,
}

def get_tool(name):
    cls = TOOL_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Tool '{name}' not found. Available: {list(TOOL_REGISTRY.keys())}")
    return cls()
