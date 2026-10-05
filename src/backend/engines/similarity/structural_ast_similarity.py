"""
Structural AST Similarity Algorithm - 基于AST的固实结构比对算法.

Implements comprehensive structural comparison with:
- Weighted Tree Edit Distance with configurable costs
- Control Flow Graph (CFG) structural matching
- Data Flow Graph (DFG) dependency matching
- Subtree Isomorphism Detection
- Tree Kernel Methods (All-Subtree and Subset Tree Kernels)
- Normalized Variable Renaming Resistance

All parameters are configurable for hyperparameter optimization.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from . import _tree_utils as tu
from .base_similarity import BaseSimilarityAlgorithm

#: The pairwise tree kernel is O(N^2) node pairs (each with a recursive child kernel).
#: Above this many nodes in either tree a linear subtree-hash kernel is used instead.
MAX_KERNEL_NODES = 300

# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class ASTStructuralNode:
    """Represents a node in an Abstract Syntax Tree with structural metadata."""

    node_type: str
    value: str = ""
    children: list[ASTStructuralNode] = field(default_factory=list)
    line_number: int = 0
    depth_level: int = 0
    parent: ASTStructuralNode | None = field(default=None, repr=False)

    def __post_init__(self):
        for child in self.children:
            child.parent = self

    def to_tuple(self) -> tuple:
        """Convert to tuple for hashing and comparison (built iteratively)."""
        built: dict[int, tuple] = {}
        for node in tu.postorder(self):
            built[id(node)] = (
                node.node_type,
                node.value,
                tuple(built[id(c)] for c in node.children),
            )
        return built[id(self)]

    def subtree_size(self) -> int:
        """Count total nodes in subtree."""
        return len(tu.preorder(self))

    def tree_depth(self) -> int:
        """Calculate maximum depth of subtree."""
        return tu.max_depth(self)

    def get_all_subtrees(self, min_size: int = 1) -> list[ASTStructuralNode]:
        """Get all subtrees with minimum node count (sizes computed once)."""
        sizes = tu.subtree_sizes(self)
        return [n for n in tu.preorder(self) if sizes[id(n)] >= min_size]

    def subtree_hash(self) -> str:
        """SHA-256 hash of the subtree structure (bottom-up; ``repr`` of a deep
        nested tuple raised RecursionError)."""
        out: dict[int, str] = {}
        for node in tu.postorder(self):
            payload = f"{node.node_type}|{node.value}|" + ",".join(out[id(c)] for c in node.children)
            out[id(node)] = hashlib.sha256(payload.encode()).hexdigest()
        return out[id(self)]

    def normalize_identifiers(self) -> dict[str, str]:
        """Normalize identifier names for renaming resistance."""
        keywords = {
            "if",
            "else",
            "elif",
            "for",
            "while",
            "return",
            "def",
            "class",
            "import",
            "from",
            "try",
            "except",
            "finally",
            "with",
            "as",
            "yield",
            "lambda",
            "pass",
            "break",
            "continue",
            "raise",
            "assert",
            "del",
            "global",
            "nonlocal",
            "in",
            "not",
            "and",
            "or",
            "is",
            "True",
            "False",
            "None",
            "int",
            "float",
            "str",
            "list",
            "dict",
            "set",
            "tuple",
            "bool",
            "self",
            "cls",
        }

        var_map: dict[str, str] = {}
        for node in tu.preorder(self):
            if (
                node.node_type in ("IDENTIFIER", "NAME", "VARIABLE")
                and node.value
                and node.value not in keywords
            ):
                if node.value not in var_map:
                    var_map[node.value] = f"VAR_{len(var_map)}"
                node.value = var_map[node.value]
        return var_map

    def extract_paths(self, max_length: int = 8) -> list[list[str]]:
        """Extract all paths up to max_length in the AST (iterative)."""
        paths: list[list[str]] = []
        stack: list[tuple[ASTStructuralNode, list[str]]] = [(self, [])]
        while stack:
            node, prefix = stack.pop()
            current_path = [*prefix, f"{node.node_type}:{node.value}"]
            if len(current_path) >= max_length or not node.children:
                if len(current_path) >= 2:
                    paths.append(current_path)
            else:
                for child in reversed(node.children):
                    stack.append((child, current_path))
        return paths


@dataclass
class CFGNode:
    """Basic block in Control Flow Graph."""

    block_id: int
    statements: list[str] = field(default_factory=list)
    successors: list[int] = field(default_factory=list)
    predecessors: list[int] = field(default_factory=list)
    block_type: str = "normal"


@dataclass
class ControlFlowGraph:
    """Control Flow Graph representation."""

    nodes: dict[int, CFGNode] = field(default_factory=dict)
    edges: list[tuple[int, int, str]] = field(default_factory=list)
    entry_node: int | None = None

    def add_node(self, node_id: int, block_type: str = "normal") -> CFGNode:
        node = CFGNode(block_id=node_id, block_type=block_type)
        self.nodes[node_id] = node
        return node

    def add_edge(self, from_id: int, to_id: int, edge_type: str = "flow"):
        self.edges.append((from_id, to_id, edge_type))
        if from_id in self.nodes:
            self.nodes[from_id].successors.append(to_id)
        if to_id in self.nodes:
            self.nodes[to_id].predecessors.append(from_id)

    def structural_signature(self) -> str:
        """Generate structural signature for comparison."""
        sorted_edges = sorted(self.edges, key=lambda e: (e[0], e[1]))
        edge_hashes = [f"{s}-{t}-{tp}" for s, t, tp in sorted_edges]
        return hashlib.sha256(";".join(edge_hashes).encode()).hexdigest()

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def cyclomatic_complexity(self) -> int:
        """Calculate cyclomatic complexity."""
        e = self.edge_count()
        n = self.node_count()
        p = 1
        return max(1, e - n + 2 * p)


@dataclass
class DataFlowGraph:
    """Data Flow Graph representation."""

    definitions: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    uses: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    dependencies: list[tuple[str, str]] = field(default_factory=list)

    def add_definition(self, variable: str, location: int):
        self.definitions[variable].append(location)

    def add_use(self, variable: str, location: int):
        self.uses[variable].append(location)

    def add_dependency(self, source: str, target: str):
        self.dependencies.append((source, target))

    def variable_count(self) -> int:
        return len(self.definitions)

    def dependency_count(self) -> int:
        return len(self.dependencies)


# ============================================================================
# Tree Kernel Methods
# ============================================================================


class TreeKernel:
    """
    Tree Kernel methods for AST comparison.
    Implements All-Subtree Tree Kernel and Subset Tree Kernel.
    """

    def __init__(self, kernel_type: str = "subtree", decay_factor: float = 0.5):
        self.kernel_type = kernel_type
        self.decay_factor = decay_factor

    def compute(self, tree_a: ASTStructuralNode, tree_b: ASTStructuralNode) -> float:
        """Compute tree kernel similarity normalized to [0, 1]."""
        sizes_a, sizes_b = tu.subtree_sizes(tree_a), tu.subtree_sizes(tree_b)
        if len(sizes_a) > MAX_KERNEL_NODES or len(sizes_b) > MAX_KERNEL_NODES:
            return self._hashed_kernel(tree_a, tree_b)

        subtrees_a = [n for n in tu.preorder(tree_a) if sizes_a[id(n)] >= 2]
        subtrees_b = [n for n in tu.preorder(tree_b) if sizes_b[id(n)] >= 2]

        if not subtrees_a or not subtrees_b:
            return 0.0

        # Node sizes are looked up, not recomputed inside the double loop.
        sizes = {**sizes_a, **sizes_b}
        k_aa = self._kernel_norm(subtrees_a, subtrees_a, sizes)
        k_bb = self._kernel_norm(subtrees_b, subtrees_b, sizes)
        k_ab = self._kernel_cross(subtrees_a, subtrees_b, sizes)

        denominator = math.sqrt(k_aa * k_bb) if k_aa > 0 and k_bb > 0 else 1.0
        if denominator == 0:
            return 0.0

        return min(1.0, k_ab / denominator)

    @staticmethod
    def _hashed_kernel(tree_a: ASTStructuralNode, tree_b: ASTStructuralNode) -> float:
        """Linear-time subtree kernel for large trees: cosine of the counts of identical
        (type-only) subtrees. The decayed pairwise kernel is quadratic and, for trees of
        a few hundred nodes, its ``decay ** size`` terms underflow to 0 so the result
        collapsed to 0.0 even for identical trees."""

        def counts(root: ASTStructuralNode) -> Counter:
            sizes = tu.subtree_sizes(root)
            hashes = tu.subtree_hashes(root, lambda n: n.node_type)
            return Counter(hashes[i] for i, n in sizes.items() if n >= 2)

        ca, cb = counts(tree_a), counts(tree_b)
        if not ca or not cb:
            return 0.0
        dot = sum(v * cb.get(k, 0) for k, v in ca.items())
        na = math.sqrt(sum(v * v for v in ca.values()))
        nb = math.sqrt(sum(v * v for v in cb.values()))
        return min(1.0, dot / (na * nb)) if na and nb else 0.0

    def _kernel_norm(
        self,
        trees_a: list[ASTStructuralNode],
        trees_b: list[ASTStructuralNode],
        sizes: dict[int, int],
    ) -> float:
        """Compute kernel value K(T_a, T_b)."""
        score = 0.0
        for ta in trees_a:
            for tb in trees_b:
                if self._nodes_match(ta, tb):
                    if self.kernel_type == "subtree":
                        children_score = self._children_kernel(ta.children, tb.children)
                    else:
                        children_score = self._subset_kernel(ta.children, tb.children)
                    score += self.decay_factor ** (sizes[id(ta)] + sizes[id(tb)]) * (1 + children_score)
        return score

    def _kernel_cross(
        self,
        trees_a: list[ASTStructuralNode],
        trees_b: list[ASTStructuralNode],
        sizes: dict[int, int],
    ) -> float:
        """Compute cross kernel K(T_a, T_b)."""
        score = 0.0
        for ta in trees_a:
            for tb in trees_b:
                if self._nodes_match(ta, tb):
                    if self.kernel_type == "subtree":
                        children_score = self._children_kernel(ta.children, tb.children)
                    else:
                        children_score = self._subset_kernel(ta.children, tb.children)
                    score += self.decay_factor ** ((sizes[id(ta)] + sizes[id(tb)]) / 2) * (1 + children_score)
        return score

    def _nodes_match(self, a: ASTStructuralNode, b: ASTStructuralNode) -> bool:
        return a.node_type == b.node_type

    def _children_kernel(
        self, children_a: list[ASTStructuralNode], children_b: list[ASTStructuralNode]
    ) -> float:
        score = 0.0
        for ca in children_a:
            for cb in children_b:
                if self._nodes_match(ca, cb):
                    score += self.decay_factor * (
                        1 + self._children_kernel(ca.children, cb.children)
                    )
        return score

    def _subset_kernel(
        self, children_a: list[ASTStructuralNode], children_b: list[ASTStructuralNode]
    ) -> float:
        if not children_a and not children_b:
            return 1.0
        if not children_a or not children_b:
            return 0.0

        prod = 1.0
        for ca in children_a:
            child_max = 0.0
            for cb in children_b:
                if self._nodes_match(ca, cb):
                    child_max = max(
                        child_max,
                        self.decay_factor
                        * (1 + self._subset_kernel(ca.children, cb.children)),
                    )
            prod *= 1 + child_max
        return prod - 1


# ============================================================================
# Structural Comparison Algorithms
# ============================================================================


class WeightedTreeEditDistance:
    """Weighted Tree Edit Distance algorithm with configurable costs."""

    def __init__(
        self,
        deletion_cost: float = 1.0,
        insertion_cost: float = 1.0,
        relabel_cost: float = 1.0,
        structure_weight: float = 0.5,
    ):
        self.deletion_cost = deletion_cost
        self.insertion_cost = insertion_cost
        self.relabel_cost = relabel_cost
        self.structure_weight = structure_weight

    def compute_similarity(
        self, tree_a: ASTStructuralNode, tree_b: ASTStructuralNode
    ) -> float:
        """Compute similarity using weighted tree edit distance."""
        if tree_a is None or tree_b is None:
            return 0.0

        distance = self._compute_distance(tree_a, tree_b)
        max_possible = max(tree_a.subtree_size(), tree_b.subtree_size()) * max(
            self.deletion_cost, self.insertion_cost, self.relabel_cost
        )

        if max_possible == 0:
            return 1.0

        similarity = 1.0 - (distance / max_possible)
        return max(0.0, min(1.0, similarity))

    def _compute_distance(
        self, tree_a: ASTStructuralNode, tree_b: ASTStructuralNode
    ) -> float:
        forest_a = self._linearize_postorder(tree_a)
        forest_b = self._linearize_postorder(tree_b)
        return self._forest_distance(forest_a, forest_b)

    def _forest_distance(
        self, forest_a: list[ASTStructuralNode], forest_b: list[ASTStructuralNode]
    ) -> float:
        if not forest_a and not forest_b:
            return 0.0
        if not forest_a:
            return len(forest_b) * self.insertion_cost
        if not forest_b:
            return len(forest_a) * self.deletion_cost

        # one bottom-up hash per node (the forest is post-order, so its last node is the
        # root); ``to_tuple()`` per node was quadratic in the tree size
        label = lambda n: f"{n.node_type}|{n.value}"  # noqa: E731
        hashes_a = tu.subtree_hashes(forest_a[-1], label)
        hashes_b = tu.subtree_hashes(forest_b[-1], label)
        set_a = {hashes_a[id(n)] for n in forest_a}
        set_b = {hashes_b[id(n)] for n in forest_b}

        only_a = len(set_a - set_b)
        only_b = len(set_b - set_a)

        cost = only_a * self.deletion_cost + only_b * self.insertion_cost

        avg_depth_a = (
            sum(n.depth_level for n in forest_a) / len(forest_a) if forest_a else 0
        )
        avg_depth_b = (
            sum(n.depth_level for n in forest_b) / len(forest_b) if forest_b else 0
        )
        depth_penalty = abs(avg_depth_a - avg_depth_b) * self.structure_weight

        return cost + depth_penalty

    def _linearize_postorder(self, node: ASTStructuralNode) -> list[ASTStructuralNode]:
        for current, depth in tu.with_depths(node):
            current.depth_level = depth
        return tu.postorder(node)


class CFGComparator:
    """Control Flow Graph structural comparator."""

    def __init__(self, edge_weight: float = 0.6, type_weight: float = 0.4):
        self.edge_weight = edge_weight
        self.type_weight = type_weight

    def compare(self, cfg_a: ControlFlowGraph, cfg_b: ControlFlowGraph) -> float:
        if cfg_a.node_count() == 0 and cfg_b.node_count() == 0:
            return 1.0
        if cfg_a.node_count() == 0 or cfg_b.node_count() == 0:
            return 0.0

        edges_a = {(s, t) for s, t, _ in cfg_a.edges}
        edges_b = {(s, t) for s, t, _ in cfg_b.edges}
        edge_sim = (
            len(edges_a & edges_b) / len(edges_a | edges_b) if edges_a | edges_b else 0
        )

        types_a: dict[str, int] = defaultdict(int)
        types_b: dict[str, int] = defaultdict(int)
        for node in cfg_a.nodes.values():
            types_a[node.block_type] += 1
        for node in cfg_b.nodes.values():
            types_b[node.block_type] += 1

        all_types = set(types_a.keys()) | set(types_b.keys())
        if not all_types:
            type_sim = 1.0
        else:
            max_sum = sum(max(types_a.get(t, 0), types_b.get(t, 0)) for t in all_types)
            if max_sum == 0:
                type_sim = 1.0
            else:
                type_sim = (
                    sum(min(types_a.get(t, 0), types_b.get(t, 0)) for t in all_types)
                    / max_sum
                )

        return self.edge_weight * edge_sim + self.type_weight * type_sim


class DFGComparator:
    """Data Flow Graph structural comparator."""

    def __init__(self, dependency_weight: float = 0.7, variable_weight: float = 0.3):
        self.dependency_weight = dependency_weight
        self.variable_weight = variable_weight

    def compare(self, dfg_a: DataFlowGraph, dfg_b: DataFlowGraph) -> float:
        if dfg_a.variable_count() == 0 and dfg_b.variable_count() == 0:
            return 1.0
        if dfg_a.variable_count() == 0 or dfg_b.variable_count() == 0:
            return 0.0

        vars_a = set(dfg_a.definitions.keys())
        vars_b = set(dfg_b.definitions.keys())
        var_sim = len(vars_a & vars_b) / len(vars_a | vars_b) if vars_a | vars_b else 0

        deps_a = set(dfg_a.dependencies)
        deps_b = set(dfg_b.dependencies)
        dep_sim = len(deps_a & deps_b) / len(deps_a | deps_b) if deps_a | deps_b else 0

        return self.dependency_weight * dep_sim + self.variable_weight * var_sim


# ============================================================================
# Main Structural AST Similarity Algorithm
# ============================================================================


class StructuralASTSimilarity(BaseSimilarityAlgorithm):
    """
    Structural AST Similarity Algorithm with configurable parameters.

    Combines multiple structural analysis techniques:
    - Weighted Tree Edit Distance
    - Tree Kernel Methods
    - Control Flow Graph comparison
    - Data Flow Graph comparison
    - Subtree pattern matching
    - AST path-based similarity
    """

    def __init__(
        self,
        ted_weight: float = 0.25,
        ted_deletion_cost: float = 1.0,
        ted_insertion_cost: float = 1.0,
        ted_relabel_cost: float = 1.0,
        tree_kernel_weight: float = 0.15,
        tree_kernel_type: str = "subtree",
        tree_kernel_decay: float = 0.5,
        cfg_weight: float = 0.15,
        cfg_edge_weight: float = 0.6,
        cfg_type_weight: float = 0.4,
        dfg_weight: float = 0.15,
        dfg_dependency_weight: float = 0.7,
        dfg_variable_weight: float = 0.3,
        pattern_weight: float = 0.15,
        pattern_min_subtree_size: int = 2,
        path_weight: float = 0.10,
        path_max_length: int = 8,
        normalize_identifiers: bool = True,
        similarity_threshold: float = 0.5,
    ):
        super().__init__("structural_ast")

        self.ted_weight = ted_weight
        self.ted_deletion_cost = ted_deletion_cost
        self.ted_insertion_cost = ted_insertion_cost
        self.ted_relabel_cost = ted_relabel_cost
        self.tree_kernel_weight = tree_kernel_weight
        self.tree_kernel_type = tree_kernel_type
        self.tree_kernel_decay = tree_kernel_decay
        self.cfg_weight = cfg_weight
        self.cfg_edge_weight = cfg_edge_weight
        self.cfg_type_weight = cfg_type_weight
        self.dfg_weight = dfg_weight
        self.dfg_dependency_weight = dfg_dependency_weight
        self.dfg_variable_weight = dfg_variable_weight
        self.pattern_weight = pattern_weight
        self.pattern_min_subtree_size = pattern_min_subtree_size
        self.path_weight = path_weight
        self.path_max_length = path_max_length
        self.normalize_identifiers = normalize_identifiers
        self.similarity_threshold = similarity_threshold

        self._init_comparators()

    def _init_comparators(self):
        self.ted_comparator = WeightedTreeEditDistance(
            deletion_cost=self.ted_deletion_cost,
            insertion_cost=self.ted_insertion_cost,
            relabel_cost=self.ted_relabel_cost,
        )
        self.tree_kernel = TreeKernel(
            kernel_type=self.tree_kernel_type, decay_factor=self.tree_kernel_decay
        )
        self.cfg_comparator = CFGComparator(
            edge_weight=self.cfg_edge_weight, type_weight=self.cfg_type_weight
        )
        self.dfg_comparator = DFGComparator(
            dependency_weight=self.dfg_dependency_weight,
            variable_weight=self.dfg_variable_weight,
        )

    def get_params(self) -> dict[str, Any]:
        return {
            "ted_weight": self.ted_weight,
            "ted_deletion_cost": self.ted_deletion_cost,
            "ted_insertion_cost": self.ted_insertion_cost,
            "ted_relabel_cost": self.ted_relabel_cost,
            "tree_kernel_weight": self.tree_kernel_weight,
            "tree_kernel_type": self.tree_kernel_type,
            "tree_kernel_decay": self.tree_kernel_decay,
            "cfg_weight": self.cfg_weight,
            "cfg_edge_weight": self.cfg_edge_weight,
            "cfg_type_weight": self.cfg_type_weight,
            "dfg_weight": self.dfg_weight,
            "dfg_dependency_weight": self.dfg_dependency_weight,
            "dfg_variable_weight": self.dfg_variable_weight,
            "pattern_weight": self.pattern_weight,
            "pattern_min_subtree_size": self.pattern_min_subtree_size,
            "path_weight": self.path_weight,
            "path_max_length": self.path_max_length,
            "normalize_identifiers": self.normalize_identifiers,
            "similarity_threshold": self.similarity_threshold,
        }

    def set_params(self, **params) -> StructuralASTSimilarity:
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self._init_comparators()
        return self

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> float:
        ast_a = self._extract_ast(parsed_a)
        ast_b = self._extract_ast(parsed_b)

        if ast_a is None or ast_b is None:
            return 0.0

        tokens_a, tokens_b = self._graph_tokens(parsed_a), self._graph_tokens(parsed_b)

        if self.normalize_identifiers:
            ast_a.normalize_identifiers()
            ast_b.normalize_identifiers()

        scores: dict[str, tuple[float, float]] = {
            "ted": (self.ted_comparator.compute_similarity(ast_a, ast_b), self.ted_weight),
            "kernel": (self.tree_kernel.compute(ast_a, ast_b), self.tree_kernel_weight),
            "pattern": (self._compute_pattern_similarity(ast_a, ast_b), self.pattern_weight),
            "path": (self._compute_path_similarity(ast_a, ast_b), self.path_weight),
        }
        # CFG / DFG: when NEITHER side has any control-flow edge (or any variable) the
        # comparison has no evidence. Two empty graphs used to score 1.0 ("identical"),
        # adding their whole weight to every pair of simple files.
        cfg_a, cfg_b = self._extract_cfg(parsed_a, tokens_a), self._extract_cfg(parsed_b, tokens_b)
        if cfg_a.edge_count() or cfg_b.edge_count():
            scores["cfg"] = (self.cfg_comparator.compare(cfg_a, cfg_b), self.cfg_weight)
        dfg_a, dfg_b = self._extract_dfg(parsed_a, tokens_a), self._extract_dfg(parsed_b, tokens_b)
        if dfg_a.variable_count() or dfg_b.variable_count():
            scores["dfg"] = (self.dfg_comparator.compare(dfg_a, dfg_b), self.dfg_weight)

        total_weight = sum(w for _, w in scores.values())
        if total_weight == 0:
            return 0.0

        combined = sum(v * w for v, w in scores.values()) / total_weight
        return max(0.0, min(1.0, combined))

    def _graph_tokens(self, parsed: dict[str, Any]) -> list[dict]:
        """Token dicts for the CFG/DFG extractors (raw source is tokenised on demand;
        ``parsed["tokens"]`` alone meant raw-source input produced empty graphs)."""
        tokens = parsed.get("tokens")
        if tokens:
            return [t for t in tokens if isinstance(t, dict)]
        raw = parsed.get("raw")
        if raw:
            from .ast_similarity import tokenize_raw_for_ast

            return tokenize_raw_for_ast(raw, parsed.get("language"))
        return []

    def _extract_ast(self, parsed: dict[str, Any]) -> ASTStructuralNode | None:
        if parsed.get("ast"):
            return self._convert_to_structural_ast(parsed["ast"])
        tokens = self._graph_tokens(parsed)
        if tokens:
            return self._build_ast_from_tokens(tokens)
        return None

    def _convert_to_structural_ast(self, ast_data: Any) -> ASTStructuralNode:
        """Convert nested dict/list AST data to nodes (iterative)."""
        if isinstance(ast_data, dict):
            root = ASTStructuralNode(node_type=ast_data.get("type", "UNKNOWN"), value=ast_data.get("value", ""))
        elif isinstance(ast_data, list):
            root = ASTStructuralNode(node_type="SEQUENCE")
        else:
            return ASTStructuralNode(node_type="LITERAL", value=str(ast_data))

        stack: list[tuple[Any, ASTStructuralNode]] = [(ast_data, root)]
        while stack:
            data, node = stack.pop()
            kids = data if isinstance(data, list) else data.get("children", data.get("body", []))
            for child_data in kids or []:
                if isinstance(child_data, dict):
                    child = ASTStructuralNode(node_type=child_data.get("type", "UNKNOWN"), value=child_data.get("value", ""))
                elif isinstance(child_data, list):
                    child = ASTStructuralNode(node_type="SEQUENCE")
                else:
                    if isinstance(data, list):
                        child = ASTStructuralNode(node_type="LITERAL", value=str(child_data))
                        child.parent = node
                        node.children.append(child)
                    continue
                child.parent = node
                node.children.append(child)
                stack.append((child_data, child))
        return root

    def _build_ast_from_tokens(self, tokens: list[dict]) -> ASTStructuralNode:
        root = ASTStructuralNode(node_type="ROOT")
        current = root
        for token in tokens:
            token_type = token.get("type", "UNKNOWN")
            value = token.get("value", "")
            node = ASTStructuralNode(node_type=token_type, value=value)
            current.children.append(node)
            if token_type in ("KEYWORD", "FUNCTION", "CLASS"):
                current = node
        return root

    def _compute_cfg_similarity(self, parsed_a: dict, parsed_b: dict) -> float:
        cfg_a = self._extract_cfg(parsed_a, self._graph_tokens(parsed_a))
        cfg_b = self._extract_cfg(parsed_b, self._graph_tokens(parsed_b))
        return self.cfg_comparator.compare(cfg_a, cfg_b)

    def _extract_cfg(self, parsed: dict, tokens: list[dict] | None = None) -> ControlFlowGraph:
        cfg = ControlFlowGraph()
        block_id = 0

        if tokens is None:
            tokens = parsed.get("tokens")
        if not tokens:
            cfg.add_node(0, block_type="entry")
            cfg.entry_node = 0
            return cfg

        cfg.add_node(block_id, block_type="entry")
        cfg.entry_node = block_id
        current_block = block_id
        loop_stack: list[int] = []
        cond_stack: list[int] = []

        for token in tokens:
            if token.get("type") != "KEYWORD":
                continue
            kw = token.get("value", "")

            if kw == "if":
                new_block = block_id + 1
                cfg.add_node(new_block, block_type="conditional")
                cfg.add_edge(current_block, new_block, "conditional")
                cond_stack.append(new_block)
                current_block = new_block
                block_id += 1
            elif kw == "else":
                if cond_stack:
                    branch_block = block_id + 1
                    cfg.add_node(branch_block, block_type="alternative")
                    cfg.add_edge(cond_stack[-1], branch_block, "alternative")
                    current_block = branch_block
                    block_id += 1
            elif kw in ("for", "while"):
                loop_block = block_id + 1
                cfg.add_node(loop_block, block_type="loop")
                cfg.add_edge(current_block, loop_block, "loop_entry")
                loop_stack.append(loop_block)
                current_block = loop_block
                block_id += 1
            elif kw == "return":
                ret_block = block_id + 1
                cfg.add_node(ret_block, block_type="return")
                cfg.add_edge(current_block, ret_block, "return")
                block_id += 1
            elif kw == "break":
                if loop_stack:
                    cfg.add_edge(current_block, loop_stack[-1], "break")
            elif kw == "continue":
                if loop_stack:
                    cfg.add_edge(current_block, loop_stack[-1], "continue")

        return cfg

    def _compute_dfg_similarity(self, parsed_a: dict, parsed_b: dict) -> float:
        dfg_a = self._extract_dfg(parsed_a, self._graph_tokens(parsed_a))
        dfg_b = self._extract_dfg(parsed_b, self._graph_tokens(parsed_b))
        return self.dfg_comparator.compare(dfg_a, dfg_b)

    def _extract_dfg(self, parsed: dict, tokens: list[dict] | None = None) -> DataFlowGraph:
        """Variable-sequence data-flow graph.

        Names are replaced by order of first appearance when identifier normalisation is
        on; the AST was normalised but this graph used the raw names, so renaming every
        variable still dropped its similarity to zero.
        """
        dfg = DataFlowGraph()
        if tokens is None:
            tokens = parsed.get("tokens")
        if not tokens:
            return dfg

        canonical: dict[str, str] = {}
        last_var: str | None = None

        for i, token in enumerate(tokens):
            token_type = token.get("type", "")
            value = token.get("value", "")

            if token_type in ("VARIABLE", "NAME", "IDENTIFIER") and value:
                if self.normalize_identifiers:
                    value = canonical.setdefault(value, f"VAR_{len(canonical)}")
                if last_var is not None:
                    dfg.add_dependency(last_var, value)
                last_var = value
                dfg.add_definition(value, i)

        return dfg

    def _compute_pattern_similarity(
        self, ast_a: ASTStructuralNode, ast_b: ASTStructuralNode
    ) -> float:
        subtrees_a = ast_a.get_all_subtrees(min_size=self.pattern_min_subtree_size)
        subtrees_b = ast_b.get_all_subtrees(min_size=self.pattern_min_subtree_size)

        if not subtrees_a and not subtrees_b:
            return 1.0

        hashes_a = {st.subtree_hash() for st in subtrees_a}
        hashes_b = {st.subtree_hash() for st in subtrees_b}

        if not hashes_a and not hashes_b:
            return 1.0

        common = len(hashes_a & hashes_b)
        total = len(hashes_a | hashes_b)
        return common / total if total > 0 else 0.0

    def _compute_path_similarity(
        self, ast_a: ASTStructuralNode, ast_b: ASTStructuralNode
    ) -> float:
        paths_a = ast_a.extract_paths(max_length=self.path_max_length)
        paths_b = ast_b.extract_paths(max_length=self.path_max_length)

        if not paths_a and not paths_b:
            return 1.0

        set_a = {tuple(p) for p in paths_a}
        set_b = {tuple(p) for p in paths_b}

        if not set_a and not set_b:
            return 1.0

        common = len(set_a & set_b)
        total = len(set_a | set_b)
        return common / total if total > 0 else 0.0
