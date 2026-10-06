"""
Data models for Control Flow Graph (CFG) and Data Flow Graph (DFG).
"""

import ast
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EdgeType(Enum):
    """Types of edges in the Control Flow Graph."""

    SEQUENTIAL = "sequential"  # Normal flow to next statement
    TRUE_BRANCH = "true_branch"  # Conditional branch when condition is True
    FALSE_BRANCH = "false_branch"  # Conditional branch when condition is False
    LOOP_BACK = "loop_back"  # Back edge in loops
    LOOP_EXIT = "loop_exit"  # Exit edge from loops
    BREAK = "break"  # Break statement
    CONTINUE = "continue"  # Continue statement
    RETURN = "return"  # Return statement
    EXCEPTION = "exception"  # Exception flow
    FUNCTION_CALL = "function_call"  # Function call edge
    FUNCTION_RETURN = "function_return"  # Function return edge


class VariableState(Enum):
    """State of a variable at a program point."""

    DEFINED = "defined"  # Variable is assigned
    USED = "used"  # Variable is read
    MODIFIED = "modified"  # Variable is modified (e.g., +=)
    KILLED = "killed"  # Variable is no longer live


@dataclass
class CFGNode:
    """A node in the Control Flow Graph representing a program statement or expression.

    Attributes:
        id: Unique identifier for this node
        ast_node: The original AST node this represents
        node_type: Type of AST node (e.g., 'Assign', 'If', 'For')
        source_code: Source code string for this node
        line_start: Starting line number in source
        line_end: Ending line number in source (header only for compound statements)
        successors: List of (node_id, edge_type) tuples
        predecessors: List of (node_id, edge_type) tuples
        scope: Lexical scope identifier (qualified, e.g. ``Class.method``)
        metadata: Additional metadata
        dominated_nodes: After ``compute_dominators``: the set of nodes that
            *dominate* this node (the name is historical and misleading).
        post_dominated_nodes: Likewise for post-dominators.
    """

    id: int
    ast_node: ast.AST | None = None
    node_type: str = ""
    source_code: str = ""
    line_start: int = 0
    line_end: int = 0
    successors: list[tuple[int, EdgeType]] = field(default_factory=list)
    predecessors: list[tuple[int, EdgeType]] = field(default_factory=list)
    scope: str = "global"
    metadata: dict[str, Any] = field(default_factory=dict)

    # Computed fields for analysis
    dominated_nodes: set[int] = field(default_factory=set, init=False)
    post_dominated_nodes: set[int] = field(default_factory=set, init=False)

    def __repr__(self) -> str:
        return f"CFGNode({self.id}: {self.node_type} at line {self.line_start})"

    def add_successor(
        self, node_id: int, edge_type: EdgeType = EdgeType.SEQUENTIAL
    ) -> None:
        """Add a successor edge (deduplicated on (target, type))."""
        if (node_id, edge_type) not in self.successors:
            self.successors.append((node_id, edge_type))

    def add_predecessor(
        self, node_id: int, edge_type: EdgeType = EdgeType.SEQUENTIAL
    ) -> None:
        """Add a predecessor edge (deduplicated on (source, type))."""
        if (node_id, edge_type) not in self.predecessors:
            self.predecessors.append((node_id, edge_type))

    def get_successor_ids(self, edge_type: EdgeType | None = None) -> list[int]:
        """Get IDs of successor nodes, optionally filtered by edge type."""
        if edge_type is None:
            return [s[0] for s in self.successors]
        return [s[0] for s in self.successors if s[1] == edge_type]

    def get_predecessor_ids(self, edge_type: EdgeType | None = None) -> list[int]:
        """Get IDs of predecessor nodes, optionally filtered by edge type."""
        if edge_type is None:
            return [p[0] for p in self.predecessors]
        return [p[0] for p in self.predecessors if p[1] == edge_type]


@dataclass
class CFGEdge:
    """An edge in the Control Flow Graph."""

    source: int
    target: int
    edge_type: EdgeType = EdgeType.SEQUENTIAL
    condition: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"CFGEdge({self.source} -> {self.target}: {self.edge_type.value})"


@dataclass
class ControlFlowGraph:
    """A Control Flow Graph representing the execution flow of a program.

    Attributes:
        nodes: Dictionary mapping node ID to CFGNode
        edges: List of CFGEdge objects (no exact duplicates)
        entry_node: Entry point node ID
        exit_node: Exit point node ID
        source_code: Original source code
        ast_tree: Original AST tree
        scopes: Dictionary mapping scope name to list of node IDs in that scope
    """

    nodes: dict[int, CFGNode] = field(default_factory=dict)
    edges: list[CFGEdge] = field(default_factory=list)
    entry_node: int | None = None
    exit_node: int | None = None
    source_code: str = ""
    ast_tree: ast.Module | None = None
    scopes: dict[str, list[int]] = field(default_factory=dict)
    _edge_keys: set[tuple[int, int, EdgeType]] = field(
        default_factory=set, init=False, repr=False
    )

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def add_node(self, node: CFGNode) -> None:
        """Add a node to the graph.

        Raises:
            ValueError: If a node with the same ID already exists. (A silent
                overwrite used to corrupt the graph when a builder reset its
                ID counter mid-build.)
        """
        if node.id in self.nodes:
            raise ValueError(f"Duplicate CFG node id {node.id}")
        self.nodes[node.id] = node
        self.scopes.setdefault(node.scope, []).append(node.id)

    def add_edge(self, edge: CFGEdge) -> None:
        """Add an edge and update successor/predecessor lists.

        Exact duplicates (same source, target, type) are ignored, so
        ``edges`` and the per-node lists always agree.

        Raises:
            ValueError: If either endpoint is not in the graph.
        """
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError(
                f"Edge {edge.source}->{edge.target} references an unknown node"
            )
        key = (edge.source, edge.target, edge.edge_type)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(edge)
        self.nodes[edge.source].add_successor(edge.target, edge.edge_type)
        self.nodes[edge.target].add_predecessor(edge.source, edge.edge_type)

    def get_edge(self, source: int, target: int) -> CFGEdge | None:
        """Get the first edge between two nodes."""
        for edge in self.edges:
            if edge.source == source and edge.target == target:
                return edge
        return None

    def get_edges(self, source: int, target: int | None = None) -> list[CFGEdge]:
        """Get all edges from a source node, optionally to a specific target."""
        return [
            e
            for e in self.edges
            if e.source == source and (target is None or e.target == target)
        ]

    def get_nodes_in_scope(self, scope: str) -> list[CFGNode]:
        return [
            self.nodes[nid] for nid in self.scopes.get(scope, []) if nid in self.nodes
        ]

    def get_all_scopes(self) -> list[str]:
        return list(self.scopes.keys())

    # ── graph analysis ──────────────────────────────────────────────

    def _reverse_postorder(self, start: int) -> list[int]:
        """Reverse postorder of nodes reachable from ``start`` (iterative DFS)."""
        seen: set[int] = {start}
        order: list[int] = []
        stack: list[tuple[int, int]] = [(start, 0)]
        while stack:
            node_id, idx = stack.pop()
            succs = self.nodes[node_id].get_successor_ids()
            if idx < len(succs):
                stack.append((node_id, idx + 1))
                nxt = succs[idx]
                if nxt not in seen and nxt in self.nodes:
                    seen.add(nxt)
                    stack.append((nxt, 0))
            else:
                order.append(node_id)
        order.reverse()
        return order

    def find_unreachable_nodes(self) -> set[int]:
        """Nodes that cannot be reached from the entry node."""
        if self.entry_node is None or self.entry_node not in self.nodes:
            return set(self.nodes)
        return set(self.nodes) - set(self._reverse_postorder(self.entry_node))

    def compute_dominators(self) -> dict[int, set[int]]:
        """Compute dominator sets for all nodes.

        Unreachable nodes dominate only themselves (previously they kept the
        "all nodes" initial value, and a node whose predecessors were all
        unknown crashed ``set.intersection()``).

        Returns:
            Dictionary mapping node ID to the set of nodes that dominate it.
        """
        if self.entry_node is None or self.entry_node not in self.nodes:
            return {}

        order = self._reverse_postorder(self.entry_node)
        reachable = set(order)
        dom: dict[int, set[int]] = {n: set(reachable) for n in reachable}
        dom[self.entry_node] = {self.entry_node}

        changed = True
        while changed:
            changed = False
            for node_id in order:
                if node_id == self.entry_node:
                    continue
                preds = [
                    p
                    for p in self.nodes[node_id].get_predecessor_ids()
                    if p in reachable
                ]
                new_dom = set.intersection(*(dom[p] for p in preds)) | {node_id}
                if new_dom != dom[node_id]:
                    dom[node_id] = new_dom
                    changed = True

        for node_id in self.nodes:
            dom.setdefault(node_id, {node_id})
            self.nodes[node_id].dominated_nodes = dom[node_id]
        return dom

    def compute_immediate_dominators(self) -> dict[int, int | None]:
        """Immediate dominator of every node (``None`` for entry/unreachable)."""
        dom = self.compute_dominators()
        idom: dict[int, int | None] = {}
        for node_id, dominators in dom.items():
            strict = dominators - {node_id}
            # Dominators form a chain; the closest one has the largest set.
            idom[node_id] = max(strict, key=lambda d: len(dom[d])) if strict else None
        return idom

    def compute_post_dominators(self) -> dict[int, set[int]]:
        """Compute post-dominator sets for all nodes.

        post_dom(n) = {n} ∪ ⋂ post_dom(s) over the *successors* s of n. The old
        code intersected over predecessors (it computed dominators of the
        reversed labelling) and so returned wrong sets. Nodes that cannot reach
        the exit (infinite loops, function bodies hung off a module CFG)
        post-dominate only themselves.
        """
        if self.exit_node is None or self.exit_node not in self.nodes:
            return {}

        # Nodes that can reach the exit: backward BFS.
        can_reach: set[int] = {self.exit_node}
        queue = deque([self.exit_node])
        while queue:
            current = queue.popleft()
            for pred in self.nodes[current].get_predecessor_ids():
                if pred in self.nodes and pred not in can_reach:
                    can_reach.add(pred)
                    queue.append(pred)

        post_dom: dict[int, set[int]] = {n: set(can_reach) for n in can_reach}
        post_dom[self.exit_node] = {self.exit_node}

        changed = True
        while changed:
            changed = False
            for node_id in sorted(can_reach, reverse=True):
                if node_id == self.exit_node:
                    continue
                succs = [
                    s for s in self.nodes[node_id].get_successor_ids() if s in can_reach
                ]
                new_dom = set.intersection(*(post_dom[s] for s in succs)) | {node_id}
                if new_dom != post_dom[node_id]:
                    post_dom[node_id] = new_dom
                    changed = True

        for node_id in self.nodes:
            post_dom.setdefault(node_id, {node_id})
            self.nodes[node_id].post_dominated_nodes = post_dom[node_id]
        return post_dom

    def to_dict(self) -> dict[str, Any]:
        """Convert graph to dictionary representation for serialization."""
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entry_node": self.entry_node,
            "exit_node": self.exit_node,
            "nodes": {
                nid: {
                    "id": n.id,
                    "node_type": n.node_type,
                    "source_code": n.source_code[:100] if n.source_code else "",
                    "line_start": n.line_start,
                    "line_end": n.line_end,
                    "scope": n.scope,
                    "successors": [(s, e.value) for s, e in n.successors],
                    "predecessors": [(p, e.value) for p, e in n.predecessors],
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.edge_type.value,
                    "condition": e.condition,
                }
                for e in self.edges
            ],
            "scopes": {name: list(ids) for name, ids in self.scopes.items()},
        }


# ─────────────────────────────────────────────
# Data Flow Graph Models
# ─────────────────────────────────────────────


@dataclass
class DFNode:
    """A node in the Data Flow Graph representing a variable definition or use.

    ``metadata["owner"]`` (set by the builder) names the scope that owns the
    variable binding; it can differ from ``scope`` for globals, closures and
    comprehension variables. Reaching definitions are computed per
    (owner, variable) so a local never kills a same-named variable elsewhere.
    """

    id: int
    variable_name: str
    state: VariableState = VariableState.DEFINED
    cfg_node_id: int = 0
    line_number: int = 0
    source_code: str = ""
    scope: str = "global"
    reaching_definitions: set[int] = field(default_factory=set, init=False)
    live_out: set[str] = field(default_factory=set, init=False)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"DFNode({self.id}: {self.variable_name} [{self.state.value}] "
            f"at line {self.line_number})"
        )

    @property
    def key(self) -> tuple[str, str]:
        """(owner scope, variable name) identity used by flow analysis."""
        return (self.metadata.get("owner", self.scope), self.variable_name)


@dataclass
class DFEdge:
    """An edge in the Data Flow Graph (definition -> use)."""

    source: int
    target: int
    variable: str
    edge_type: str = "data_dependency"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"DFEdge({self.source} --{self.variable}--> {self.target})"


_State = dict[tuple[str, str], frozenset[int]]


def _merge_states(states: Iterable[_State]) -> _State:
    merged: _State = {}
    for state in states:
        for key, defs in state.items():
            merged[key] = merged[key] | defs if key in merged else defs
    return merged


@dataclass
class DataFlowGraph:
    """A Data Flow Graph representing data dependencies in a program."""

    nodes: dict[int, DFNode] = field(default_factory=dict)
    edges: list[DFEdge] = field(default_factory=list)
    variable_definitions: dict[str, set[int]] = field(default_factory=dict)
    variable_uses: dict[str, set[int]] = field(default_factory=dict)
    cfg_reference: ControlFlowGraph | None = None
    source_code: str = ""

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def variables(self) -> set[str]:
        """All variables tracked in the data flow graph."""
        return set(self.variable_definitions) | set(self.variable_uses)

    def add_node(self, node: DFNode) -> None:
        """Add a node; MODIFIED nodes count as both a definition and a use.

        Raises:
            ValueError: If the ID is already present.
        """
        if node.id in self.nodes:
            raise ValueError(f"Duplicate DFG node id {node.id}")
        self.nodes[node.id] = node
        if node.state in (VariableState.DEFINED, VariableState.MODIFIED):
            self.variable_definitions.setdefault(node.variable_name, set()).add(node.id)
        if node.state in (VariableState.USED, VariableState.MODIFIED):
            self.variable_uses.setdefault(node.variable_name, set()).add(node.id)

    def add_edge(self, edge: DFEdge) -> None:
        self.edges.append(edge)

    def get_definition_chains(self, variable: str) -> list[list[int]]:
        """For each definition of ``variable``: the def followed by every node
        reachable from it along that variable's edges (BFS order, no repeats).
        """
        if variable not in self.variable_definitions:
            return []

        adjacency: dict[int, list[int]] = {}
        for edge in self.edges:  # built once, not rescanned per BFS step
            if edge.variable == variable:
                adjacency.setdefault(edge.source, []).append(edge.target)

        chains = []
        for def_id in sorted(self.variable_definitions[variable]):
            chain = [def_id]
            visited = {def_id}
            queue = deque([def_id])
            while queue:
                current = queue.popleft()
                for target in adjacency.get(current, ()):
                    if target not in visited:
                        visited.add(target)
                        chain.append(target)
                        queue.append(target)
            if len(chain) > 1:
                chains.append(chain)
        return chains

    def compute_reaching_definitions(self) -> dict[int, set[int]]:
        """Classic forward may-analysis over the CFG.

        State is kept per (owner scope, variable). A DEFINED/MODIFIED node
        kills all earlier definitions of its variable. Several DF nodes may
        share one CFG node; they are applied in ID order (= evaluation order).

        The previous implementation mixed CFG IDs and DF-node IDs in the same
        dictionary, ignored MODIFIED nodes, tracked all variables in one set,
        and gave up after 100 iterations.

        Returns:
            DF node ID -> reaching definition IDs. For USED/MODIFIED nodes
            these are the definitions that reach the read; a DEFINED node maps
            to ``{itself}``.
        """
        cfg = self.cfg_reference
        if cfg is None or cfg.entry_node is None:
            return {}

        by_cfg: dict[int, list[DFNode]] = {}
        for node in sorted(self.nodes.values(), key=lambda n: n.id):
            by_cfg.setdefault(node.cfg_node_id, []).append(node)

        defining = (VariableState.DEFINED, VariableState.MODIFIED)
        in_state: dict[int, _State] = {cid: {} for cid in cfg.nodes}
        out_state: dict[int, _State] = {cid: {} for cid in cfg.nodes}

        worklist = deque(sorted(cfg.nodes))
        queued = set(worklist)
        while worklist:
            cid = worklist.popleft()
            queued.discard(cid)
            cfg_node = cfg.nodes[cid]
            new_in = _merge_states(out_state[p] for p in cfg_node.get_predecessor_ids())
            in_state[cid] = new_in
            new_out = dict(new_in)
            for df_node in by_cfg.get(cid, ()):
                if df_node.state in defining:
                    new_out[df_node.key] = frozenset((df_node.id,))
            if new_out != out_state[cid]:
                out_state[cid] = new_out
                for succ in cfg_node.get_successor_ids():
                    if succ not in queued:
                        queued.add(succ)
                        worklist.append(succ)

        result: dict[int, set[int]] = {}
        for cid, df_nodes in by_cfg.items():
            current: _State = dict(in_state.get(cid, {}))
            for df_node in df_nodes:
                key = df_node.key
                if df_node.state is VariableState.DEFINED:
                    reach = {df_node.id}
                    current[key] = frozenset((df_node.id,))
                elif df_node.state is VariableState.MODIFIED:
                    reach = set(current.get(key, ()))
                    current[key] = frozenset((df_node.id,))
                else:
                    reach = set(current.get(key, ()))
                result[df_node.id] = reach
                df_node.reaching_definitions = reach
        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert graph to dictionary representation (deterministic order)."""
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "variables": sorted(self.variables),
            "nodes": {
                nid: {
                    "id": n.id,
                    "variable": n.variable_name,
                    "state": n.state.value,
                    "cfg_node_id": n.cfg_node_id,
                    "line_number": n.line_number,
                    "source_code": n.source_code[:100] if n.source_code else "",
                    "scope": n.scope,
                    "reaching_definitions": sorted(n.reaching_definitions),
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "variable": e.variable,
                    "type": e.edge_type,
                }
                for e in self.edges
            ],
        }


# ─────────────────────────────────────────────
# Combined CFG + DFG Model
# ─────────────────────────────────────────────


@dataclass
class CombinedGraph:
    """Combined Control Flow Graph and Data Flow Graph."""

    cfg: ControlFlowGraph = field(default_factory=ControlFlowGraph)
    dfg: DataFlowGraph = field(default_factory=DataFlowGraph)
    source_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"CombinedGraph(cfg_nodes={self.cfg.node_count}, "
            f"cfg_edges={self.cfg.edge_count}, "
            f"dfg_nodes={self.dfg.node_count}, "
            f"dfg_edges={self.dfg.edge_count})"
        )

    def get_node_mapping(self) -> dict[int, list[int]]:
        """Mapping from CFG node IDs to DFG node IDs."""
        mapping: dict[int, list[int]] = {}
        for df_node_id, df_node in self.dfg.nodes.items():
            mapping.setdefault(df_node.cfg_node_id, []).append(df_node_id)
        return mapping

    def compute_graph_edit_distance(self, other: "CombinedGraph") -> float:
        """Count-based distance heuristic (NOT a true graph edit distance).

        0 means identical counts and variable sets; use a graph kernel or real
        GED for structural comparison.
        """
        cfg_dist = abs(self.cfg.node_count - other.cfg.node_count) + abs(
            self.cfg.edge_count - other.cfg.edge_count
        )
        dfg_dist = abs(self.dfg.node_count - other.dfg.node_count) + abs(
            self.dfg.edge_count - other.dfg.edge_count
        )
        var_dist = len(
            set(self.dfg.variables).symmetric_difference(other.dfg.variables)
        )
        return cfg_dist + dfg_dist + var_dist

    def to_dict(self) -> dict[str, Any]:
        return {
            "cfg": self.cfg.to_dict(),
            "dfg": self.dfg.to_dict(),
            "metadata": self.metadata,
        }
