"""
Graph-based Intermediate Representation.

Provides graph-based representation of code structure and dependencies.
"""

import ast as python_ast
from dataclasses import dataclass, field, replace
from typing import Any

from .base_ir import BaseIR, IRMetadata, normalize_language


@dataclass
class GraphNode:
    """Represents a node in the code graph.

    Attributes:
        node_id: Unique identifier for the node
        node_type: Type of node (e.g., 'function', 'class', 'variable', 'statement')
        label: Human-readable label for the node
        properties: Additional properties (e.g., line number, complexity)
    """

    node_id: str
    node_type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphNode":
        return cls(
            node_id=data["node_id"],
            node_type=data["node_type"],
            label=data["label"],
            properties=data.get("properties", {}),
        )

    def __repr__(self) -> str:
        return f"GraphNode({self.node_id}, {self.node_type}, '{self.label}')"

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GraphNode):
            return False
        return self.node_id == other.node_id


@dataclass
class GraphEdge:
    """Represents an edge in the code graph.

    Attributes:
        source_id: ID of the source node
        target_id: ID of the target node
        edge_type: Type of relationship (e.g., 'calls', 'contains', 'uses', 'defines')
        weight: Edge weight (for 'calls' edges: the number of call sites)
        properties: Additional properties
    """

    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphEdge":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_type=data["edge_type"],
            weight=data.get("weight", 1.0),
            properties=data.get("properties", {}),
        )

    def __repr__(self) -> str:
        return f"GraphEdge({self.source_id} --{self.edge_type}--> {self.target_id})"

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.edge_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GraphEdge):
            return False
        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.edge_type == other.edge_type
        )


# ── call-graph construction (shared by all languages) ───────────────────────

MODULE_ID = "module:<top>"


@dataclass
class _Def:
    qual: str  # qualified name, e.g. "Outer.method"
    kind: str  # "class" | "function" | "method"
    node_id: str
    line: int
    parent: str  # qualified name of the enclosing definition ("" = module)
    extra: dict[str, Any] = field(default_factory=dict)


class _GraphBuilder:
    """Collects definitions and call sites, then resolves calls by scope.

    The old builders walked the AST breadth-first with two "current class /
    current function" variables that were never scoped or reset: every
    function after the first class was "contained" by it, and every call was
    attributed to whichever function BFS visited last. Methods with the same
    name in different classes also produced duplicate node IDs, which made
    ``validate()`` fail.
    """

    def __init__(self, language: str):
        self.language = language
        self.defs: dict[str, _Def] = {}
        # (caller qualified name or "" for module level, callee, qualifier, count)
        self.calls: list[tuple[str, str, str | None]] = []

    # python/js: nested named functions are visible to inner code, class bodies
    # are not; java: members of enclosing classes are visible.
    @property
    def _class_scope_visible(self) -> bool:
        return self.language == "java"

    def add_def(
        self, qual: str, kind: str, line: int, parent: str, **extra: Any
    ) -> None:
        if qual in self.defs:  # redefinition / overload: keep the first, merge calls
            return
        prefix = {"class": "class", "function": "func", "method": "method"}[kind]
        self.defs[qual] = _Def(qual, kind, f"{prefix}:{qual}", line, parent, extra)

    def add_call(self, caller: str, name: str, qualifier: str | None) -> None:
        self.calls.append((caller, name, qualifier))

    # ── resolution ──────────────────────────────────────────────────

    def _chain(self, caller: str) -> list[str]:
        """caller, its parent, ... up to the module ("")."""
        chain = []
        current = caller
        while current:
            chain.append(current)
            current = self.defs[current].parent if current in self.defs else ""
        chain.append("")
        return chain

    def _enclosing_class(self, caller: str) -> str | None:
        for q in self._chain(caller):
            if q in self.defs and self.defs[q].kind == "class":
                return q
        return None

    def resolve(self, caller: str, name: str, qualifier: str | None) -> str | None:
        """Qualified name of the definition a call refers to (None = unknown)."""
        if qualifier is None:  # plain call: foo(...) / new Foo(...)
            for scope in self._chain(caller):
                if scope == "":
                    candidate = name
                else:
                    scope_def = self.defs.get(scope)
                    if scope_def is None:
                        continue
                    if scope_def.kind == "class" and not (
                        self._class_scope_visible or scope == caller
                    ):
                        continue
                    candidate = f"{scope}.{name}"
                if candidate in self.defs:
                    return candidate
            return None

        if qualifier in ("self", "cls", "this"):
            owner = self._enclosing_class(caller)
            if owner and f"{owner}.{name}" in self.defs:
                return f"{owner}.{name}"
            return None

        if qualifier != "?":  # ClassName.method(...)
            target_class = self.resolve(caller, qualifier, None)
            if target_class and f"{target_class}.{name}" in self.defs:
                return f"{target_class}.{name}"

        # obj.method(...): link only if exactly one method has that name
        matches = [
            q
            for q, d in self.defs.items()
            if d.kind != "class" and q.rsplit(".", 1)[-1] == name and "." in q
        ]
        return matches[0] if len(matches) == 1 else None

    # ── assembly ────────────────────────────────────────────────────

    def build(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        node_ids: set[str] = set()

        def add_node(node: GraphNode) -> None:
            if node.node_id not in node_ids:
                node_ids.add(node.node_id)
                nodes.append(node)

        for d in self.defs.values():
            ntype = {"class": "class", "function": "function", "method": "method"}[
                d.kind
            ]
            props = {"line": d.line, **d.extra}
            add_node(GraphNode(d.node_id, ntype, d.qual.rsplit(".", 1)[-1], props))

        for d in self.defs.values():  # containment
            if d.parent and d.parent in self.defs:
                edges.append(
                    GraphEdge(self.defs[d.parent].node_id, d.node_id, "contains")
                )

        call_edges: dict[tuple[str, str], GraphEdge] = {}
        for caller, name, qualifier in self.calls:
            target = self.resolve(caller, name, qualifier)
            if target is not None:
                target_id = self.defs[target].node_id
            elif qualifier is None:
                if name == "":
                    continue
                kind = "method" if self.language == "java" else "function"
                prefix = "method" if kind == "method" else "func"
                target_id = f"{prefix}:{name}"
                add_node(GraphNode(target_id, kind, name, {"external": True}))
            else:
                continue  # unresolved obj.method(): too noisy to model

            if caller:
                source_id = self.defs[caller].node_id
            else:
                source_id = MODULE_ID
                add_node(GraphNode(MODULE_ID, "module", "<module>", {}))
            key = (source_id, target_id)
            if key in call_edges:
                call_edges[key].weight += 1
            else:
                call_edges[key] = GraphEdge(source_id, target_id, "calls", 1.0)
        edges.extend(call_edges.values())
        return nodes, edges


class GraphIR(BaseIR):
    """Graph-based intermediate representation.

    Represents code as a graph with nodes (functions, classes, variables)
    and edges (calls, contains, uses, defines).

    Node IDs from ``from_source`` are scope-qualified: ``class:Outer.Inner``,
    ``func:outer.helper``, ``func:Class.method`` (``method:Class.name`` for
    Java). ``module:<top>`` is the caller of module-level calls; ``external``
    nodes stand for callees not defined in the file. ``calls`` edges are
    de-duplicated, with ``weight`` = number of call sites.
    """

    REPRESENTATION_TYPE = "graph"

    def __init__(
        self, nodes: list[GraphNode], edges: list[GraphEdge], metadata: IRMetadata
    ):
        super().__init__(metadata)
        self._set_graph(nodes, edges)

    def _set_graph(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self.nodes = nodes
        self.edges = edges
        self._node_map: dict[str, GraphNode] = {n.node_id: n for n in nodes}
        self._outgoing: dict[str, list[GraphEdge]] = {}
        self._incoming: dict[str, list[GraphEdge]] = {}
        for edge in edges:
            self._outgoing.setdefault(edge.source_id, []).append(edge)
            self._incoming.setdefault(edge.target_id, []).append(edge)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_types": sorted(self.get_node_types()),  # was set order
            "edge_types": sorted(self.get_edge_types()),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], metadata: IRMetadata | None = None
    ) -> "GraphIR":
        """Deserialize Graph IR from ``to_dict()`` output.

        A payload without ``"nodes"`` yields an empty placeholder IR (the old
        implementation returned that for *every* input and lost the graph).
        """
        meta = cls._resolve_metadata(data, metadata)
        if isinstance(data, dict) and "nodes" in data:
            nodes = [GraphNode.from_dict(n) for n in data["nodes"]]
            edges = [GraphEdge.from_dict(e) for e in data.get("edges", [])]
        else:
            nodes, edges = [], []
        return cls(nodes=nodes, edges=edges, metadata=meta)

    def _load_from_dict(self, data: dict[str, Any]) -> None:
        self._set_graph(
            [GraphNode.from_dict(n) for n in data["nodes"]],
            [GraphEdge.from_dict(e) for e in data["edges"]],
        )

    def validate(self) -> bool:
        """Validate Graph IR integrity."""
        if not self.metadata.validate():
            return False
        if not isinstance(self.nodes, list) or not isinstance(self.edges, list):
            return False

        node_ids = set()
        for node in self.nodes:
            if not isinstance(node, GraphNode):
                return False
            if node.node_id in node_ids:
                return False  # Duplicate node ID
            node_ids.add(node.node_id)

        for edge in self.edges:
            if not isinstance(edge, GraphEdge):
                return False
            if edge.source_id not in node_ids or edge.target_id not in node_ids:
                return False
        return True

    @classmethod
    def from_source(
        cls, source_code: str, language: str, file_path: str | None = None
    ) -> "GraphIR":
        """Create Graph IR from source code.

        Raises:
            ValueError: If language is not supported
        """
        language = normalize_language(language)
        nodes, edges = cls._build_graph(source_code, language)  # fail before hashing
        metadata = cls.create_metadata(source_code, language, "graph", file_path)
        return cls(nodes=nodes, edges=edges, metadata=metadata)

    @staticmethod
    def _build_graph(
        source_code: str, language: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        language = normalize_language(language)
        if language == "python":
            return GraphIR._build_python_graph(source_code)
        if language == "java":
            return GraphIR._build_java_graph(source_code)
        if language == "javascript":
            return GraphIR._build_javascript_graph(source_code)
        raise ValueError(f"Unsupported language: {language}")

    @staticmethod
    def _build_python_graph(
        source_code: str,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Build the definition/call graph of Python source (empty on SyntaxError)."""
        try:
            tree = python_ast.parse(source_code)
        except (SyntaxError, ValueError, RecursionError):
            return [], []

        builder = _GraphBuilder("python")
        defining = (
            python_ast.FunctionDef,
            python_ast.AsyncFunctionDef,
            python_ast.ClassDef,
        )
        # iterative pre-order walk carrying the enclosing definition's name
        stack: list[tuple[python_ast.AST, str]] = [(tree, "")]
        while stack:
            node, scope = stack.pop()
            if isinstance(node, defining):
                qual = f"{scope}.{node.name}" if scope else node.name
                is_class = isinstance(node, python_ast.ClassDef)
                extra = (
                    {}
                    if is_class
                    else (
                        {"async": True}
                        if isinstance(node, python_ast.AsyncFunctionDef)
                        else {}
                    )
                )
                builder.add_def(
                    qual,
                    "class" if is_class else "function",
                    node.lineno,
                    scope,
                    **extra,
                )
                # decorators, defaults, bases run in the enclosing scope
                children: list[tuple[python_ast.AST, str]] = []
                for field_name, value in python_ast.iter_fields(node):
                    inner = field_name == "body"
                    items = value if isinstance(value, list) else [value]
                    for item in items:
                        if isinstance(item, python_ast.AST):
                            children.append((item, qual if inner else scope))
                stack.extend(reversed(children))
                continue
            if isinstance(node, python_ast.Call):
                func = node.func
                if isinstance(func, python_ast.Name):
                    builder.add_call(scope, func.id, None)
                elif isinstance(func, python_ast.Attribute):
                    base = (
                        func.value.id
                        if isinstance(func.value, python_ast.Name)
                        else "?"
                    )
                    builder.add_call(scope, func.attr, base)
            stack.extend(
                (child, scope)
                for child in reversed(list(python_ast.iter_child_nodes(node)))
            )
        return builder.build()

    @staticmethod
    def _build_clike_graph(
        source_code: str, language: str
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        from ._clike import parse_clike

        root = parse_clike(source_code, language)
        builder = _GraphBuilder(language)
        stack: list[tuple[Any, str]] = [(root, "")]
        while stack:
            node, scope = stack.pop()
            inner = scope
            ntype = node.node_type
            if ntype == "Class" and node.value:
                inner = f"{scope}.{node.value}" if scope else node.value
                builder.add_def(inner, "class", node.line_start, scope)
            elif ntype in ("Method", "Function") and node.value:
                inner = f"{scope}.{node.value}" if scope else node.value
                kind = (
                    "method"
                    if (ntype == "Method" or language == "java")
                    else "function"
                )
                builder.add_def(inner, kind, node.line_start, scope)
            # anonymous functions/classes, blocks and control nodes act as part of
            # the enclosing named scope
            for call in node.metadata.get("calls", []):
                qualifier, _, name = call.rpartition(".")
                builder.add_call(inner, name, qualifier or None)
            stack.extend((child, inner) for child in reversed(node.children))
        return builder.build()

    @staticmethod
    def _build_java_graph(source_code: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Definition/call graph of Java (heuristic, brace-aware; see ``_clike``)."""
        return GraphIR._build_clike_graph(source_code, "java")

    @staticmethod
    def _build_javascript_graph(
        source_code: str,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Definition/call graph of JavaScript (heuristic, brace-aware)."""
        return GraphIR._build_clike_graph(source_code, "javascript")

    # ── queries ─────────────────────────────────────────────────────

    def get_node_by_id(self, node_id: str) -> GraphNode | None:
        return self._node_map.get(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        return self._outgoing.get(node_id, [])

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        return self._incoming.get(node_id, [])

    def get_node_types(self) -> set[str]:
        return {node.node_type for node in self.nodes}

    def get_edge_types(self) -> set[str]:
        return {edge.edge_type for edge in self.edges}

    def get_nodes_by_type(self, node_type: str) -> list[GraphNode]:
        return [node for node in self.nodes if node.node_type == node_type]

    def get_edges_by_type(self, edge_type: str) -> list[GraphEdge]:
        return [edge for edge in self.edges if edge.edge_type == edge_type]

    def get_functions(self) -> list[GraphNode]:
        """All function/method nodes."""
        return self.get_nodes_by_type("function") + self.get_nodes_by_type("method")

    def get_classes(self) -> list[GraphNode]:
        return self.get_nodes_by_type("class")

    def get_call_graph(self) -> "GraphIR":
        """New GraphIR containing only call relationships."""
        call_edges = self.get_edges_by_type("calls")
        call_node_ids = set()
        for edge in call_edges:
            call_node_ids.add(edge.source_id)
            call_node_ids.add(edge.target_id)
        call_nodes = [n for n in self.nodes if n.node_id in call_node_ids]
        return GraphIR(
            nodes=call_nodes, edges=call_edges, metadata=replace(self.metadata)
        )

    def get_statistics(self) -> dict[str, Any]:
        node_type_counts: dict[str, int] = {}
        for node in self.nodes:
            node_type_counts[node.node_type] = (
                node_type_counts.get(node.node_type, 0) + 1
            )

        edge_type_counts: dict[str, int] = {}
        for edge in self.edges:
            edge_type_counts[edge.edge_type] = (
                edge_type_counts.get(edge.edge_type, 0) + 1
            )

        total_degree = sum(
            len(self.get_outgoing_edges(n.node_id))
            + len(self.get_incoming_edges(n.node_id))
            for n in self.nodes
        )
        avg_degree = total_degree / len(self.nodes) if self.nodes else 0

        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "unique_node_types": len(self.get_node_types()),
            "unique_edge_types": len(self.get_edge_types()),
            "average_degree": round(avg_degree, 2),
        }

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"GraphIR(nodes={stats['node_count']}, edges={stats['edge_count']}, "
            f"language={self.metadata.language})"
        )

    def __len__(self) -> int:
        return len(self.nodes)
