"""
Combined CFG + DFG Builder for Python AST.

This module provides a unified builder that constructs both the Control Flow
Graph and the Data Flow Graph from a Python AST (CFG first, then the DFG on top
of it), ensuring proper correspondence between the two graphs.
"""

import ast
from collections import deque
from collections.abc import Iterator

from .cfg_builder import ControlFlowGraphBuilder
from .dfg_builder import DataFlowGraphBuilder
from .models import (
    CombinedGraph,
    ControlFlowGraph,
    EdgeType,
)

_FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _iter_definitions(node: ast.AST, prefix: str = "") -> Iterator[tuple[str, ast.AST]]:
    """Yield (qualified name, node) for every function/class, in source order."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (*_FUNCTION_TYPES, ast.ClassDef)):
            qualified = f"{prefix}{child.name}"
            yield qualified, child
            yield from _iter_definitions(child, f"{qualified}.")
        else:
            yield from _iter_definitions(child, prefix)


def _find_definition(
    tree: ast.AST, name: str, node_types: tuple[type, ...]
) -> ast.AST | None:
    """Find a function/class by bare (``method``) or qualified (``Class.method``) name.

    Several definitions can share a bare name (e.g. ``__init__``); the shallowest
    match wins, then source order.
    """
    matches = [
        (qualified, node)
        for qualified, node in _iter_definitions(tree)
        if isinstance(node, node_types)
        and (qualified == name or qualified.rsplit(".", 1)[-1] == name)
    ]
    if not matches:
        return None
    exact = [m for m in matches if m[0] == name]
    pool = exact or matches
    return min(pool, key=lambda m: m[0].count("."))[1]


class CFGDFGBuilder:
    """Unified builder that constructs both CFG and DFG from Python AST.

    Creates a CombinedGraph containing:
    - A Control Flow Graph representing execution paths
    - A Data Flow Graph representing variable dependencies
    - Cross-references between CFG nodes and DFG nodes

    Each ``build*`` call uses fresh sub-builders, so one instance can be shared
    across threads.

    Usage:
        builder = CFGDFGBuilder()
        combined = builder.build(source_code)
    """

    def build(self, source_code: str) -> CombinedGraph:
        """Build combined CFG + DFG from source code.

        Raises:
            SyntaxError: If source code cannot be parsed
        """
        tree = ast.parse(source_code)
        return self.build_from_ast(tree, source_code)

    def build_from_ast(self, tree: ast.Module, source_code: str = "") -> CombinedGraph:
        """Build combined CFG + DFG from an AST."""
        cfg = ControlFlowGraphBuilder().build(tree, source_code)
        dfg = DataFlowGraphBuilder().build(tree, cfg, source_code)
        return CombinedGraph(
            cfg=cfg,
            dfg=dfg,
            source_code=source_code,
            metadata={
                "language": "python",
                "ast_nodes": sum(1 for _ in ast.walk(tree)),
            },
        )

    def build_for_function(
        self,
        source_code: str,
        function_name: str,
    ) -> CombinedGraph | None:
        """Build combined CFG + DFG for a specific function.

        ``function_name`` may be qualified (``Class.method``) to disambiguate.
        Returns None if no such function exists.
        """
        tree = ast.parse(source_code)
        node = _find_definition(tree, function_name, _FUNCTION_TYPES)
        if node is None:
            return None

        cfg = ControlFlowGraphBuilder().build_from_function(node, source_code)  # type: ignore[arg-type]
        dfg = DataFlowGraphBuilder().build_for_function(node, cfg, source_code)  # type: ignore[arg-type]
        return CombinedGraph(
            cfg=cfg,
            dfg=dfg,
            source_code=source_code,
            metadata={"language": "python", "function_name": function_name},
        )

    def build_for_class(
        self,
        source_code: str,
        class_name: str,
    ) -> CombinedGraph | None:
        """Build combined CFG + DFG for a specific class (None if not found).

        The DFG is now built from the class body. It used to be built from the
        whole module while the CFG covered only the class, so the two graphs
        described different code.
        """
        tree = ast.parse(source_code)
        node = _find_definition(tree, class_name, (ast.ClassDef,))
        if node is None:
            return None

        cfg = ControlFlowGraphBuilder().build_from_class(node, source_code)  # type: ignore[arg-type]
        dfg = DataFlowGraphBuilder().build_for_class(node, cfg, source_code)  # type: ignore[arg-type]
        return CombinedGraph(
            cfg=cfg,
            dfg=dfg,
            source_code=source_code,
            metadata={"language": "python", "class_name": class_name},
        )


def build_combined(source_code: str) -> CombinedGraph:
    """Convenience function to build combined CFG + DFG from source code.

    Raises:
        SyntaxError: If source code cannot be parsed
    """
    return CFGDFGBuilder().build(source_code)


def build_combined_for_function(
    source_code: str,
    function_name: str,
) -> CombinedGraph | None:
    """Convenience function to build combined CFG + DFG for a function."""
    return CFGDFGBuilder().build_for_function(source_code, function_name)


# ─────────────────────────────────────────────
# Graph Analysis Utilities
# ─────────────────────────────────────────────


def compute_cyclomatic_complexity(
    cfg: ControlFlowGraph, scope: str | None = None
) -> int:
    """Cyclomatic complexity as 1 + the number of extra branches.

    Equivalent to E - N + 2 for a single-entry/single-exit graph, but robust to
    several sinks (function bodies hang off a module CFG, ``raise`` exits, ...)
    where E - N + 2P gave wrong values. FUNCTION_CALL edges are not decisions.

    Args:
        cfg: Control Flow Graph
        scope: Restrict to one scope's nodes (e.g. ``"Class.method"``) to get
            per-function complexity; ``None`` measures the whole graph.
    """
    ids = set(cfg.nodes) if scope is None else set(cfg.scopes.get(scope, ()))
    extra = 0
    for node_id in ids:
        targets = {
            target
            for target, edge_type in cfg.nodes[node_id].successors
            if edge_type is not EdgeType.FUNCTION_CALL and target in ids
        }
        extra += max(0, len(targets) - 1)
    return 1 + extra


def find_reachable_nodes(cfg: ControlFlowGraph, start: int) -> set[int]:
    """All nodes reachable from ``start`` (empty if ``start`` is not in the graph)."""
    if start not in cfg.nodes:
        return set()
    visited: set[int] = {start}
    queue = deque([start])  # deque: list.pop(0) made this quadratic
    while queue:
        current = queue.popleft()
        for successor_id in cfg.nodes[current].get_successor_ids():
            if successor_id not in visited and successor_id in cfg.nodes:
                visited.add(successor_id)
                queue.append(successor_id)
    return visited


def find_dominance_frontier(cfg: ControlFlowGraph) -> dict[int, set[int]]:
    """Dominance frontiers for all nodes (Cooper-Harvey-Kennedy).

    DF(n) = nodes m such that n dominates a predecessor of m but does not
    strictly dominate m. The previous loop condition was a mangled conditional
    expression that also called ``.pop()`` on the real dominator sets, silently
    corrupting them.
    """
    idom = cfg.compute_immediate_dominators()
    reachable = {n for n, d in idom.items() if d is not None or n == cfg.entry_node}
    frontier: dict[int, set[int]] = {n: set() for n in cfg.nodes}

    for node_id in reachable:
        preds = [p for p in cfg.nodes[node_id].get_predecessor_ids() if p in reachable]
        if len(preds) < 2:
            continue
        for pred in preds:
            runner: int | None = pred
            while runner is not None and runner != idom[node_id]:
                frontier[runner].add(node_id)
                runner = idom[runner]
    return frontier


def extract_variable_dependencies(
    combined: CombinedGraph,
) -> dict[str, list[tuple[int, int]]]:
    """Variable name -> list of (def_id, use_id) pairs."""
    deps: dict[str, list[tuple[int, int]]] = {}
    for edge in combined.dfg.edges:
        deps.setdefault(edge.variable, []).append((edge.source, edge.target))
    return deps


def compute_code_metrics(combined: CombinedGraph) -> dict[str, float]:
    """Compute various code metrics from the combined graph."""
    cfg = combined.cfg
    dfg = combined.dfg
    return {
        "cyclomatic_complexity": compute_cyclomatic_complexity(cfg),
        "cfg_nodes": cfg.node_count,
        "cfg_edges": cfg.edge_count,
        "dfg_nodes": dfg.node_count,
        "dfg_edges": dfg.edge_count,
        "num_variables": len(dfg.variables),
        "num_scopes": len(cfg.get_all_scopes()),
        "avg_defs_per_variable": (
            sum(len(defs) for defs in dfg.variable_definitions.values())
            / max(1, len(dfg.variable_definitions))
        ),
        # Size (in CFG nodes) of the largest scope.
        "max_variable_scope_size": max(
            (len(nodes) for nodes in cfg.scopes.values()), default=0
        ),
    }


def serialize_graph(combined: CombinedGraph) -> dict:
    """Serialize combined graph to a JSON-serializable dictionary."""
    return combined.to_dict()
