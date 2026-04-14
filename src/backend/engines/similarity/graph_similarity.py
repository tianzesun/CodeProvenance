"""
Graph Similarity Engine for code similarity detection.

This engine compares two pieces of code by analyzing their
Control Flow Graph (CFG) and Data Flow Graph (DFG) structures.

Similarity is computed at multiple levels:
1. Structural similarity (CFG topology)
2. Data flow similarity (DFG dependencies)
3. Semantic similarity (variable naming + patterns)
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.backend.core.graph.combined_builder import (
    CFGDFGBuilder,
    CombinedGraph,
    compute_cyclomatic_complexity,
)
from src.backend.core.graph.models import (
    CFGNode,
    ControlFlowGraph,
    DataFlowGraph,
    DFEdge,
    EdgeType,
)
from .base_similarity import BaseSimilarityAlgorithm


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
    common_patterns: List[str] = field(default_factory=list)
    differences: List[str] = field(default_factory=list)


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
        self._structural_weight = structural_weight
        self._dataflow_weight = dataflow_weight
        self._semantic_weight = semantic_weight
        self._builder: CFGDFGBuilder = CFGDFGBuilder()

    # ── BaseSimilarityAlgorithm interface ──────────────────────────

    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """Compare two parsed code representations.

        Args:
            parsed_a: Dict with 'content' key containing source code
            parsed_b: Dict with 'content' key containing source code

        Returns:
            Similarity score between 0.0 and 1.0
        """
        code_a = parsed_a.get("content", "")
        code_b = parsed_b.get("content", "")

        if not code_a or not code_b:
            return 0.0

        try:
            graph_a = self._builder.build(code_a)
            graph_b = self._builder.build(code_b)
        except SyntaxError:
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
            graph_a = self._builder.build(code_a)
            graph_b = self._builder.build(code_b)
        except SyntaxError:
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
        self, code_a: str, code_b: str, func_a: str, func_b: str,
    ) -> Optional[GraphSimilarityResult]:
        """Compare specific functions from two files."""
        g_a = self._builder.build_for_function(code_a, func_a)
        g_b = self._builder.build_for_function(code_b, func_b)
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
        ta: Dict[str, int] = {}
        tb: Dict[str, int] = {}
        for n in a.nodes.values():
            ta[n.node_type] = ta.get(n.node_type, 0) + 1
        for n in b.nodes.values():
            tb[n.node_type] = tb.get(n.node_type, 0) + 1
        return self._cosine(ta, tb)

    def _edge_type_sim(self, a: ControlFlowGraph, b: ControlFlowGraph) -> float:
        ta: Dict[str, int] = {}
        tb: Dict[str, int] = {}
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
        va, vb = a.variables, b.variables
        if not va and not vb:
            return 1.0
        if not va or not vb:
            return 0.0
        return len(va & vb) / len(va | vb)

    def _dep_pattern_sim(self, a: DataFlowGraph, b: DataFlowGraph) -> float:
        if a.edge_count == 0 and b.edge_count == 0:
            return 1.0
        if a.edge_count == 0 or b.edge_count == 0:
            return 0.0
        da: Dict[int, int] = {}
        db: Dict[int, int] = {}
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

    def _chain_lengths(self, dfg: DataFlowGraph) -> List[int]:
        groups: Dict[str, int] = {}
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

    def _bigrams(self, nodes: List[CFGNode]) -> Dict[str, int]:
        result: Dict[str, int] = {}
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

    def _patterns(self, g: CombinedGraph) -> Set[str]:
        p: Set[str] = set()
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

    def _common_patterns(self, a: CombinedGraph, b: CombinedGraph) -> List[str]:
        return list(self._patterns(a) & self._patterns(b))

    def _differences(self, a: CombinedGraph, b: CombinedGraph) -> List[str]:
        diffs: List[str] = []
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
    def _cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
        keys = set(a) | set(b)
        if not keys:
            return 1.0
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        na = math.sqrt(sum(v ** 2 for v in a.values()))
        nb = math.sqrt(sum(v ** 2 for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def _dist_sim(a: List[int], b: List[int]) -> float:
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