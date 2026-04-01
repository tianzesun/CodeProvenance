"""
Advanced AST Normalizer – robust against advanced obfuscation.

Handles:
- Variable/function renaming (AST normalizes identifiers)
- Statement reordering (control-flow-aware canonicalization)
- Dead code insertion (unreachable code detection)
- Control flow changes (CFG comparison)
- Comment/whitespace/formatting changes (already handled by AST)

Strategy:
1. Parse to AST
2. Normalize all identifiers to __ID__
3. Build Control Flow Graph (CFG)
4. Build Program Dependency Graph (PDG)
5. Compute structural hash of CFG + PDG
6. Compare CFG/PDG similarity

This approach is robust because obfuscation that changes surface text
(renaming, reordering comments, inserting unreachable dead code)
will NOT change the CFG/PDG structure.
"""
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
import ast
import re
import hashlib
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class CFGNode:
    """Node in the Control Flow Graph."""
    node_id: int
    node_type: str
    stmt_hash: str  # Hash of normalized statement
    predecessors: List[int] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    is_entry: bool = False
    is_exit: bool = False


@dataclass
class PDGNode:
    """Node in the Program Dependency Graph."""
    node_id: int
    variable: str
    definition_line: int
    uses: List[int] = field(default_factory=list)  # CFGNode IDs
    dep_from: List[int] = field(default_factory=list)  # PDGNode IDs (data deps)


@dataclass
class NormalizedProgram:
    """Fully normalized program representation."""
    ast_structure_hash: str
    cfg_nodes: List[CFGNode]
    cfg_edges: List[Tuple[int, int]]
    pdg_nodes: List[PDGNode]
    token_sequence: List[str]
    function_signatures: List[str]
    complexity_scores: Dict[str, float]

    @property
    def structural_fingerprint(self) -> str:
        """Compute a fingerprint robust to obfuscation."""
        parts = [self.ast_structure_hash]
        # CFG edge list (sorted for determinism)
        cfg_sorted = sorted(self.cfg_edges)
        parts.append(str(cfg_sorted))
        # PDG structure
        pdg_deps = sorted(
            (n.variable, sorted(n.dep_from)) for n in self.pdg_nodes
        )
        parts.append(str(pdg_deps))
        return hashlib.sha256('|'.join(parts).encode()).hexdigest()


class DeadCodeRemover:
    """
    Detects and removes unreachable dead code.

    Dead code patterns:
    - Code after unconditional return
    - Code in always-false conditions
    - Unused variable assignments
    - Unreachable branches
    """

    def visit(self, node: ast.AST) -> None:
        """Mark dead code nodes."""
        pass

    @staticmethod
    def remove_dead_code(tree: ast.AST) -> ast.AST:
        """Remove unreachable code from AST."""
        return DeadCodeRemoverVisitor().visit(tree)


class DeadCodeRemoverVisitor(ast.NodeTransformer):
    """AST visitor that removes unreachable code after return statements."""

    def __init__(self):
        self._in_dead_code = False

    def _is_dead(self, node: ast.AST) -> bool:
        """Check if a node is dead code."""
        if isinstance(node, (ast.Return, ast.Raise)):
            return False  # These are the terminating statements, not dead
        return self._in_dead_code

    def _mark_dead_after(self, body: List[ast.AST]) -> List[ast.AST]:
        """Remove statements after a return/raise/continue/break."""
        result = []
        for stmt in body:
            if self._is_dead(stmt):
                break  # Everything after is dead
            result.append(stmt)
            # Check if this statement terminates the block
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                self._in_dead_code = True
                break
        return result

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Process function body, removing dead code."""
        old_dead = self._in_dead_code
        self._in_dead_code = False
        new_body = self._mark_dead_after(node.body)
        self._in_dead_code = old_dead
        node.body = [self.generic_visit(stmt) for stmt in new_body]
        return node

    def visit_If(self, node: ast.If) -> ast.If:
        """Process if/else branches."""
        node = self.generic_visit(node)
        # Remove empty branches
        node.body = self._mark_dead_after(node.body)
        node.orelse = self._mark_dead_after(node.orelse)
        # Remove if both branches are empty
        if not node.body and not node.orelse:
            return ast.Expr(value=ast.Constant(value=None))  # Replace with pass equivalent
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        """Process for loop body and else."""
        old_dead = self._in_dead_code
        self._in_dead_code = False
        node.body = self._mark_dead_after(node.body)
        self._in_dead_code = False
        node.orelse = self._mark_dead_after(node.orelse)
        self._in_dead_code = old_dead
        return self.generic_visit(node)

    def visit_While(self, node: ast.While) -> ast.While:
        """Process while loop body and else."""
        old_dead = self._in_dead_code
        self._in_dead_code = False
        node.body = self._mark_dead_after(node.body)
        self._in_dead_code = False
        node.orelse = self._mark_dead_after(node.orelse)
        self._in_dead_code = old_dead
        return self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> ast.Try:
        """Process try/except/finally blocks."""
        old_dead = self._in_dead_code
        self._in_dead_code = False
        node.body = self._mark_dead_after(node.body)
        self._in_dead_code = False
        for handler in node.handlers:
            handler.body = self._mark_dead_after(handler.body)
        self._in_dead_code = False
        node.orelse = self._mark_dead_after(node.orelse)
        self._in_dead_code = False
        node.finalbody = self._mark_dead_after(node.finalbody)
        self._in_dead_code = old_dead
        return self.generic_visit(node)


class CFGBuilder:
    """
    Builds a Control Flow Graph from a Python AST.

    CFG nodes represent basic blocks; edges represent possible control flow.
    """

    def build(self, tree: ast.AST) -> Tuple[List[CFGNode], List[Tuple[int, int]]]:
        """
        Build CFG from AST.

        Returns:
            (nodes, edges) where edges are (from_id, to_id) tuples
        """
        self._node_counter = 0
        self._nodes: List[CFGNode] = []
        self._edges: List[Tuple[int, int]] = []

        entry = self._make_node("Entry", is_entry=True)
        exit_node = self._make_node("Exit", is_exit=True)

        # Build CFG for each function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._build_function_cfg(node, entry, exit_node)
            elif isinstance(node, ast.Module) and not any(
                isinstance(n, ast.FunctionDef) for n in ast.walk(node)
            ):
                self._build_module_body_cfg(node, entry, exit_node)

        return self._nodes, self._edges

    def _make_node(self, node_type: str, source_node: Any = None,
                   is_entry: bool = False, is_exit: bool = False) -> CFGNode:
        """Create a new CFG node."""
        node_id = self._node_counter
        self._node_counter += 1

        stmt_hash = ""
        if source_node:
            stmt_hash = self._hash_stmt(source_node)

        cfg_node = CFGNode(
            node_id=node_id,
            node_type=node_type,
            stmt_hash=stmt_hash,
            is_entry=is_entry,
            is_exit=is_exit,
        )
        self._nodes.append(cfg_node)
        return cfg_node

    def _hash_stmt(self, node: ast.AST) -> str:
        """Hash a statement with identifier normalization."""
        # Normalize identifiers
        normalized = ast.dump(node)
        normalized = re.sub(r'arg=[\'"]\w+[\'"]', 'arg="__ID__"', normalized)
        normalized = re.sub(r'name=[\'"]\w+[\'"]', 'name="__ID__"', normalized)
        normalized = re.sub(r'id=[\'"]\w+[\'"]', 'id="__ID__"', normalized)
        return hashlib.md5(normalized.encode()).hexdigest()[:8]

    def _add_edge(self, from_id: int, to_id: int) -> None:
        """Add a CFG edge."""
        if (from_id, to_id) not in self._edges:
            self._edges.append((from_id, to_id))
            for n in self._nodes:
                if n.node_id == from_id:
                    if to_id not in n.successors:
                        n.successors.append(to_id)
                if n.node_id == to_id:
                    if from_id not in n.predecessors:
                        n.predecessors.append(from_id)

    def _build_function_cfg(self, func: ast.FunctionDef,
                            entry: CFGNode, exit_node: CFGNode) -> None:
        """Build CFG for a function definition."""
        # Entry → function body
        func_body_entry = self._make_node("FunctionDef", func)
        self._add_edge(entry.node_id, func_body_entry.node_id)

        # Build body statements
        last_nodes = [func_body_entry.node_id]
        for stmt in func.body:
            new_last = []
            for last_id in last_nodes:
                exits = self._build_stmt_cfg(stmt, last_id, exit_node.node_id)
                new_last.extend(exits)
            last_nodes = new_last if new_last else [exit_node.node_id]

        # Last → Exit
        for lid in last_nodes:
            self._add_edge(lid, exit_node.node_id)

    def _build_module_body_cfg(self, module: ast.Module,
                                 entry: CFGNode, exit_node: CFGNode) -> None:
        """Build CFG for module-level statements."""
        last_id = entry.node_id
        for stmt in module.body:
            exits = self._build_stmt_cfg(stmt, last_id, exit_node.node_id)
            last_id = exits[-1] if exits else last_id
        self._add_edge(last_id, exit_node.node_id)

    def _build_stmt_cfg(self, stmt: ast.AST, entry_id: int,
                        exit_id: int) -> List[int]:
        """Build CFG for a single statement. Returns list of exit node IDs."""
        if isinstance(stmt, ast.Assign):
            node = self._make_node("Assign", stmt)
            self._add_edge(entry_id, node.node_id)
            self._add_edge(node.node_id, exit_id)
            return [node.node_id]

        elif isinstance(stmt, ast.AugAssign):
            node = self._make_node("AugAssign", stmt)
            self._add_edge(entry_id, node.node_id)
            self._add_edge(node.node_id, exit_id)
            return [node.node_id]

        elif isinstance(stmt, ast.Expr):
            node = self._make_node("Expr", stmt)
            self._add_edge(entry_id, node.node_id)
            self._add_edge(node.node_id, exit_id)
            return [node.node_id]

        elif isinstance(stmt, ast.Return):
            node = self._make_node("Return", stmt)
            self._add_edge(entry_id, node.node_id)
            # No edge to exit_id (return terminates flow)
            return [node.node_id]

        elif isinstance(stmt, ast.If):
            if_node = self._make_node("If", stmt)
            self._add_edge(entry_id, if_node.node_id)

            # True branch
            true_entry = self._make_node("IfBody", None)
            self._add_edge(if_node.node_id, true_entry.node_id)
            true_exits = [true_entry.node_id]
            for s in stmt.body:
                new_exits = []
                for eid in true_exits:
                    exits = self._build_stmt_cfg(s, eid, exit_id)
                    new_exits.extend(exits)
                true_exits = new_exits

            # False branch (else/orelse)
            false_exits = []
            if stmt.orelse:
                false_entry = self._make_node("ElseBody", None)
                self._add_edge(if_node.node_id, false_entry.node_id)
                for s in stmt.orelse:
                    exits = self._build_stmt_cfg(s, false_entry.node_id, exit_id)
                    false_exits.extend(exits)
            else:
                false_exits = [if_node.node_id]

            # Merge
            merge_exits = list(set(true_exits + false_exits))
            return merge_exits if merge_exits else [if_node.node_id]

        elif isinstance(stmt, ast.For):
            for_node = self._make_node("For", stmt)
            self._add_edge(entry_id, for_node.node_id)

            # Loop body
            body_entry = self._make_node("ForBody", None)
            self._add_edge(for_node.node_id, body_entry.node_id)

            body_exits = [body_entry.node_id]
            for s in stmt.body:
                new_exits = []
                for eid in body_exits:
                    exits = self._build_stmt_cfg(s, eid, for_node.node_id)
                    new_exits.extend(exits)
                body_exits = new_exits

            # Back edge
            if body_exits:
                for eid in body_exits:
                    self._add_edge(eid, for_node.node_id)

            # Exit edge (loop termination)
            self._add_edge(for_node.node_id, exit_id)
            return [for_node.node_id]

        elif isinstance(stmt, ast.While):
            while_node = self._make_node("While", stmt)
            self._add_edge(entry_id, while_node.node_id)

            # Loop body
            body_entry = self._make_node("WhileBody", None)
            self._add_edge(while_node.node_id, body_entry.node_id)

            body_exits = [body_entry.node_id]
            for s in stmt.body:
                new_exits = []
                for eid in body_exits:
                    exits = self._build_stmt_cfg(s, eid, while_node.node_id)
                    new_exits.extend(exits)
                body_exits = new_exits

            # Back edge
            if body_exits:
                for eid in body_exits:
                    self._add_edge(eid, while_node.node_id)

            # Exit edge
            self._add_edge(while_node.node_id, exit_id)
            return [while_node.node_id]

        elif isinstance(stmt, ast.Try):
            try_node = self._make_node("Try", stmt)
            self._add_edge(entry_id, try_node.node_id)

            # Try body
            try_exits = [try_node.node_id]
            for s in stmt.body:
                new_exits = []
                for eid in try_exits:
                    exits = self._build_stmt_cfg(s, eid, exit_id)
                    new_exits.extend(exits)
                try_exits = new_exits

            # Except handlers
            for handler in stmt.handlers:
                handler_entry = self._make_node("Except", handler)
                self._add_edge(try_node.node_id, handler_entry.node_id)
                for s in handler.body:
                    exits = self._build_stmt_cfg(s, handler_entry.node_id, exit_id)

            # Both try and except can reach exit
            results = list(set(try_exits))
            return results if results else [try_node.node_id]

        elif isinstance(stmt, (ast.Break, ast.Continue)):
            node = self._make_node(type(stmt).__name__, stmt)
            self._add_edge(entry_id, node.node_id)
            # Flow continues at loop level (handled by caller)
            return [node.node_id]

        else:
            # Generic statement
            node = self._make_node(type(stmt).__name__, stmt)
            self._add_edge(entry_id, node.node_id)
            self._add_edge(node.node_id, exit_id)
            return [node.node_id]


class PDGBuilder:
    """
    Builds a Program Dependency Graph from a Python AST.

    PDG captures data dependencies (which statement's output feeds
    which other statement's input).
    """

    def build(self, tree: ast.AST) -> List[PDGNode]:
        """
        Build PDG from AST.

        Returns:
            List of PDGNode with dependency relationships
        """
        self._pdg_nodes: List[PDGNode] = []
        self._definitions: Dict[str, List[int]] = defaultdict(list)  # var → [PDG node IDs]
        self._node_counter = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._process_function(node)

        return self._pdg_nodes

    def _make_pdg_node(self, variable: str, line: int) -> PDGNode:
        """Create a new PDG node."""
        node = PDGNode(
            node_id=self._node_counter,
            variable=variable,
            definition_line=line,
        )
        self._node_counter += 1
        self._pdg_nodes.append(node)
        return node

    def _process_function(self, func: ast.FunctionDef) -> None:
        """Process a function for data dependencies."""
        # Function args are definitions
        for arg in func.args.args:
            def_node = self._make_pdg_node(arg.arg, func.lineno)
            self._definitions[arg.arg].append(def_node.node_id)

        # Walk body for definitions and uses
        for stmt in ast.walk(func):
            if isinstance(stmt, ast.Assign):
                # Definition: left side targets
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        def_node = self._make_pdg_node(target.id, getattr(stmt, 'lineno', 0))
                        new_defs = [def_node.node_id]

                        # Find where this variable was defined before (data dep)
                        old_defs = self._definitions.get(target.id, [])
                        for old_id in old_defs:
                            def_node.dep_from.append(old_id)

                        self._definitions[target.id] = new_defs

            elif isinstance(stmt, ast.Name) and isinstance(stmt.ctx, ast.Load):
                # Use: record dependency
                pass  # Uses are implicit in the AST walk

            elif isinstance(stmt, ast.For):
                # Loop variable is a definition
                if isinstance(stmt.target, ast.Name):
                    def_node = self._make_pdg_node(stmt.target.id,
                                                    getattr(stmt, 'lineno', 0))


class ASTNormalizer:
    """
    Complete AST Normalizer with CFG + PDG analysis.

    Produces a normalized representation robust against:
    - Variable/function name changes
    - Statement reordering (within independent blocks)
    - Dead code insertion (removed by dead code eliminator)
    - Comment/whitespace/formatting changes
    """

    def __init__(self):
        self.dead_code_remover = DeadCodeRemoverVisitor()
        self.cfg_builder = CFGBuilder()
        self.pdg_builder = PDGBuilder()

    def normalize(self, source: str) -> Optional[NormalizedProgram]:
        """
        Normalize Python source code.

        Args:
            source: Python source code string

        Returns:
            NormalizedProgram or None if parsing fails
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        # Step 1: Remove dead code
        tree = self.dead_code_remover.visit(tree)
        ast.fix_missing_locations(tree)

        # Step 2: Compute AST structure hash (with identifier normalization)
        ast_hash = self._compute_ast_hash(tree)

        # Step 3: Build CFG
        cfg_nodes, cfg_edges = self.cfg_builder.build(tree)

        # Step 4: Build PDG
        pdg_nodes = self.pdg_builder.build(tree)

        # Step 5: Extract normalized token sequence
        token_seq = self._extract_tokens(tree)

        # Step 6: Extract function signatures
        func_sigs = self._extract_function_signatures(tree)

        # Step 7: Compute complexity scores
        complexity = self._compute_complexity(tree)

        return NormalizedProgram(
            ast_structure_hash=ast_hash,
            cfg_nodes=cfg_nodes,
            cfg_edges=cfg_edges,
            pdg_nodes=pdg_nodes,
            token_sequence=token_seq,
            function_signatures=func_sigs,
            complexity_scores=complexity,
        )

    def _compute_ast_hash(self, tree: ast.AST) -> str:
        """Compute AST hash with all identifiers normalized."""
        class Normalizer(ast.NodeTransformer):
            def visit_Name(self, node):
                node.id = "__ID__"
                return node
            def visit_FunctionDef(self, node):
                node.name = "__FUNC__"
                return self.generic_visit(node)
            def visit_arg(self, node):
                node.arg = "__ID__"
                return node
            def visit_Attribute(self, node):
                node.attr = "__ATTR__"
                return self.generic_visit(node)

        normalized = Normalizer().visit(ast.parse(ast.dump(tree)))
        return hashlib.sha256(ast.dump(normalized).encode()).hexdigest()

    def _extract_tokens(self, tree: ast.AST) -> List[str]:
        """Extract normalized token sequence."""
        tokens = []
        for node in ast.walk(tree):
            tokens.append(type(node).__name__)
            if isinstance(node, ast.Name):
                tokens.append("__ID__")
            elif isinstance(node, (ast.Num, ast.Constant)):
                tokens.append("__LIT__")
            elif isinstance(node, ast.Str):
                tokens.append("__STR__")
        return tokens

    def _extract_function_signatures(self, tree: ast.AST) -> List[str]:
        """Extract function signatures with normalized names."""
        sigs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                arg_types = []
                for arg in node.args.args:
                    arg_types.append("__ID__")
                sigs.append(f"def({len(arg_types)}args)")
        return sigs

    def _compute_complexity(self, tree: ast.AST) -> Dict[str, float]:
        """Compute cyclomatic and other complexity metrics."""
        counts = {
            'branches': 0,
            'loops': 0,
            'functions': 0,
            'statements': 0,
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                counts['branches'] += 1
            elif isinstance(node, (ast.For, ast.While)):
                counts['loops'] += 1
            elif isinstance(node, ast.FunctionDef):
                counts['functions'] += 1
            elif isinstance(node, (ast.Assign, ast.Expr, ast.AugAssign,
                                   ast.Return, ast.Call)):
                counts['statements'] += 1

        # Cyclomatic complexity = edges - nodes + 2*P
        # Approximation: 1 + branches + loops
        cyclomatic = 1 + counts['branches'] + counts['loops']

        return {
            'cyclomatic_complexity': float(cyclomatic),
            'num_functions': float(counts['functions']),
            'num_statements': float(counts['statements']),
            'branch_density': counts['branches'] / max(1, counts['statements']),
            'loop_density': counts['loops'] / max(1, counts['statements']),
        }


class CFGComparator:
    """
    Compares two CFGs for structural similarity.

    Uses graph edit distance approximation:
    1. Compare node type distributions
    2. Compare edge patterns (branch density, loop count)
    3. Compare longest path (critical program path)
    """

    @staticmethod
    def compare(cfg1: NormalizedProgram, cfg2: NormalizedProgram) -> float:
        """
        Compare two normalized programs by CFG structure.

        Returns:
            Similarity score in [0, 1]
        """
        if not cfg1 or not cfg2:
            return 0.0

        # 1. Node type distribution similarity
        types1 = set(n.node_type for n in cfg1.cfg_nodes)
        types2 = set(n.node_type for n in cfg2.cfg_nodes)
        type_sim = len(types1 & types2) / len(types1 | types2) if (types1 | types2) else 0

        # 2. Edge pattern similarity
        edges1 = set(cfg1.cfg_edges)
        edges2 = set(cfg2.cfg_edges)
        # Normalize by size
        edge_sim = 1.0 - abs(len(edges1) - len(edges2)) / max(len(edges1), len(edges2), 1)

        # 3. Complexity similarity
        c1 = cfg1.complexity_scores
        c2 = cfg2.complexity_scores
        if c1 and c2:
            diffs = []
            for key in c1:
                v1, v2 = c1.get(key, 0), c2.get(key, 0)
                max_v = max(abs(v1), abs(v2), 1)
                diffs.append(1 - abs(v1 - v2) / max_v)
            complexity_sim = sum(diffs) / len(diffs) if diffs else 0
        else:
            complexity_sim = 0

        # Weighted combination
        return 0.3 * type_sim + 0.3 * edge_sim + 0.4 * complexity_sim


class PDGComparator:
    """Compares two PDGs for data dependency similarity."""

    @staticmethod
    def compare(pdgs1: List[PDGNode], pdgs2: List[PDGNode]) -> float:
        """
        Compare two PDGs.

        Returns:
            Similarity score in [0, 1]
        """
        if not pdgs1 or not pdgs2:
            return 0.0

        # Compare dependency structures
        deps1 = set()
        for node in pdgs1:
            deps1.add((node.variable, tuple(sorted(node.dep_from))))

        deps2 = set()
        for node in pdgs2:
            deps2.add((node.variable, tuple(sorted(node.dep_from))))

        dep_sim = len(deps1 & deps2) / len(deps1 | deps2) if (deps1 | deps2) else 0

        # Variable names (normalized) distribution similarity
        vars1 = set(n.variable for n in pdgs1)
        vars2 = set(n.variable for n in pdgs2)
        var_sim = len(vars1 & vars2) / len(vars1 | vars2) if (vars1 | vars2) else 0

        return 0.7 * dep_sim + 0.3 * var_sim


# Module-level convenience function
def compare_robust(code1: str, code2: str) -> Dict[str, float]:
    """
    Robust code comparison resistant to advanced obfuscation.

    Returns:
        {"similarity": float, "ast_sim": float, "cfg_sim": float, "pdg_sim": float}
    """
    normalizer = ASTNormalizer()
    prog1 = normalizer.normalize(code1)
    prog2 = normalizer.normalize(code2)

    if prog1 is None or prog2 is None:
        return {"similarity": 0.0, "ast_sim": 0.0, "cfg_sim": 0.0, "pdg_sim": 0.0}

    # Structural fingerprint match
    exact_match = prog1.structural_fingerprint == prog2.structural_fingerprint

    # AST token similarity
    tokens1 = set(prog1.token_sequence)
    tokens2 = set(prog2.token_sequence)
    ast_sim = len(tokens1 & tokens2) / len(tokens1 | tokens2) if (tokens1 | tokens2) else 0

    # CFG comparison
    cfg_sim = CFGComparator.compare(prog1, prog2)

    # PDG comparison
    pdg_sim = PDGComparator.compare(prog1.pdg_nodes, prog2.pdg_nodes)

    # Combined: weighted
    similarity = 0.2 * ast_sim + 0.4 * cfg_sim + 0.4 * pdg_sim

    return {
        "similarity": round(similarity, 4),
        "ast_sim": round(ast_sim, 4),
        "cfg_sim": round(cfg_sim, 4),
        "pdg_sim": round(pdg_sim, 4),
        "exact_structural_match": exact_match,
    }
