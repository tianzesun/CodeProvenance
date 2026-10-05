"""
Enhanced AST-based similarity algorithm.

Implements comprehensive Abstract Syntax Tree analysis with:
- Tree Edit Distance (Zhang-Shasha algorithm)
- Control Flow Graph (CFG) extraction and comparison
- Data Flow Graph (DFG) extraction and comparison
- Normalized AST comparison for variable renaming resistance
- Pattern clone detection using subtree matching
- Complexity metrics comparison
"""

import hashlib
import logging
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Any

# ``Finding`` and ``EvidenceBlock`` were re-declared here as look-alike classes. Every
# other engine returns the domain models, so ``isinstance`` checks and ``to_dict()``
# consumers saw two different ``Finding`` types depending on the engine. The domain
# classes are used (and still importable from this module under the same names).
from src.backend.domain.models import EvidenceBlock, Finding

from . import _tree_utils as tu
from .base_similarity import BaseSimilarityAlgorithm
from .code_scan import scan

logger = logging.getLogger(__name__)

#: Relative weights of the score components in ``ASTSimilarity.compare``. They are
#: NORMALISED before use. The constants that were inlined summed to 1.25 (0.60 + 0.10
#: + 0.10 + 0.10 + 0.05 + 0.05 + 0.25), so any pair whose components averaged 0.8
#: scored a perfect 1.0, and ``self.weights`` (which did sum to ~1) was never read.
SCORE_WEIGHTS: dict[str, float] = {
    "winnowing": 0.60,
    "jplag": 0.10,
    "ted": 0.10,
    "pdg": 0.10,
    "pattern": 0.05,
    "complexity": 0.05,
    "control_abstraction": 0.25,
}

#: Pairs of dependency edges are built over at most this many variables.
_MAX_DFG_VARIABLES = 200


_SKIP_KEYWORDS = frozenset(
    "if else elif for while switch case default do return def class import from try except "
    "finally with as yield lambda pass break continue raise assert del global nonlocal in not "
    "and or is True False None self cls range len print list dict set str int float bool object "
    "type enumerate zip map filter all any sum min max sorted".split()
)
_IDENTIFIER_NODES = frozenset({"IDENTIFIER", "VARIABLE", "FUNCTION_NAME", "CLASS_NAME", "PARAMETER"})


class ASTNode:
    """Represents a node in an Abstract Syntax Tree.

    All traversals are iterative (see ``_tree_utils``): the token-built trees nest one
    level per keyword, so recursion overflowed on files of a few hundred statements.
    """

    def __init__(
        self,
        node_type: str,
        value: str = "",
        children: list["ASTNode"] | None = None,
        line: int = 0,
        col: int = 0,
    ):
        self.node_type = node_type
        self.value = value
        self.children: list[ASTNode] = children if children is not None else []
        self.line = line
        self.col = col
        self.parent: ASTNode | None = None
        self._set_parent()

    def _set_parent(self):
        for child in self.children:
            child.parent = self

    def __repr__(self):
        return f"ASTNode({self.node_type}, {self.value!r})"

    def to_tuple(self) -> tuple:
        """Convert node to a nested tuple for hashing (built iteratively)."""
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

    def depth(self) -> int:
        """Calculate depth of this node from root."""
        depth, node = 0, self
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth

    def normalize_variable_names(self):
        """
        Thoroughly normalize identifier names for renaming resistance.
        Handles variables, functions, arguments, and class names.
        """
        var_map: dict[str, str] = {}
        for node in tu.preorder(self):
            if node.node_type in _IDENTIFIER_NODES and node.value and node.value not in _SKIP_KEYWORDS:
                if node.value not in var_map:
                    var_map[node.value] = f"var_{len(var_map)}"
                node.value = var_map[node.value]

    def normalize_control_flow_constructs(self):
        """Normalize equivalent control-flow constructs before structural matching."""
        loop_node_types = {"ForStatement", "WhileStatement", "DoWhileStatement", "ForEachStatement"}
        decision_node_types = {"IfStatement", "SwitchStatement"}
        loop_values = {"for", "while", "do"}
        decision_values = {"if", "switch"}
        branch_values = {"else", "elif", "case", "default"}

        for node in tu.preorder(self):
            if node.node_type in loop_node_types:
                node.node_type = "IterativeBlock"
            elif node.node_type in decision_node_types:
                node.node_type = "DecisionBlock"
            if node.value in loop_values:
                node.value = "ITERATIVE_BLOCK"
            elif node.value in decision_values:
                node.value = "DECISION_BLOCK"
            elif node.value in branch_values:
                node.value = "BRANCH_BLOCK"

    def get_subtrees(self, min_size: int = 1) -> list["ASTNode"]:
        """Get all subtrees with minimum size (sizes computed once, not per node)."""
        sizes = tu.subtree_sizes(self)
        return [n for n in tu.preorder(self) if sizes[id(n)] >= min_size]

    def hash_subtree(self) -> str:
        """Generate hash of subtree for quick comparison."""
        return _subtree_hex_hashes(self)[id(self)]


def _subtree_hex_hashes(root: ASTNode) -> dict[int, str]:
    """``id(node) -> SHA-256 hex`` of every node's subtree in ONE bottom-up pass.

    ``hash_subtree`` used to ``repr`` the whole nested tuple per node: quadratic, and
    ``repr`` of a deep tuple raises RecursionError.
    """
    out: dict[int, str] = {}
    for node in tu.postorder(root):
        payload = f"{node.node_type}|{node.value}|" + ",".join(out[id(c)] for c in node.children)
        out[id(node)] = hashlib.sha256(payload.encode()).hexdigest()
    return out


class JPlagNormalizer:
    """
    JPlag-style identifier normalizer.
    Provides stable rename-invariant normalization by replacing identifiers
    with occurrence-ordered placeholders based on first appearance position.
    """

    def __init__(self):
        self.var_counter = 0
        self.var_map: dict[str, str] = {}
        self.skip_keywords = set(_SKIP_KEYWORDS)
        self.identifier_nodes = set(_IDENTIFIER_NODES)

    def normalize(self, node: ASTNode) -> None:
        """Normalize identifiers in the entire subtree in-place."""
        self.var_counter = 0
        self.var_map.clear()
        self._traverse(node)

    def _traverse(self, node: ASTNode) -> None:
        for current in tu.preorder(node):
            if (
                current.node_type in self.identifier_nodes
                and current.value
                and current.value not in self.skip_keywords
            ):
                if current.value not in self.var_map:
                    self.var_map[current.value] = f"v{self.var_counter}"
                    self.var_counter += 1
                current.value = self.var_map[current.value]


class JPlagSubtreeHasher:
    """
    JPlag-style bottom-up subtree hashing with memoization.
    Implements incremental rolling hash for all subtrees using post-order traversal.
    This is O(n) time complexity vs O(n^2) for naive subtree hashing.
    """

    def __init__(self, min_subtree_size: int = 2, max_subtree_size: int = 32):
        self.min_subtree_size = min_subtree_size
        self.max_subtree_size = max_subtree_size
        self.hash_cache: dict[ASTNode, int] = {}
        self.size_cache: dict[ASTNode, int] = {}
        self.hashes: list[int] = []

    def compute_hashes(self, root: ASTNode) -> list[int]:
        """Compute all subtree hashes for the given AST root."""
        self.hash_cache.clear()
        self.size_cache.clear()
        self.hashes.clear()
        self._postorder(root)
        return list(self.hashes)

    def _postorder(self, root: ASTNode) -> tuple[int, int]:
        """Bottom-up hash calculation (iterative)."""
        for node in tu.postorder(root):
            child_hashes = [self.hash_cache[c] for c in node.children]
            total_size = 1 + sum(self.size_cache[c] for c in node.children)

            # Node hash combines type and SORTED child hashes (order invariant)
            hash_input = f"{node.node_type}|{node.value}|{sorted(child_hashes)}".encode()
            node_hash = tu.hash64(hash_input)

            self.hash_cache[node] = node_hash
            self.size_cache[node] = total_size
            if self.min_subtree_size <= total_size <= self.max_subtree_size:
                self.hashes.append(node_hash)
        return self.hash_cache[root], self.size_cache[root]


def multiset_jaccard_similarity(hashes_a: list[int], hashes_b: list[int]) -> float:
    """
    Compute Multiset Jaccard similarity (bag similarity) as used in JPlag.
    This correctly handles duplicate subtree occurrences unlike set-based Jaccard.

    Formula: sum(min(count_a[x], count_b[x])) / sum(max(count_a[x], count_b[x]))
    """
    if not hashes_a and not hashes_b:
        return 1.0
    if not hashes_a or not hashes_b:
        return 0.0

    count_a = Counter(hashes_a)
    count_b = Counter(hashes_b)

    all_keys = count_a.keys() | count_b.keys()
    min_sum = 0
    max_sum = 0

    for key in all_keys:
        ca = count_a.get(key, 0)
        cb = count_b.get(key, 0)
        min_sum += min(ca, cb)
        max_sum += max(ca, cb)

    return min_sum / max_sum if max_sum > 0 else 0.0


def collect_hash_sequence(root: ASTNode, min_size: int = 3) -> list[int]:
    """
    Collect the sequence of subtree hashes (children before parents) for subtrees of at
    least ``min_size`` nodes. Order-sensitive: the hash of a node covers its ordered
    child hashes.

    Returns:
        Ordered list of 64-bit integer hashes for valid subtrees
    """
    hashes: list[int] = []
    cache: dict[int, tuple[int, int]] = {}
    for node in tu.postorder(root):
        child_hashes = [cache[id(c)][0] for c in node.children]
        size = 1 + sum(cache[id(c)][1] for c in node.children)
        node_hash = tu.hash64(f"{node.node_type}|{node.value}|{child_hashes}".encode())
        cache[id(node)] = (node_hash, size)
        if size >= min_size:
            hashes.append(node_hash)
    return hashes


def winnow(hash_sequence: list[int], window_size: int = 5) -> set[int]:
    """
    Winnowing algorithm to select robust document fingerprint hashes.

    For each sliding window of size window_size:
    1. Find minimum hash value in window
    2. Select rightmost occurrence of this minimum
    3. Ensure each hash is only added once

    Guarantees that any two sequences with > window_size consecutive matching
    hashes will share at least one common fingerprint.

    Returns:
        Set of selected winnowing fingerprint hashes
    """
    if not hash_sequence:
        return set()

    n = len(hash_sequence)
    if n <= window_size:
        return set(hash_sequence)

    fingerprints = set()
    last_selected = -1

    for i in range(n - window_size + 1):
        window = hash_sequence[i : i + window_size]
        min_hash = min(window)

        # Find rightmost occurrence of min_hash in current window
        rightmost_pos = window_size - 1
        while rightmost_pos >= 0 and window[rightmost_pos] != min_hash:
            rightmost_pos -= 1

        global_pos = i + rightmost_pos

        if global_pos != last_selected:
            fingerprints.add(min_hash)
            last_selected = global_pos

    return fingerprints


def jaccard_set(set_a: set[int], set_b: set[int]) -> float:
    """
    Standard Jaccard similarity for sets of winnowing fingerprints.

    Formula: |A ∩ B| / |A ∪ B|
    """
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


class WinnowingFingerprinter:
    """
    Winnowing fingerprinting system for fast AST similarity detection.
    Combines ordered subtree hashing with sliding window minimum selection
    to produce robust, compact document fingerprints.

    Performance: 5-10x faster than full subtree hashing with near identical accuracy.
    """

    def __init__(self, window_size: int = 5, min_subtree_size: int = 3):
        self.window_size = window_size
        self.min_subtree_size = min_subtree_size

    def fingerprint(self, root: ASTNode) -> set[int]:
        """Generate winnowing fingerprint set for an AST."""
        hash_sequence = collect_hash_sequence(root, self.min_subtree_size)
        return winnow(hash_sequence, self.window_size)

    def compare(self, root_a: ASTNode, root_b: ASTNode) -> float:
        """Compare two ASTs using winnowing fingerprint similarity."""
        fp_a = self.fingerprint(root_a)
        fp_b = self.fingerprint(root_b)
        return jaccard_set(fp_a, fp_b)


class CFGEdge:
    """Represents an edge in a Control Flow Graph."""

    def __init__(self, from_block: int, to_block: int, edge_type: str = "flow"):
        self.from_block = from_block
        self.to_block = to_block
        self.edge_type = edge_type

    def __eq__(self, other):
        if not isinstance(other, CFGEdge):
            return False
        return self.from_block == other.from_block and self.to_block == other.to_block

    def __hash__(self):
        return hash((self.from_block, self.to_block))

    def __repr__(self):
        return f"CFGEdge({self.from_block}->{self.to_block}, {self.edge_type})"


class ControlFlowGraph:
    """Represents a Control Flow Graph."""

    def __init__(self):
        self.basic_blocks: list[dict[str, Any]] = []
        self.edges: list[CFGEdge] = []
        self.entry_block: int = 0
        self.exit_blocks: list[int] = []

    def add_block(
        self, statements: list[str] | None = None, block_id: int | None = None
    ) -> int:
        """Add a basic block."""
        block_id = block_id if block_id is not None else len(self.basic_blocks)
        self.basic_blocks.append(
            {"id": block_id, "statements": statements or [], "type": "normal"}
        )
        return block_id

    def add_edge(self, from_block: int, to_block: int, edge_type: str = "flow"):
        """Add control flow edge."""
        self.edges.append(CFGEdge(from_block, to_block, edge_type))

    def to_signature(self) -> str:
        """Generate CFG signature for comparison."""
        sorted_edges = sorted(self.edges, key=lambda e: (e.from_block, e.to_block))
        edge_str = ",".join(
            f"{e.from_block}-{e.to_block}-{e.edge_type}" for e in sorted_edges
        )
        block_types = sorted(b.get("type", "normal") for b in self.basic_blocks)
        block_str = ",".join(block_types)
        combined = f"blocks:[{block_str}];edges:[{edge_str}]"
        return hashlib.sha256(combined.encode()).hexdigest()


class DataFlowGraph:
    """Represents a Data Flow Graph."""

    def __init__(self):
        self.variables: dict[str, list[str]] = defaultdict(list)
        self.dependencies: list[tuple[str, str]] = []
        self.dependencies_by_type: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def add_dependency(self, from_var: str, to_var: str, dep_type: str = "data"):
        """Add data dependency."""
        self.dependencies.append((from_var, to_var))
        self.dependencies_by_type[dep_type].append((from_var, to_var))

    def to_signature(self) -> str:
        """Generate DFG signature for comparison."""
        sorted_deps = sorted(self.dependencies)
        dep_str = ",".join(f"{d[0]}->{d[1]}" for d in sorted_deps)
        return hashlib.sha256(dep_str.encode()).hexdigest()


class TreeEditDistance:
    """
    Identity-Aware tree edit distance calculation.

    Computes weighted edit distance with identity awareness:
    - Higher cost for mismatches at greater function depths
    - Higher cost for mismatches in high logic density regions
    - FunctionDeclaration nodes have strict identity matching requirements
    """

    def __init__(
        self,
        deletion_cost: float = 1.0,
        insertion_cost: float = 1.0,
        relabel_cost: float = 1.0,
    ):
        self.deletion_cost = deletion_cost
        self.insertion_cost = insertion_cost
        self.relabel_cost = relabel_cost

    def calculate_distance(
        self, tree_a: ASTNode | None, tree_b: ASTNode | None
    ) -> float:
        """Calculate identity-aware tree edit distance between two ASTs."""
        if tree_a is None or tree_b is None:
            return float("inf")

        # Precompute node weightings for both trees
        weights_a = self._compute_node_weights(tree_a)
        weights_b = self._compute_node_weights(tree_b)

        forest_a = self._postorder_linearize(tree_a)
        forest_b = self._postorder_linearize(tree_b)

        return self._identity_aware_ted(forest_a, forest_b, weights_a, weights_b)

    def _compute_node_weights(self, root: ASTNode) -> dict[ASTNode, float]:
        """Compute identity weights for each node based on depth and context."""
        weights: dict[ASTNode, float] = {}
        function_types = {"FunctionDeclaration", "def", "function"}
        control_types = {
            "IfStatement", "ForStatement", "WhileStatement", "TryStatement",
            "ReturnStatement", "if", "for", "while",
        }  # fmt: skip
        for node, depth in tu.with_depths(root):
            depth_weight = 1.0 + (depth * 0.15)
            if node.node_type in function_types:
                weights[node] = 3.0 * depth_weight  # strict identity requirements
            elif node.node_type in control_types:
                weights[node] = 2.0 * depth_weight
            else:
                weights[node] = 1.0 * depth_weight
        return weights

    def _identity_aware_ted(
        self,
        forest_a: list[ASTNode],
        forest_b: list[ASTNode],
        weights_a: dict[ASTNode, float],
        weights_b: dict[ASTNode, float],
    ) -> float:
        """Identity-aware tree edit distance with weighted nodes."""
        if not forest_a and not forest_b:
            return 0.0
        if not forest_a:
            return sum(weights_b[n] * self.insertion_cost for n in forest_b)
        if not forest_b:
            return sum(weights_a[n] * self.deletion_cost for n in forest_a)

        deletion_cost = 0.0
        insertion_cost = 0.0

        # One bottom-up hash per node (the forest is in post-order, so its last node
        # is the root). ``to_tuple()`` per node was quadratic in the tree size.
        label = lambda n: f"{n.node_type}|{n.value}"  # noqa: E731
        hashes_a = tu.subtree_hashes(forest_a[-1], label)
        hashes_b = tu.subtree_hashes(forest_b[-1], label)
        tuples_a = [hashes_a[id(node)] for node in forest_a]
        tuples_b = [hashes_b[id(node)] for node in forest_b]

        set_a = set(tuples_a)
        set_b = set(tuples_b)

        # Calculate costs for unmatched nodes with their weights
        for i, node in enumerate(forest_a):
            if tuples_a[i] not in set_b:
                deletion_cost += weights_a[node] * self.deletion_cost

        for i, node in enumerate(forest_b):
            if tuples_b[i] not in set_a:
                insertion_cost += weights_b[node] * self.insertion_cost

        # Function depth identity penalty
        functions_a = [
            n
            for n in forest_a
            if n.node_type in ["FunctionDeclaration", "def", "function"]
        ]
        functions_b = [
            n
            for n in forest_b
            if n.node_type in ["FunctionDeclaration", "def", "function"]
        ]

        function_depth_penalty = 0.0
        for fa, fb in zip(functions_a, functions_b):
            depth_diff = abs(fa.depth() - fb.depth())
            if depth_diff > 0:
                function_depth_penalty += depth_diff * 1.5

        # Logic density penalty
        control_a = sum(
            1
            for n in forest_a
            if n.node_type
            in ["IfStatement", "ForStatement", "WhileStatement", "if", "for", "while"]
        )
        control_b = sum(
            1
            for n in forest_b
            if n.node_type
            in ["IfStatement", "ForStatement", "WhileStatement", "if", "for", "while"]
        )

        density_a = control_a / max(len(forest_a), 1)
        density_b = control_b / max(len(forest_b), 1)
        density_penalty = abs(density_a - density_b) * 10.0

        return deletion_cost + insertion_cost + function_depth_penalty + density_penalty

    def _postorder_linearize(self, node: ASTNode) -> list[ASTNode]:
        """Linearize tree using post-order traversal."""
        return tu.postorder(node)


class ProgramDependencyGraph:
    """
    Combines Control Flow Graph (CFG) and Data Flow Graph (DFG).
    This captures the semantic structure of the code, making it
    resistant to statement reordering and junk code insertion.
    """

    def __init__(self, cfg: ControlFlowGraph, dfg: DataFlowGraph):
        self.cfg = cfg
        self.dfg = dfg

    def to_signature(self) -> str:
        """
        Combine CFG and DFG signatures.
        The signature is invariant to variable renaming (if AST was normalized).
        """
        cfg_sig = self.cfg.to_signature()
        dfg_sig = self.dfg.to_signature()
        combined = f"cfg:{cfg_sig};dfg:{dfg_sig}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def has_data(self) -> bool:
        """True when at least one graph has an edge/dependency to compare."""
        return bool(self.cfg.edges or self.dfg.dependencies)

    def compare(self, other: "ProgramDependencyGraph") -> float:
        """Compare two PDGs for structural similarity."""
        # Weighted average of CFG and DFG similarity
        cfg_score = self._set_similarity(set(self.cfg.edges), set(other.cfg.edges))
        dfg_score = self._set_similarity(
            set(self.dfg.dependencies), set(other.dfg.dependencies)
        )
        return cfg_score * 0.4 + dfg_score * 0.6

    def _set_similarity(self, set_a: set, set_b: set) -> float:
        if not set_a and not set_b:
            return 1.0
        common = len(set_a.intersection(set_b))
        total = len(set_a.union(set_b))
        return common / total if total > 0 else 0.0


def tokenize_raw_for_ast(source: str, language: str | None = None) -> list[dict[str, str]]:
    """Build coarse AST tokens from raw source when a parser is unavailable.

    Uses the comment/string-aware scanner: stripping ``//`` before strings both
    destroyed Python floor division and cut lines at any ``//`` or ``#`` inside a
    string, and string contents were tokenised as code.
    """
    class_keywords = {"class", "interface", "enum", "struct"}
    function_keywords = {"def", "func", "function"}
    control_keywords = {
        "if", "else", "for", "while", "switch", "case", "return", "break", "continue",
        "try", "catch", "finally", "throw", "do", "elif", "except",
    }  # fmt: skip
    tokens: list[dict[str, str]] = []
    for kind, token in scan(source, language):
        if kind == "ident":
            if token in class_keywords:
                token_type = "CLASS"
            elif token in function_keywords:
                token_type = "FUNCTION"
            elif token in control_keywords:
                token_type = "KEYWORD"
            else:
                token_type = "IDENTIFIER"
        elif kind in ("number", "string"):
            token_type = "LITERAL"
            token = "STR" if kind == "string" else token
        else:
            token_type = "OPERATOR"
        tokens.append({"type": token_type, "value": token})
    return tokens


class ASTSimilarity(BaseSimilarityAlgorithm):
    """
    Enhanced AST-based similarity algorithm.

    Combines multiple structural analysis techniques:
    - Tree Edit Distance
    - Control Flow Graph comparison
    - Data Flow Graph comparison
    - Normalized AST comparison
    - Subtree pattern matching
    - Complexity metrics comparison
    """

    def __init__(
        self,
        ted_weight: float = 0.35,
        cfg_weight: float = 0.18,
        dfg_weight: float = 0.18,
        pattern_weight: float = 0.12,
        complexity_weight: float = 0.17,
        normalize_variables: bool = True,
    ):
        """
        Initialize Identity-Aware AST similarity algorithm.

        Args:
            ted_weight: Weight for identity-aware tree edit distance
            cfg_weight: Weight for control flow graph comparison
            dfg_weight: Weight for data flow graph comparison
            pattern_weight: Weight for subtree pattern matching
            complexity_weight: Weight for complexity metrics (function depth, logic density)
            normalize_variables: Whether to normalize variable names before comparison
        """
        super().__init__("enhanced_ast")
        self.ted = TreeEditDistance()
        self.weights: dict[str, float] = {
            "ted": ted_weight,
            "cfg": cfg_weight,
            "dfg": dfg_weight,
            "pattern": pattern_weight,
            "complexity": complexity_weight,
            "jplag": 0.65,
        }
        self.normalize_variables = normalize_variables
        # Kept for compatibility. ``compare`` builds its own normaliser/hasher per call:
        # both carry per-call state (``var_map``, ``hashes``), so sharing them across a
        # thread pool corrupted each other's results.
        self.jplag_normalizer = JPlagNormalizer()
        self.jplag_hasher = JPlagSubtreeHasher(min_subtree_size=2, max_subtree_size=32)
        self.use_jplag_fast_path = True
        self.winnowing_fingerprinter = WinnowingFingerprinter(
            window_size=5, min_subtree_size=3
        )
        self.use_winnowing_fast_path = True

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> Finding:
        """
        Compare two parsed code representations using AST analysis.

        Returns:
            A Finding object containing scores and evidence.
        """
        # (A pre-parsed ``ast`` counts as data: an input with only an AST was rejected
        # here as "empty" and scored 0.0.)
        if not any(
            parsed.get(key) for parsed in (parsed_a, parsed_b) for key in ("ast", "tokens", "raw")
        ):
            return Finding(engine=self.name, score=0.0, confidence=1.0)

        ast_a = self._extract_ast(parsed_a)
        ast_b = self._extract_ast(parsed_b)
        ast_tokens_a = self._tokens_for_graphs(parsed_a)
        ast_tokens_b = self._tokens_for_graphs(parsed_b)

        raw_a = parsed_a.get("raw", "") or ""
        raw_b = parsed_b.get("raw", "") or ""

        if ast_a is None or ast_b is None:
            return Finding(engine=self.name, score=0.0, confidence=1.0)

        if self.normalize_variables:
            ast_a.normalize_variable_names()
            ast_b.normalize_variable_names()
        ast_a.normalize_control_flow_constructs()
        ast_b.normalize_control_flow_constructs()

        # Winnowing fast path (fastest - 5-10x speed improvement)
        winnowing_score = 0.0
        if self.use_winnowing_fast_path:
            winnowing_score = self.winnowing_fingerprinter.compare(ast_a, ast_b)

            # Ultra early exit threshold for very high similarity
            if winnowing_score >= 0.97:
                return Finding(
                    engine=self.name,
                    score=min(1.0, winnowing_score),
                    confidence=0.99,
                    evidence_blocks=[
                        EvidenceBlock(
                            engine=self.name,
                            score=winnowing_score,
                            confidence=0.99,
                            a_snippet="Winnowing fingerprint match",
                            b_snippet="Winnowing fingerprint match",
                            transformation_notes=[
                                "Ordered subtree hashing",
                                "Sliding window winnowing",
                                "Rename invariant",
                            ],
                        )
                    ],
                    methodology="Winnowing fingerprinting with window size=5, min subtree size=3.",
                )

        # JPlag fast path (optimized subtree hashing)
        jplag_score = 0.0
        if self.use_jplag_fast_path:
            # Make copies to preserve original AST for full analysis
            ast_a_jplag = self._deep_copy_ast(ast_a)
            ast_b_jplag = self._deep_copy_ast(ast_b)

            normalizer = JPlagNormalizer()
            normalizer.normalize(ast_a_jplag)
            normalizer.normalize(ast_b_jplag)

            hasher = JPlagSubtreeHasher(min_subtree_size=2, max_subtree_size=32)
            hashes_a = hasher.compute_hashes(ast_a_jplag)
            hashes_b = hasher.compute_hashes(ast_b_jplag)

            jplag_score = multiset_jaccard_similarity(hashes_a, hashes_b)

            # Early exit threshold: if extremely high similarity, return immediately
            if jplag_score >= 0.95:
                return Finding(
                    engine=self.name,
                    score=min(1.0, jplag_score),
                    confidence=0.98,
                    evidence_blocks=[
                        EvidenceBlock(
                            engine=self.name,
                            score=jplag_score,
                            confidence=0.98,
                            a_snippet="JPlag subtree hash match",
                            b_snippet="JPlag subtree hash match",
                            transformation_notes=[
                                "Bottom-up subtree hashing",
                                "Multiset Jaccard similarity",
                                "Rename invariant",
                            ],
                        )
                    ],
                    methodology="JPlag-style optimized subtree hashing with multiset Jaccard similarity.",
                )

        # 1. AST Metrics
        ted_score = self._tree_edit_distance_similarity(ast_a, ast_b)

        cfg_a = self._extract_cfg(parsed_a, ast_tokens_a)
        cfg_b = self._extract_cfg(parsed_b, ast_tokens_b)
        dfg_a = self._extract_dfg(parsed_a, ast_tokens_a)
        dfg_b = self._extract_dfg(parsed_b, ast_tokens_b)

        pdg_a = ProgramDependencyGraph(cfg_a, dfg_a)
        pdg_b = ProgramDependencyGraph(cfg_b, dfg_b)

        # With no control-flow edges and no dependencies on EITHER side the PDG says
        # nothing. It used to report 1.0 ("identical": two empty sets), and for raw-source
        # input (the usual case) that was every pair: +0.10 on every score, and it also
        # satisfied the ``pdg_score >= 0.5`` clause of the 0.56 floor below.
        pdg_score: float | None = pdg_a.compare(pdg_b) if (pdg_a.has_data() or pdg_b.has_data()) else None

        pattern_score = self._pattern_similarity(ast_a, ast_b)
        complexity_score = self._complexity_similarity(ast_a, ast_b)
        control_abstraction_score = self._control_abstraction_similarity(ast_a, ast_b)

        # 2. Stylometry adjustment input (per-file features are cached)
        stylometry_score = self._stylometry_similarity(raw_a, raw_b)

        # 3. Weighted mean over the components that have a value, with weights normalised.
        components = {
            "winnowing": winnowing_score,
            "jplag": jplag_score,
            "ted": ted_score,
            "pdg": pdg_score,
            "pattern": pattern_score,
            "complexity": complexity_score,
            "control_abstraction": control_abstraction_score,
        }
        active = {k: v for k, v in components.items() if v is not None}
        total_weight = sum(SCORE_WEIGHTS[k] for k in active)
        score = sum(SCORE_WEIGHTS[k] * v for k, v in active.items()) / total_weight

        # 4. Stylometry Adjustment (Boost/Penalty)
        # If stylometry is very different, reduce the score to avoid FP
        if stylometry_score < 0.4:
            score *= 0.8

        if (
            control_abstraction_score >= 0.55
            and pdg_score is not None
            and pdg_score >= 0.50
            and complexity_score >= 0.75
        ):
            score = max(score, 0.56)

        # 5. Evidence Blocks
        evidence = []
        if score > 0.6:
            evidence.append(
                EvidenceBlock(
                    engine=self.name,
                    score=score,
                    confidence=0.9,
                    a_snippet="AST structural alignment detected",
                    b_snippet="AST structural alignment detected",
                    transformation_notes=["Tree edit distance", "CFG/DFG isomorphism"],
                )
            )

        return Finding(
            engine=self.name,
            score=min(1.0, max(0.0, score)),
            confidence=0.92,
            evidence_blocks=evidence,
            methodology="Comprehensive AST analysis including TED, CFG/DFG overlap, and stylometry.",
        )

    def _extract_ast(self, parsed: dict[str, Any]) -> ASTNode | None:
        """Extract AST from parsed code representation."""
        if parsed.get("ast"):
            return self._convert_to_ast_nodes(parsed["ast"])

        tokens = parsed.get("tokens")
        if tokens:
            return self._build_ast_from_tokens(tokens)

        raw = parsed.get("raw", "")
        if raw:
            return self._build_ast_from_tokens(
                self._tokenize_raw_for_ast(raw, parsed.get("language"))
            )

        return None

    def _tokens_for_graphs(self, parsed: dict[str, Any]) -> list[dict]:
        """Token dicts used by the CFG/DFG extractors.

        They read ``parsed["tokens"]`` only, so for raw-source input they saw nothing and
        every pair was reported as having an identical (empty) CFG and DFG.
        """
        tokens = parsed.get("tokens")
        if tokens:
            return [t for t in tokens if isinstance(t, dict)]
        raw = parsed.get("raw", "")
        return self._tokenize_raw_for_ast(raw, parsed.get("language")) if raw else []

    def _tokenize_raw_for_ast(self, source: str, language: str | None = None) -> list[dict[str, str]]:
        """Coarse AST tokens from raw source (see :func:`tokenize_raw_for_ast`)."""
        return tokenize_raw_for_ast(source, language)

    def _deep_copy_ast(self, node: ASTNode) -> ASTNode:
        """Create deep copy of ASTNode subtree (iterative)."""
        copies: dict[int, ASTNode] = {}
        for current in tu.postorder(node):
            copies[id(current)] = ASTNode(
                current.node_type,
                current.value,
                [copies[id(c)] for c in current.children],
                current.line,
                current.col,
            )
        return copies[id(node)]

    def _convert_to_ast_nodes(self, ast_data: Any) -> ASTNode:
        """Convert parsed AST data (nested dicts) to ASTNode structure, iteratively."""
        if not isinstance(ast_data, dict):
            return ASTNode("LITERAL", str(ast_data))
        root = ASTNode(ast_data.get("type", "UNKNOWN"), ast_data.get("value", ""))
        stack: list[tuple[dict, ASTNode]] = [(ast_data, root)]
        while stack:
            data, node = stack.pop()
            for child_data in data.get("children", []) or []:
                if isinstance(child_data, dict):
                    child = ASTNode(child_data.get("type", "UNKNOWN"), child_data.get("value", ""))
                    stack.append((child_data, child))
                else:
                    child = ASTNode("LITERAL", str(child_data))
                node.children.append(child)
                child.parent = node
        return root

    def _build_ast_from_tokens(self, tokens: list[dict]) -> ASTNode:
        """Build simplified AST from token stream."""
        root = ASTNode("ROOT")
        current_node = root

        for token in tokens:
            if not isinstance(token, dict):
                continue
            token_type = token.get("type", "UNKNOWN")
            value = token.get("value", "")

            new_node = ASTNode(token_type, value)
            new_node.parent = current_node
            current_node.children.append(new_node)
            if token_type in ("KEYWORD", "FUNCTION", "CLASS"):
                current_node = new_node

        return root

    def _tree_edit_distance_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Calculate similarity based on tree edit distance."""
        distance = self.ted.calculate_distance(ast_a, ast_b)
        max_size = max(ast_a.subtree_size(), ast_b.subtree_size())

        if max_size == 0:
            return 1.0

        similarity = 1.0 - (distance / max_size)
        return max(0.0, min(1.0, similarity))

    def _cfg_similarity(self, parsed_a: dict, parsed_b: dict) -> float:
        """Calculate similarity based on control flow graphs."""
        cfg_a = self._extract_cfg(parsed_a)
        cfg_b = self._extract_cfg(parsed_b)

        if cfg_a is None or cfg_b is None:
            return 0.5

        if cfg_a.to_signature() == cfg_b.to_signature():
            return 1.0

        edges_a = set(cfg_a.edges)
        edges_b = set(cfg_b.edges)

        if not edges_a and not edges_b:
            return 1.0

        common = len(edges_a.intersection(edges_b))
        total = len(edges_a.union(edges_b))

        return common / total if total > 0 else 0.0

    def _extract_cfg(self, parsed: dict, tokens: list[dict] | None = None) -> ControlFlowGraph | None:
        """Extract Control Flow Graph from parsed code."""
        cfg = ControlFlowGraph()

        if tokens is None:
            if "tokens" not in parsed:
                return cfg
            tokens = parsed["tokens"]

        current_block = cfg.add_block([])
        block_stack = [current_block]
        loop_stack: list[int] = []

        for token in tokens:
            if token.get("type") != "KEYWORD":
                continue

            value = token.get("value", "")

            if value in {"if", "switch"}:
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], new_block, "conditional")
                block_stack.append(new_block)

            elif value in {"else", "case", "default", "elif"}:
                if len(block_stack) > 1:
                    block_stack.pop()
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], new_block, "alternative")
                block_stack.append(new_block)

            elif value in ["for", "while"]:
                loop_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], loop_block, "loop")
                loop_stack.append(loop_block)
                block_stack.append(loop_block)

            elif value == "break":
                if loop_stack:
                    cfg.add_edge(block_stack[-1], loop_stack[-1], "break")

            elif value == "continue":
                if loop_stack:
                    cfg.add_edge(block_stack[-1], loop_stack[-1], "continue")

            elif value == "return":
                cfg.add_edge(block_stack[-1], -1, "return")

            elif value == "try":
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1], new_block, "try")
                block_stack.append(new_block)

            elif value in {"except", "catch"}:
                if block_stack:
                    block_stack.pop()
                new_block = cfg.add_block([])
                cfg.add_edge(block_stack[-1] if block_stack else 0, new_block, "except")
                block_stack.append(new_block)

        return cfg

    def _dfg_similarity(self, parsed_a: dict, parsed_b: dict) -> float:
        """Calculate similarity based on data flow graphs."""
        dfg_a = self._extract_dfg(parsed_a)
        dfg_b = self._extract_dfg(parsed_b)

        if dfg_a is None or dfg_b is None:
            return 0.5

        deps_a = set(dfg_a.dependencies)
        deps_b = set(dfg_b.dependencies)

        if not deps_a and not deps_b:
            return 1.0

        common = len(deps_a.intersection(deps_b))
        total = len(deps_a.union(deps_b))

        return common / total if total > 0 else 0.0

    def _extract_dfg(self, parsed: dict, tokens: list[dict] | None = None) -> DataFlowGraph | None:
        """Extract Data Flow Graph from parsed code.

        Variables are renamed by order of first appearance (so renaming does not change
        the graph) and kept in that order. The dependency pairs used to be built from
        iterating a ``set``, whose order differs between runs, so the (a, b) and (b, a)
        edge directions were arbitrary.
        """
        dfg = DataFlowGraph()

        if tokens is None:
            if "tokens" not in parsed:
                return dfg
            tokens = parsed["tokens"]

        order: dict[str, str] = {}
        for token in tokens:
            if token.get("type") in ("VARIABLE", "IDENTIFIER", "NAME"):
                name = token.get("value", "")
                if not name or name in _SKIP_KEYWORDS:
                    continue
                canonical = order.get(name)
                if canonical is None:
                    canonical = order[name] = f"v{len(order)}" if self.normalize_variables else name
                    dfg.variables[canonical].append("definition")
                else:
                    dfg.variables[canonical].append("use")

        # Infer dependencies from sequential variable usage (capped: all pairs of
        # thousands of names would be tens of millions of tuples)
        var_list = list(dfg.variables)[:_MAX_DFG_VARIABLES]
        for i, var in enumerate(var_list):
            for other_var in var_list[i + 1 :]:
                dfg.add_dependency(var, other_var, "sequential")

        return dfg

    def _pattern_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Calculate similarity based on subtree pattern matching."""
        sizes_a, sizes_b = tu.subtree_sizes(ast_a), tu.subtree_sizes(ast_b)
        hashes_a_all, hashes_b_all = _subtree_hex_hashes(ast_a), _subtree_hex_hashes(ast_b)
        hashes_a = {hashes_a_all[i] for i, n in sizes_a.items() if n >= 2}
        hashes_b = {hashes_b_all[i] for i, n in sizes_b.items() if n >= 2}

        if not hashes_a and not hashes_b:
            return 1.0

        common = len(hashes_a.intersection(hashes_b))
        total = len(hashes_a.union(hashes_b))

        return common / total if total > 0 else 0.0

    def _control_abstraction_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Compare normalized control-flow intent without requiring identical shape."""
        marker_values = {
            "ITERATIVE_BLOCK", "DECISION_BLOCK", "BRANCH_BLOCK", "return", "break", "continue", "throw",
        }  # fmt: skip

        def _tokens(root: ASTNode) -> list[str]:
            tokens = []
            for node in tu.preorder(root):
                if node.value in marker_values:
                    tokens.append(node.value)
                elif node.node_type in {"OPERATOR", "NUMBER", "LITERAL"}:
                    tokens.append(node.node_type)
            return tokens

        tokens_a = _tokens(ast_a)
        tokens_b = _tokens(ast_b)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        count_a = Counter(tokens_a)
        count_b = Counter(tokens_b)
        intersection = sum((count_a & count_b).values())
        union = sum((count_a | count_b).values())
        return intersection / union if union else 0.0

    def _complexity_similarity(self, ast_a: ASTNode, ast_b: ASTNode) -> float:
        """Calculate similarity based on complexity metrics."""
        metrics_a = self._compute_complexity(ast_a)
        metrics_b = self._compute_complexity(ast_b)

        # Compare individual metrics
        scores: list[float] = []

        for key in metrics_a:
            if key in metrics_b:
                val_a = metrics_a[key]
                val_b = metrics_b[key]
                max_val = max(val_a, val_b)
                if max_val == 0:
                    scores.append(1.0)
                else:
                    # Use ratio similarity
                    ratio = min(val_a, val_b) / max_val
                    scores.append(ratio)

        return sum(scores) / len(scores) if scores else 0.5

    def _compute_complexity(self, ast: ASTNode) -> dict[str, float]:
        """Compute complexity metrics from AST with logic density and function depth."""
        total_nodes = ast.subtree_size()

        node_types: dict[str, int] = defaultdict(int)
        function_depths = []
        max_depth = 0

        for node, depth in tu.with_depths(ast):
            node_types[node.node_type] += 1
            max_depth = max(max_depth, depth)
            if node.node_type == "FunctionDeclaration" or node.node_type == "def":
                function_depths.append(depth)

        # Cyclomatic complexity approximation
        decision_points = sum(node_types.get(t, 0) for t in ["if", "for", "while", "elif", "case", "catch"])
        cyclomatic = decision_points + 1

        # Logic density: ratio of control flow nodes to total nodes
        control_flow_nodes = sum(
            node_types.get(t, 0)
            for t in ["if", "for", "while", "elif", "case", "catch", "return", "break", "continue"]
        )
        logic_density = control_flow_nodes / max(total_nodes, 1)

        avg_function_depth = sum(function_depths) / len(function_depths) if function_depths else 0.0

        return {
            "total_nodes": float(total_nodes),
            "cyclomatic": float(cyclomatic),
            "max_depth": float(max_depth),
            "branching_factor": (total_nodes - 1) / max(max_depth, 1),
            "logic_density": float(logic_density),
            "avg_function_depth": float(avg_function_depth),
            "function_count": float(len(function_depths)),
        }

    def _stylometry_similarity(self, raw_a: str, raw_b: str) -> float:
        """Stylometry similarity of two sources; per-file features are cached."""
        from src.backend.engines.features.stylometry import compare_stylometry

        return compare_stylometry(_style_features(raw_a), _style_features(raw_b))


@lru_cache(maxsize=128)
def _style_features(raw: str) -> dict[str, Any]:
    """Stylometry features of one source (cached: they were re-extracted, with a full
    ``ast.parse``, for both files of every pair)."""
    from src.backend.engines.features.stylometry import StylometryExtractor

    return StylometryExtractor().extract(raw)
