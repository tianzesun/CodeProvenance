"""
Graph Similarity Engine for code similarity detection.

This engine compares two pieces of code by analyzing their
Control Flow Graph (CFG) and Data Flow Graph (DFG) structures.

Similarity is computed at multiple levels:
1. Structural similarity (CFG topology)
2. Data flow similarity (DFG dependencies)
3. Semantic similarity (variable naming + patterns)
"""

import logging
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from src.backend.core.graph.combined_builder import (
    CFGDFGBuilder,
    CombinedGraph,
    compute_cyclomatic_complexity,
)
from src.backend.core.graph.models import (
    CFGNode,
    ControlFlowGraph,
    DataFlowGraph,
    EdgeType,
)

from .base_similarity import BaseSimilarityAlgorithm

logger = logging.getLogger(__name__)

#: Graphs are built per file; every pair rebuilt both. Built graphs are treated as
#: read-only and kept in a small LRU.
_GRAPH_CACHE_SIZE = 64
#: Failures that mean "this input cannot be graphed" rather than "the engine is broken".
_UNGRAPHABLE = (SyntaxError, ValueError, RecursionError, MemoryError)


@dataclass
class GraphSimilarityResult:
    """Result from graph similarity comparison."""

    overall_score: float = 0.0
    structural_score: float = 0.0
    dataflow_score: float = 0.0
    semantic_score: float = 0.0
    complexity_diff: float = 0.0
    node_diff: int = 0
    edge_diff: int = 0
    common_patterns: list[str] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)


class GraphSimilarity(BaseSimilarityAlgorithm):
    """Graph-based similarity algorithm implementing BaseSimilarityAlgorithm.

    Compares code by analyzing CFG and DFG structures. Detects plagiarism even
    with variable renaming, statement reordering, and dead code insertion.
    """

    def __init__(
        self,
        name: str = "GraphSimilarity",
        structural_weight: float = 0.4,
        dataflow_weight: float = 0.35,
        semantic_weight: float = 0.25,
    ) -> None:
        super().__init__(name)
        weights = (structural_weight, dataflow_weight, semantic_weight)
        if any(not math.isfinite(w) or w < 0 for w in weights) or sum(weights) <= 0:
            raise ValueError("component weights must be finite, non-negative and not all zero")
        # Normalised: custom weights that did not sum to 1.0 scaled the score
        # (>1 was silently clamped to a perfect match).
        total = sum(weights)
        self._structural_weight = structural_weight / total
        self._dataflow_weight = dataflow_weight / total
        self._semantic_weight = semantic_weight / total
        self._builder: CFGDFGBuilder = CFGDFGBuilder()  # kept for compatibility
        self._cache: OrderedDict[str, CombinedGraph] = OrderedDict()
        self._cache_lock = threading.Lock()

    # ── Graph construction ─────────────────────────────────────────

    def _build(self, code: str) -> CombinedGraph:
        """Build (or fetch) the combined graph for ``code``.

        A fresh builder per build: the builders carry per-build state, so one shared
        instance is not safe when engines run in a thread pool.
        """
        with self._cache_lock:
            cached = self._cache.get(code)
            if cached is not None:
                self._cache.move_to_end(code)
                return cached
        graph = CFGDFGBuilder().build(code)
        with self._cache_lock:
            self._cache[code] = graph
            while len(self._cache) > _GRAPH_CACHE_SIZE:
                self._cache.popitem(last=False)
        return graph

    @staticmethod
    def _code_of(parsed: dict[str, Any]) -> str:
        """Source text of a parsed dict.

        Only ``"content"`` was read, while every other engine (and the engine
        wrapper, and the visualisation endpoint) passes ``"raw"``; the graph engine
        then saw an empty string, returned 0.0, and its 20% weight dragged the
        combined score down.
        """
        return parsed.get("content") or parsed.get("raw") or ""

    # ── BaseSimilarityAlgorithm interface ──────────────────────────

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> float:
        """Compare two parsed code representations.

        Args:
            parsed_a: Dict with 'content' key containing source code
            parsed_b: Dict with 'content' key containing source code

        Returns:
            Similarity score between 0.0 and 1.0
        """
        code_a = self._code_of(parsed_a)
        code_b = self._code_of(parsed_b)

        if not code_a or not code_b:
            return 0.0

        try:
            graph_a = self._build(code_a)
            graph_b = self._build(code_b)
        except _UNGRAPHABLE as exc:
            # (only SyntaxError used to be handled; NUL bytes, deep nesting ... raised)
            logger.debug("Graph similarity skipped: %s", exc)
            return 0.0

        structural = self._structural(graph_a, graph_b)
        dataflow = self._dataflow(graph_a, graph_b)
        semantic = self._semantic(graph_a, graph_b)

        overall = (
            self._structural_weight * structural
            + self._dataflow_weight * dataflow
            + self._semantic_weight * semantic
        )
        return max(0.0, min(1.0, overall))

    # ── Detailed comparison ────────────────────────────────────────

    def compare_detailed(self, code_a: str, code_b: str) -> GraphSimilarityResult:
        """Compute detailed similarity with per-component breakdown."""
        try:
            graph_a = self._build(code_a)
            graph_b = self._build(code_b)
        except _UNGRAPHABLE:
            return GraphSimilarityResult(
                overall_score=0.0, differences=["Syntax error in input"]
            )

        s = self._structural(graph_a, graph_b)
        d = self._dataflow(graph_a, graph_b)
        m = self._semantic(graph_a, graph_b)
        overall = (
            self._structural_weight * s
            + self._dataflow_weight * d
            + self._semantic_weight * m
        )
        return GraphSimilarityResult(
            overall_score=max(0.0, min(1.0, overall)),
            structural_score=s,
            dataflow_score=d,
            semantic_score=m,
            complexity_diff=(
                compute_cyclomatic_complexity(graph_a.cfg)
                - compute_cyclomatic_complexity(graph_b.cfg)
            ),
            node_diff=graph_a.cfg.node_count - graph_b.cfg.node_count,
            edge_diff=graph_a.cfg.edge_count - graph_b.cfg.edge_count,
            common_patterns=self._common_patterns(graph_a, graph_b),
            differences=self._differences(graph_a, graph_b),
        )

    def compare_functions(
        self,
        code_a: str,
        code_b: str,
        func_a: str,
        func_b: str,
    ) -> GraphSimilarityResult | None:
        """Compare specific functions from two files."""
        try:
            g_a = CFGDFGBuilder().build_for_function(code_a, func_a)
            g_b = CFGDFGBuilder().build_for_function(code_b, func_b)
        except _UNGRAPHABLE:
            return None
        if g_a is None or g_b is None:
            return None
        s = self._structural(g_a, g_b)
        d = self._dataflow(g_a, g_b)
        m = self._semantic(g_a, g_b)
        overall = (
            self._structural_weight * s
            + self._dataflow_weight * d
            + self._semantic_weight * m
        )
        return GraphSimilarityResult(
            overall_score=max(0.0, min(1.0, overall)),
            structural_score=s,
            dataflow_score=d,
            semantic_score=m,
            complexity_diff=(
                compute_cyclomatic_complexity(g_a.cfg)
                - compute_cyclomatic_complexity(g_b.cfg)
            ),
            node_diff=g_a.cfg.node_count - g_b.cfg.node_count,
            edge_diff=g_a.cfg.edge_count - g_b.cfg.edge_count,
        )

    # ── Structural similarity ──────────────────────────────────────

    def _structural(self, a: CombinedGraph, b: CombinedGraph) -> float:
        ca, cb = a.cfg, b.cfg
        if ca.node_count == 0 or cb.node_count == 0:
            return 0.0
        return (
            0.25 * self._node_type_sim(ca, cb)
            + 0.20 * self._edge_type_sim(ca, cb)
            + 0.25 * self._branching_sim(ca, cb)
            + 0.15 * self._loop_sim(ca, cb)
            + 0.15 * self._size_sim(ca, cb)
        )

    def _node_type_sim(self, a: ControlFlowGraph, b: ControlFlowGraph) -> float:
        ta: dict[str, int] = {}
        tb: dict[str, int] = {}
        for n in a.nodes.values():
            ta[n.node_type] = ta.get(n.node_type, 0) + 1
        for n in b.nodes.values():
            tb[n.node_type] = tb.get(n.node_type, 0) + 1
        return self._cosine(ta, tb)

    def _edge_type_sim(self, a: ControlFlowGraph, b: ControlFlowGraph) -> float:
        ta: dict[str, int] = {}
        tb: dict[str, int] = {}
        for e in a.edges:
            ta[e.edge_type.value] = ta.get(e.edge_type.value, 0) + 1
        for e in b.edges:
            tb[e.edge_type.value] = tb.get(e.edge_type.value, 0) + 1
        return self._cosine(ta, tb)

    def _branching_sim(self, a: ControlFlowGraph, b: ControlFlowGraph) -> float:
        ba = sum(
            1
            for e in a.edges
            if e.edge_type in (EdgeType.TRUE_BRANCH, EdgeType.FALSE_BRANCH)
        )
        bb = sum(
            1
            for e in b.edges
            if e.edge_type in (EdgeType.TRUE_BRANCH, EdgeType.FALSE_BRANCH)
        )
        if ba == 0 and bb == 0:
            return 1.0
        if ba == 0 or bb == 0:
            return 0.0
        na = ba / max(1, a.node_count)
        nb = bb / max(1, b.node_count)
        return 1.0 - abs(na - nb)

    def _loop_sim(self, a: ControlFlowGraph, b: ControlFlowGraph) -> float:
        la = sum(1 for e in a.edges if e.edge_type == EdgeType.LOOP_BACK)
        lb = sum(1 for e in b.edges if e.edge_type == EdgeType.LOOP_BACK)
        if la == 0 and lb == 0:
            return 1.0
        if la == 0 or lb == 0:
            return 0.0
        return 1.0 - abs(la - lb) / max(la, lb)

    def _size_sim(self, a: ControlFlowGraph, b: ControlFlowGraph) -> float:
        sa = a.node_count + a.edge_count
        sb = b.node_count + b.edge_count
        if sa == 0 and sb == 0:
            return 1.0
        if sa == 0 or sb == 0:
            return 0.0
        return 1.0 - abs(sa - sb) / max(sa, sb)

    # ── Data-flow similarity ───────────────────────────────────────

    def _dataflow(self, a: CombinedGraph, b: CombinedGraph) -> float:
        da, db = a.dfg, b.dfg
        return (
            0.20 * self._var_count_sim(da, db)
            + 0.30 * self._dep_pattern_sim(da, db)
            + 0.20 * self._scope_sim(a, b)
            + 0.30 * self._defuse_sim(da, db)
        )

    def _var_count_sim(self, a: DataFlowGraph, b: DataFlowGraph) -> float:
        """Similarity of the NUMBER of variables.

        It compared the variable NAMES (Jaccard), so renaming every variable scored 0
        here, contradicting the engine's purpose ("detects plagiarism even with
        variable renaming") and the method's own name.
        """
        na, nb = len(a.variables), len(b.variables)
        if na == 0 and nb == 0:
            return 1.0
        if na == 0 or nb == 0:
            return 0.0
        return min(na, nb) / max(na, nb)

    def _dep_pattern_sim(self, a: DataFlowGraph, b: DataFlowGraph) -> float:
        if a.edge_count == 0 and b.edge_count == 0:
            return 1.0
        if a.edge_count == 0 or b.edge_count == 0:
            return 0.0
        da: dict[int, int] = {}
        db: dict[int, int] = {}
        for e in a.edges:
            da[e.source] = da.get(e.source, 0) + 1
        for e in b.edges:
            db[e.source] = db.get(e.source, 0) + 1
        if not da or not db:
            return 0.0
        return self._dist_sim(list(da.values()), list(db.values()))

    def _scope_sim(self, a: CombinedGraph, b: CombinedGraph) -> float:
        sa = len(a.cfg.get_all_scopes())
        sb = len(b.cfg.get_all_scopes())
        if sa == 0 and sb == 0:
            return 1.0
        if sa == 0 or sb == 0:
            return 0.0
        return 1.0 - abs(sa - sb) / max(sa, sb)

    def _defuse_sim(self, a: DataFlowGraph, b: DataFlowGraph) -> float:
        ca = self._chain_lengths(a)
        cb = self._chain_lengths(b)
        if not ca and not cb:
            return 1.0
        if not ca or not cb:
            return 0.0
        return self._dist_sim(ca, cb)

    def _chain_lengths(self, dfg: DataFlowGraph) -> list[int]:
        groups: dict[str, int] = {}
        for e in dfg.edges:
            groups[e.variable] = groups.get(e.variable, 0) + 1
        return list(groups.values())

    # ── Semantic similarity ────────────────────────────────────────

    def _semantic(self, a: CombinedGraph, b: CombinedGraph) -> float:
        return 0.5 * self._seq_sim(a, b) + 0.5 * self._pattern_sim(a, b)

    def _seq_sim(self, a: CombinedGraph, b: CombinedGraph) -> float:
        na = list(a.cfg.nodes.values())
        nb = list(b.cfg.nodes.values())
        if not na and not nb:
            return 1.0
        if not na or not nb:
            return 0.0
        return self._cosine(self._bigrams(na), self._bigrams(nb))

    def _bigrams(self, nodes: list[CFGNode]) -> dict[str, int]:
        result: dict[str, int] = {}
        for i in range(len(nodes) - 1):
            key = f"{nodes[i].node_type}->{nodes[i + 1].node_type}"
            result[key] = result.get(key, 0) + 1
        return result

    def _pattern_sim(self, a: CombinedGraph, b: CombinedGraph) -> float:
        pa = self._patterns(a)
        pb = self._patterns(b)
        if not pa and not pb:
            return 1.0
        if not pa or not pb:
            return 0.0
        return len(pa & pb) / len(pa | pb)

    def _patterns(self, g: CombinedGraph) -> set[str]:
        p: set[str] = set()
        types = {n.node_type for n in g.cfg.nodes.values()}
        if "ForHeader" in types:
            p.add("for_loop")
        if "WhileCondition" in types:
            p.add("while_loop")
        if "Condition" in types:
            p.add("conditional")
        if "TryEntry" in types:
            p.add("try_except")
        if "Return" in types:
            p.add("return")
        if "FunctionDef" in types:
            p.add("nested_function")
        if "ClassDef" in types:
            p.add("class_definition")
        if "WithEntry" in types:
            p.add("context_manager")
        for defs in g.dfg.variable_definitions.values():
            if len(defs) > 1:
                p.add("accumulator")
                break
        return p

    # ── Diagnostics ────────────────────────────────────────────────

    def _common_patterns(self, a: CombinedGraph, b: CombinedGraph) -> list[str]:
        return list(self._patterns(a) & self._patterns(b))

    def _differences(self, a: CombinedGraph, b: CombinedGraph) -> list[str]:
        diffs: list[str] = []
        nd = abs(a.cfg.node_count - b.cfg.node_count)
        if nd > max(1, a.cfg.node_count * 0.3):
            diffs.append(
                f"Node count difference: {a.cfg.node_count} vs {b.cfg.node_count}"
            )
        va, vb = a.dfg.variables, b.dfg.variables
        if va - vb:
            diffs.append(f"Variables only in A: {va - vb}")
        if vb - va:
            diffs.append(f"Variables only in B: {vb - va}")
        pa, pb = self._patterns(a), self._patterns(b)
        if pa - pb:
            diffs.append(f"Patterns only in A: {pa - pb}")
        if pb - pa:
            diffs.append(f"Patterns only in B: {pb - pa}")
        return diffs

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _cosine(a: dict[str, int], b: dict[str, int]) -> float:
        keys = set(a) | set(b)
        if not keys:
            return 1.0
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        na = math.sqrt(sum(v**2 for v in a.values()))
        nb = math.sqrt(sum(v**2 for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def _dist_sim(a: list[int], b: list[int]) -> float:
        if not a or not b:
            return 0.0
        ma = sum(a) / len(a)
        mb = sum(b) / len(b)
        mx = max(max(a), max(b))
        if mx == 0:
            return 1.0
        return 1.0 - abs(ma - mb) / mx


# ── Convenience factory ───────────────────────────────────────────


def make_graph_similarity() -> GraphSimilarity:
    """Create a GraphSimilarity instance for use with SimilarityEngine."""
    return GraphSimilarity()
