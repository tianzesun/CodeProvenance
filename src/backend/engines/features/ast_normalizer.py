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
2. Remove dead code (statements after return/raise/break/continue, constant ``if``)
3. Hash the AST structure with every identifier normalized
4. Build a Control Flow Graph (CFG)
5. Build a Program Dependency Graph (PDG)
6. Compare CFG/PDG similarity

This approach is robust because obfuscation that changes surface text
(renaming, reordering comments, inserting unreachable dead code)
will NOT change the CFG/PDG structure.
"""

import ast
import hashlib
import logging
import threading
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Hard ceiling on the number of CFG nodes built for a single program.
#: Building the graph is linear in statements, so this only trips on a
#: pathological module (a minified bundle, a generated data table). Refusing
#: such a graph is deliberate: it reports "no structural evidence" instead of
#: burning the worker for minutes on a run nobody can cancel.
MAX_CFG_NODES = 200_000


#: Maximum number of live exit nodes carried between consecutive statements.
#: A safety net only: statements are now built ONCE and joined, so exit lists
#: stay short (see ``CFGBuilder._build_block``).
MAX_PENDING_EXITS = 32

#: Total weight (roughly "graph elements") the normalization cache may hold.
_CACHE_MAX_WEIGHT = 2_000_000

_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)
_MATCH = getattr(ast, "Match", None)  # Python 3.10+


class CFGTooLargeError(RuntimeError):
    """Raised when a program exceeds :data:`MAX_CFG_NODES`."""


def _cap_exits(exits: list[int]) -> list[int]:
    """De-duplicate and cap a pending-exit list.

    Args:
        exits: Exit node ids collected while building one statement.

    Returns:
        The de-duplicated exits, at most :data:`MAX_PENDING_EXITS` of them.
    """
    unique = list(dict.fromkeys(exits))
    return unique[:MAX_PENDING_EXITS]


def _weighted_jaccard(left: Counter, right: Counter) -> float:
    """Multiset Jaccard: sum of minima over sum of maxima (0.0 when both empty)."""
    keys = left.keys() | right.keys()
    if not keys:
        return 0.0
    numerator = sum(min(left[k], right[k]) for k in keys)
    denominator = sum(max(left[k], right[k]) for k in keys)
    return numerator / denominator if denominator else 0.0


# ---------------------------------------------------------------------------
# Structure hashing
# ---------------------------------------------------------------------------

_CLOSE = object()


def _structure_hash(root: ast.AST, digest_size: int = 16) -> str:
    """Hash an AST's shape with identifiers normalized (iterative, non-mutating).

    Replaces two older approaches:

    * ``ast.parse(ast.dump(tree))`` — it re-parsed the *dump text* as Python
      source, so the "normalized" tree was a tree of ``Call`` nodes: identifiers
      survived as string constants (renamed code hashed differently), node names
      collapsed, and deep trees raised RecursionError.
    * ``ast.dump`` + regexes + MD5 — recursive, and MD5.

    This walks the tree once with an explicit stack, so depth is not limited by
    the interpreter recursion limit. Literal values stay in the hash on purpose
    (a changed constant changes the program); names do not.
    """
    digest = hashlib.blake2b(digest_size=digest_size)
    update = digest.update
    stack: list[Any] = [root]
    while stack:
        item = stack.pop()
        if item is _CLOSE:
            update(b")")
            continue
        if isinstance(item, str):  # a field label pushed below
            update(item.encode())
            continue

        node: ast.AST = item
        kind = type(node).__name__
        update(b"(" + kind.encode())
        children: list[Any] = []
        for field_name, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                children.append(("." + field_name + "=", [value]))
            elif isinstance(value, list):
                nodes = [v for v in value if isinstance(v, ast.AST)]
                scalars = [v for v in value if not isinstance(v, ast.AST)]
                if scalars:
                    update(f"[{field_name}:{scalars!r}]".encode())
                if nodes:
                    children.append(("." + field_name + "[]=", nodes))
            elif field_name in ("id", "arg"):
                update(b"|__ID__")
            elif field_name == "attr":
                update(b"|__ATTR__")
            elif field_name == "name" and isinstance(node, (*_FUNC_NODES,)):
                update(b"|__FUNC__")
            elif field_name == "name" and isinstance(node, ast.ClassDef):
                update(b"|__CLASS__")
            elif field_name == "name" and isinstance(node, ast.ExceptHandler):
                update(b"|__ID__")
            elif value is not None:
                update(f"|{field_name}={value!r}".encode())
        stack.append(_CLOSE)
        # Push in reverse so children pop in source order.
        for label, nodes in reversed(children):
            for child in reversed(nodes):
                stack.append(child)
            stack.append(label)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CFGNode:
    """Node in the Control Flow Graph."""

    node_id: int
    node_type: str
    stmt_hash: str  # Hash of normalized statement
    predecessors: list[int] = field(default_factory=list)
    successors: list[int] = field(default_factory=list)
    is_entry: bool = False
    is_exit: bool = False


@dataclass
class PDGNode:
    """Node in the Program Dependency Graph."""

    node_id: int
    variable: str
    definition_line: int
    uses: list[int] = field(default_factory=list)  # CFGNode IDs
    dep_from: list[int] = field(default_factory=list)  # PDGNode IDs (data deps)


@dataclass
class NormalizedProgram:
    """Fully normalized program representation."""

    ast_structure_hash: str
    cfg_nodes: list[CFGNode]
    cfg_edges: list[tuple[int, int]]
    pdg_nodes: list[PDGNode]
    token_sequence: list[str]
    function_signatures: list[str]
    complexity_scores: dict[str, float]

    @property
    def structural_fingerprint(self) -> str:
        """Compute a fingerprint robust to obfuscation.

        Variable names are NOT part of it: it used to include each PDG node's
        variable name, so renaming a variable changed the "obfuscation-robust"
        fingerprint and ``exact_structural_match`` could never survive a rename.
        """
        parts = [self.ast_structure_hash]
        parts.append(str(sorted(self.cfg_edges)))
        parts.append(
            str([tuple(sorted(n.node_id - d for d in n.dep_from)) for n in self.pdg_nodes])
        )
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Dead code removal
# ---------------------------------------------------------------------------


class DeadCodeRemover:
    """
    Detects and removes unreachable dead code.

    Dead code patterns:
    - Code after unconditional return/raise/break/continue
    - Branches guarded by a constant condition (``if False:``, ``while 0:``)
    """

    def visit(self, node: ast.AST) -> None:
        """Kept for backward compatibility; removal lives in the visitor."""

    @staticmethod
    def remove_dead_code(tree: ast.AST) -> ast.AST:
        """Remove unreachable code from AST."""
        return DeadCodeRemoverVisitor().visit(tree)


class DeadCodeRemoverVisitor(ast.NodeTransformer):
    """AST visitor that removes unreachable code.

    Stateless: it used to carry an ``_in_dead_code`` flag that leaked between
    blocks. After ``if x: return 1`` the flag was left set, so the *else* branch
    was judged dead and deleted, and later blocks were emptied the same way.
    Each block is now truncated on its own.
    """

    def __init__(self) -> None:
        self._in_dead_code = False  # unused; kept for backward compatibility

    @staticmethod
    def _truncate(body: list[ast.stmt]) -> list[ast.stmt]:
        """Cut a block after its first terminating statement."""
        result: list[ast.stmt] = []
        for stmt in body:
            result.append(stmt)
            if isinstance(stmt, _TERMINATORS):
                break
        return result

    def _mark_dead_after(self, body: list[ast.AST]) -> list[ast.AST]:
        """Remove statements after a return/raise/continue/break."""
        return self._truncate(body)  # type: ignore[arg-type]

    def _visit_block(self, body: list[ast.stmt]) -> list[ast.stmt]:
        """Visit every statement of a block, flatten hoisted lists, truncate."""
        out: list[ast.stmt] = []
        for stmt in self._truncate(body):
            result = self.visit(stmt)
            if result is None:
                continue
            if isinstance(result, list):
                out.extend(result)
            else:
                out.append(result)
        return self._truncate(out)  # a hoisted branch may end in a terminator

    def _prune_blocks(self, node: ast.AST) -> ast.AST:
        """Clean every statement block owned by ``node``.

        Previously only the top-level body of a function was cleaned, and each
        statement was passed to ``generic_visit`` (which visits a statement's
        *children*, never the statement itself), so dead code directly inside an
        ``if``/loop/``try`` body was never removed.
        """
        for name in ("body", "orelse", "finalbody"):
            block = getattr(node, name, None)
            if isinstance(block, list):
                setattr(node, name, self._visit_block(block))
        for handler in getattr(node, "handlers", None) or []:
            handler.body = self._visit_block(handler.body)
        for case in getattr(node, "cases", None) or []:
            case.body = self._visit_block(case.body)
        return node

    visit_Module = _prune_blocks
    visit_ClassDef = _prune_blocks
    visit_FunctionDef = _prune_blocks
    visit_AsyncFunctionDef = _prune_blocks
    visit_For = _prune_blocks
    visit_AsyncFor = _prune_blocks
    visit_With = _prune_blocks
    visit_AsyncWith = _prune_blocks
    visit_Try = _prune_blocks
    visit_TryStar = _prune_blocks
    visit_Match = _prune_blocks

    def visit_If(self, node: ast.If) -> Any:
        """Prune branches; collapse ``if <constant>`` to the branch that runs."""
        self._prune_blocks(node)
        if isinstance(node.test, ast.Constant):
            live = node.body if node.test.value else node.orelse
            return live or [ast.Pass()]
        if not node.body and not node.orelse:
            return ast.Pass()
        return node

    def visit_While(self, node: ast.While) -> Any:
        """Prune the loop; ``while <falsy constant>`` only ever runs its else."""
        self._prune_blocks(node)
        if isinstance(node.test, ast.Constant) and not node.test.value:
            return node.orelse or [ast.Pass()]
        return node


# ---------------------------------------------------------------------------
# Control flow graph
# ---------------------------------------------------------------------------


class CFGBuilder:
    """
    Builds a Control Flow Graph from a Python AST.

    CFG nodes represent statements; edges represent possible control flow.

    Each statement is built exactly once. When several paths reach it (the end
    of an ``if``/``else``, loop exits, ``break``s) all of them are joined onto
    its first node. The old builder rebuilt the *next* statement once per
    pending exit — duplicating nodes, growing the graph multiplicatively with
    branching, and making node counts depend on branching style rather than on
    the program — and it attached an edge from every simple statement to the
    function exit while giving ``return`` none.
    """

    def build(self, tree: ast.AST) -> tuple[list[CFGNode], list[tuple[int, int]]]:
        """
        Build CFG from AST.

        Returns:
            (nodes, edges) where edges are (from_id, to_id) tuples
        """
        self._node_counter = 0
        self._nodes: list[CFGNode] = []
        self._nodes_by_id: dict[int, CFGNode] = {}
        self._edges: list[tuple[int, int]] = []
        self._edge_keys: set[tuple[int, int]] = set()
        self._loops: list[tuple[int, list[int]]] = []  # (header id, break node ids)

        entry = self._make_node("Entry", is_entry=True)
        exit_node = self._make_node("Exit", is_exit=True)

        functions = [n for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        if functions:
            for func in functions:
                self._build_function_cfg(func, entry, exit_node)
        elif isinstance(tree, ast.Module):
            self._build_module_body_cfg(tree, entry, exit_node)

        return self._nodes, self._edges

    def _make_node(
        self,
        node_type: str,
        source_node: Any = None,
        is_entry: bool = False,
        is_exit: bool = False,
    ) -> CFGNode:
        """Create a new CFG node."""
        if self._node_counter >= MAX_CFG_NODES:
            raise CFGTooLargeError(f"control-flow graph exceeded {MAX_CFG_NODES} nodes")
        node_id = self._node_counter
        self._node_counter += 1

        cfg_node = CFGNode(
            node_id=node_id,
            node_type=node_type,
            stmt_hash=self._hash_stmt(source_node) if source_node else "",
            is_entry=is_entry,
            is_exit=is_exit,
        )
        self._nodes.append(cfg_node)
        self._nodes_by_id[node_id] = cfg_node
        return cfg_node

    def _hash_stmt(self, node: ast.AST) -> str:
        """Hash a statement with identifier normalization (8 hex chars)."""
        return _structure_hash(node, digest_size=4)

    def _add_edge(self, from_id: int, to_id: int) -> None:
        """Add a CFG edge (set-based de-duplication, id-indexed bookkeeping)."""
        key = (from_id, to_id)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self._edges.append(key)

        source = self._nodes_by_id.get(from_id)
        if source is not None and to_id not in source.successors:
            source.successors.append(to_id)
        target = self._nodes_by_id.get(to_id)
        if target is not None and from_id not in target.predecessors:
            target.predecessors.append(from_id)

    def _build_function_cfg(
        self, func: ast.FunctionDef | ast.AsyncFunctionDef, entry: CFGNode, exit_node: CFGNode
    ) -> None:
        """Build CFG for a function definition."""
        self._loops = []
        head = self._make_node("FunctionDef", func)
        self._add_edge(entry.node_id, head.node_id)
        exits = self._build_block(func.body, [head.node_id], exit_node.node_id)
        for node_id in exits:  # falling off the end of the function
            self._add_edge(node_id, exit_node.node_id)

    def _build_module_body_cfg(
        self, module: ast.Module, entry: CFGNode, exit_node: CFGNode
    ) -> None:
        """Build CFG for module-level statements.

        Uses the same block builder as functions. It used to follow only the
        LAST exit of each statement, silently dropping every other branch.
        """
        self._loops = []
        exits = self._build_block(module.body, [entry.node_id], exit_node.node_id)
        for node_id in exits:
            self._add_edge(node_id, exit_node.node_id)

    def _build_block(self, stmts: list[ast.stmt], entries: list[int], func_exit: int) -> list[int]:
        """Build a statement sequence; return the node ids that fall through its end."""
        current = _cap_exits(list(entries))
        for stmt in stmts:
            if not current:
                break  # nothing reaches here (after return/break): unreachable
            first_id = self._node_counter  # the statement's head node gets this id
            exits = self._build_stmt(stmt, current[0], func_exit)
            for extra in current[1:]:  # join the other incoming paths
                self._add_edge(extra, first_id)
            current = _cap_exits(exits)
        return current

    def _build_stmt(self, stmt: ast.stmt, entry_id: int, func_exit: int) -> list[int]:
        """Build one statement; return its fall-through exit node ids.

        The first node created is always the statement's own node.
        """
        if isinstance(stmt, (ast.Return, ast.Raise)):
            node = self._make_node(type(stmt).__name__, stmt)
            self._add_edge(entry_id, node.node_id)
            self._add_edge(node.node_id, func_exit)
            return []

        if isinstance(stmt, ast.Break):
            node = self._make_node("Break", stmt)
            self._add_edge(entry_id, node.node_id)
            if self._loops:
                self._loops[-1][1].append(node.node_id)  # joins the loop's exits
                return []
            return [node.node_id]

        if isinstance(stmt, ast.Continue):
            node = self._make_node("Continue", stmt)
            self._add_edge(entry_id, node.node_id)
            if self._loops:
                self._add_edge(node.node_id, self._loops[-1][0])  # back to the header
                return []
            return [node.node_id]

        if isinstance(stmt, ast.If):
            if_node = self._make_node("If", stmt)
            self._add_edge(entry_id, if_node.node_id)

            true_entry = self._make_node("IfBody", None)
            self._add_edge(if_node.node_id, true_entry.node_id)
            exits = self._build_block(stmt.body, [true_entry.node_id], func_exit)

            if stmt.orelse:
                false_entry = self._make_node("ElseBody", None)
                self._add_edge(if_node.node_id, false_entry.node_id)
                exits += self._build_block(stmt.orelse, [false_entry.node_id], func_exit)
            else:
                exits.append(if_node.node_id)  # condition false: skip the body
            return _cap_exits(exits)

        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            is_while = isinstance(stmt, ast.While)
            loop_node = self._make_node("While" if is_while else "For", stmt)
            self._add_edge(entry_id, loop_node.node_id)
            body_entry = self._make_node("WhileBody" if is_while else "ForBody", None)
            self._add_edge(loop_node.node_id, body_entry.node_id)

            breaks: list[int] = []
            self._loops.append((loop_node.node_id, breaks))
            body_exits = self._build_block(stmt.body, [body_entry.node_id], func_exit)
            self._loops.pop()
            for node_id in body_exits:  # back edge
                self._add_edge(node_id, loop_node.node_id)

            # Normal termination runs the ``else`` clause if there is one;
            # ``break`` skips it. (``orelse`` used to be ignored.)
            if stmt.orelse:
                exits = self._build_block(stmt.orelse, [loop_node.node_id], func_exit)
            else:
                exits = [loop_node.node_id]
            return _cap_exits(exits + breaks)

        if isinstance(stmt, ast.Try) or type(stmt).__name__ == "TryStar":
            try_node = self._make_node("Try", stmt)
            self._add_edge(entry_id, try_node.node_id)

            body_exits = self._build_block(stmt.body, [try_node.node_id], func_exit)
            normal = (
                self._build_block(stmt.orelse, body_exits, func_exit)
                if stmt.orelse and body_exits
                else body_exits
            )
            for handler in stmt.handlers:
                handler_entry = self._make_node("Except", handler)
                self._add_edge(try_node.node_id, handler_entry.node_id)
                # Handler exits used to be dropped, cutting the code after a
                # try/except off from every path through a handler.
                normal = normal + self._build_block(handler.body, [handler_entry.node_id], func_exit)
            normal = _cap_exits(normal)

            if stmt.finalbody:  # ``finally`` used to be ignored entirely
                finally_exits = self._build_block(
                    stmt.finalbody, normal or [try_node.node_id], func_exit
                )
                return _cap_exits(finally_exits) if normal else []
            return normal

        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            # The body used to be invisible: a generic node swallowed the whole
            # ``with`` block, so loops and branches inside it never reached the graph.
            node = self._make_node("With", stmt)
            self._add_edge(entry_id, node.node_id)
            return self._build_block(stmt.body, [node.node_id], func_exit)

        if _MATCH is not None and isinstance(stmt, _MATCH):
            match_node = self._make_node("Match", stmt)
            self._add_edge(entry_id, match_node.node_id)
            exits = [match_node.node_id]  # no case matched
            for case in stmt.cases:
                case_entry = self._make_node("Case", None)
                self._add_edge(match_node.node_id, case_entry.node_id)
                exits += self._build_block(case.body, [case_entry.node_id], func_exit)
            return _cap_exits(exits)

        # Simple statement (assignment, expression, import, def, ...).
        node = self._make_node(type(stmt).__name__, stmt)
        self._add_edge(entry_id, node.node_id)
        return [node.node_id]


# ---------------------------------------------------------------------------
# Program dependency graph
# ---------------------------------------------------------------------------


def _loads(expr: ast.AST | None) -> set[str]:
    """Names read anywhere inside ``expr``."""
    if expr is None:
        return set()
    return {
        n.id for n in ast.walk(expr) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }


def _stored_names(target: ast.AST) -> list[str]:
    """Names assigned by an assignment/for/with target (handles tuple unpacking)."""
    return [
        n.id for n in ast.walk(target) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    ]


class PDGBuilder:
    """
    Builds a Program Dependency Graph from a Python AST.

    A node is a variable definition; ``dep_from`` lists the definitions whose
    values flow into it (read-after-write data dependencies).

    Differences from the earlier version, which only linked a variable to its
    own previous definition:

    * real data dependencies: ``y = x + 1`` depends on the current definitions
      of ``x``;
    * definitions are tracked per scope, in program order (it shared one table
      across all functions and walked breadth-first, so same-named variables in
      different functions were linked together);
    * ``AugAssign``, ``AnnAssign``, tuple unpacking, ``for`` and ``with`` targets
      are definitions;
    * a script with no functions is analysed as one scope, as the CFG builder
      already does (it previously produced an empty PDG).
    """

    def build(self, tree: ast.AST) -> list[PDGNode]:
        """
        Build PDG from AST.

        Returns:
            List of PDGNode with dependency relationships
        """
        self._pdg_nodes: list[PDGNode] = []
        self._node_counter = 0

        functions = [n for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        if functions:
            for func in functions:
                self._process_function(func)
        elif isinstance(tree, ast.Module):
            self._visit_body(tree.body, {})
        return self._pdg_nodes

    def _make_pdg_node(self, variable: str, line: int) -> PDGNode:
        """Create a new PDG node."""
        node = PDGNode(node_id=self._node_counter, variable=variable, definition_line=line)
        self._node_counter += 1
        self._pdg_nodes.append(node)
        return node

    def _process_function(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Process one function scope."""
        defs: dict[str, list[int]] = {}
        args = func.args
        params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        params += [a for a in (args.vararg, args.kwarg) if a is not None]
        for arg in params:
            defs[arg.arg] = [self._make_pdg_node(arg.arg, func.lineno).node_id]
        self._visit_body(func.body, defs)

    def _define(self, name: str, line: int, uses: set[str], defs: dict[str, list[int]]) -> None:
        node = self._make_pdg_node(name, line)
        node.dep_from = sorted({i for used in uses for i in defs.get(used, ())})
        defs[name] = [node.node_id]  # this definition kills the previous ones

    @staticmethod
    def _merge(base: dict[str, list[int]], *branches: dict[str, list[int]]) -> dict[str, list[int]]:
        """Union of the definitions that may reach the join point of several branches."""
        merged: dict[str, list[int]] = defaultdict(list)
        for table in branches:
            for name, ids in table.items():
                merged[name].extend(ids)
        return {name: list(dict.fromkeys(ids)) for name, ids in merged.items()}

    def _visit_body(self, stmts: list[ast.stmt], defs: dict[str, list[int]]) -> None:
        for stmt in stmts:
            line = getattr(stmt, "lineno", 0)
            if isinstance(stmt, ast.Assign):
                uses = _loads(stmt.value)
                for target in stmt.targets:
                    if not isinstance(target, ast.Name):
                        uses |= _loads(target)  # ``a[i] = v`` reads ``a`` and ``i``
                for target in stmt.targets:
                    for name in _stored_names(target):
                        self._define(name, line, uses, defs)
            elif isinstance(stmt, ast.AnnAssign):
                if stmt.value is not None and isinstance(stmt.target, ast.Name):
                    self._define(stmt.target.id, line, _loads(stmt.value), defs)
            elif isinstance(stmt, ast.AugAssign):
                if isinstance(stmt.target, ast.Name):
                    uses = _loads(stmt.value) | {stmt.target.id}
                    self._define(stmt.target.id, line, uses, defs)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                uses = _loads(stmt.iter)
                for name in _stored_names(stmt.target):
                    self._define(name, line, uses, defs)
                self._visit_body(stmt.body, defs)
                self._visit_body(stmt.orelse, defs)
            elif isinstance(stmt, ast.While):
                self._visit_body(stmt.body, defs)
                self._visit_body(stmt.orelse, defs)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    if item.optional_vars is not None:
                        for name in _stored_names(item.optional_vars):
                            self._define(name, line, _loads(item.context_expr), defs)
                self._visit_body(stmt.body, defs)
            elif isinstance(stmt, ast.If):
                then_defs = {k: list(v) for k, v in defs.items()}
                self._visit_body(stmt.body, then_defs)
                else_defs = {k: list(v) for k, v in defs.items()}
                self._visit_body(stmt.orelse, else_defs)
                defs.clear()
                defs.update(self._merge(defs, then_defs, else_defs))
            elif isinstance(stmt, ast.Try) or type(stmt).__name__ == "TryStar":
                self._visit_body(stmt.body, defs)
                branches = [{k: list(v) for k, v in defs.items()}]
                for handler in stmt.handlers:
                    handler_defs = {k: list(v) for k, v in defs.items()}
                    self._visit_body(handler.body, handler_defs)
                    branches.append(handler_defs)
                merged = self._merge(defs, *branches)
                defs.clear()
                defs.update(merged)
                self._visit_body(stmt.orelse, defs)
                self._visit_body(stmt.finalbody, defs)
            # Nested function/class bodies are separate scopes, handled by ``build``.


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


class ASTNormalizer:
    """
    Complete AST Normalizer with CFG + PDG analysis.

    Produces a normalized representation robust against:
    - Variable/function name changes
    - Statement reordering (within independent blocks)
    - Dead code insertion (removed by dead code eliminator)
    - Comment/whitespace/formatting changes
    """

    def __init__(self) -> None:
        self.dead_code_remover = DeadCodeRemoverVisitor()
        # Kept as attributes for compatibility. ``normalize`` builds fresh
        # builders per call, because they hold per-build state and a shared
        # instance is not safe across threads.
        self.cfg_builder = CFGBuilder()
        self.pdg_builder = PDGBuilder()

    def normalize(self, source: str) -> NormalizedProgram | None:
        """
        Normalize Python source code.

        Args:
            source: Python source code string

        Returns:
            NormalizedProgram or None if parsing fails
        """
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            # ValueError: NUL bytes. RecursionError/MemoryError: pathological
            # nesting. None of them is a reason to fail a whole comparison.
            return None

        # Step 1: Remove dead code
        tree = self.dead_code_remover.visit(tree)
        ast.fix_missing_locations(tree)

        try:
            # Step 2: AST structure hash (identifiers normalized)
            ast_hash = _structure_hash(tree, digest_size=32)
            token_seq = self._extract_tokens(tree)
            func_sigs = self._extract_function_signatures(tree)
            complexity = self._compute_complexity(tree)
        except RecursionError:
            return None

        # Step 3: Build CFG
        try:
            cfg_nodes, cfg_edges = CFGBuilder().build(tree)
        except CFGTooLargeError as exc:
            # The graph is the expensive half of structural scoring. When it is
            # refused, keep the AST/token evidence and report no CFG/PDG signal
            # rather than spending minutes of worker time on it.
            logger.warning("Skipping CFG/PDG for oversized program: %s", exc)
            return NormalizedProgram(
                ast_structure_hash=ast_hash,
                cfg_nodes=[],
                cfg_edges=[],
                pdg_nodes=[],
                token_sequence=token_seq,
                function_signatures=func_sigs,
                complexity_scores=complexity,
            )

        # Step 4: Build PDG
        pdg_nodes = PDGBuilder().build(tree)

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
        """AST hash with all identifiers normalized (does not modify ``tree``)."""
        return _structure_hash(tree, digest_size=32)

    @staticmethod
    def _literal_token(value: Any) -> str:
        if isinstance(value, str):
            return "__STR__"
        if isinstance(value, bytes):
            return "__BYTES__"
        return "__LIT__"

    def _extract_tokens(self, tree: ast.AST) -> list[str]:
        """Extract normalized token sequence.

        ``ast.Num``/``ast.Str`` were removed in Python 3.14 (referencing them
        raised AttributeError and silently zeroed the whole comparison), and the
        ``(Num, Constant)`` test matched *every* constant, so ``__STR__`` was
        never produced.
        """
        tokens: list[str] = []
        for node in ast.walk(tree):
            tokens.append(type(node).__name__)
            if isinstance(node, ast.Name):
                tokens.append("__ID__")
            elif isinstance(node, ast.Constant):
                tokens.append(self._literal_token(node.value))
            elif isinstance(node, ast.JoinedStr):
                tokens.append("__STR__")
        return tokens

    def _extract_function_signatures(self, tree: ast.AST) -> list[str]:
        """Extract function signatures with normalized names."""
        sigs = []
        for node in ast.walk(tree):
            if isinstance(node, _FUNC_NODES):
                a = node.args
                count = len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)
                count += (a.vararg is not None) + (a.kwarg is not None)
                sigs.append(f"def({count}args)")
        return sigs

    def _compute_complexity(self, tree: ast.AST) -> dict[str, float]:
        """Compute cyclomatic and other complexity metrics."""
        branches = loops = functions = statements = extra_paths = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.stmt):
                # One definition of "statement". It used to count Expr AND the
                # Call inside it (twice) and skip With/Try/AnnAssign/etc.
                statements += 1
            if isinstance(node, ast.If):
                branches += 1
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                loops += 1
            elif isinstance(node, ast.ExceptHandler):
                extra_paths += 1
            elif isinstance(node, ast.IfExp):
                extra_paths += 1
            elif isinstance(node, ast.BoolOp):
                extra_paths += len(node.values) - 1
            if isinstance(node, _FUNC_NODES):
                functions += 1

        # Cyclomatic complexity ~ 1 + decision points
        cyclomatic = 1 + branches + loops + extra_paths
        return {
            "cyclomatic_complexity": float(cyclomatic),
            "num_functions": float(functions),
            "num_statements": float(statements),
            "branch_density": branches / max(1, statements),
            "loop_density": loops / max(1, statements),
        }


# ---------------------------------------------------------------------------
# Comparators
# ---------------------------------------------------------------------------


class CFGComparator:
    """
    Compares two CFGs for structural similarity.

    Combines:
    1. Node type distribution (multiset, not just the set of types seen)
    2. Edge count and in/out-degree distribution (independent of node numbering)
    3. Complexity metrics
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
        # An empty graph means structural evidence is unavailable (refused as
        # oversized), not that the two graphs agree.
        if not cfg1.cfg_nodes or not cfg2.cfg_nodes:
            return 0.0

        # 1. Node type distribution similarity
        type_sim = _weighted_jaccard(
            Counter(n.node_type for n in cfg1.cfg_nodes),
            Counter(n.node_type for n in cfg2.cfg_nodes),
        )

        # 2. Edge pattern similarity: edge-count ratio plus degree histograms
        edges1, edges2 = set(cfg1.cfg_edges), set(cfg2.cfg_edges)
        count_sim = 1.0 - abs(len(edges1) - len(edges2)) / max(len(edges1), len(edges2), 1)
        degree_sim = _weighted_jaccard(
            Counter((len(n.predecessors), len(n.successors)) for n in cfg1.cfg_nodes),
            Counter((len(n.predecessors), len(n.successors)) for n in cfg2.cfg_nodes),
        )
        edge_sim = 0.5 * count_sim + 0.5 * degree_sim

        # 3. Complexity similarity
        c1, c2 = cfg1.complexity_scores, cfg2.complexity_scores
        if c1 and c2:
            diffs = []
            for key in c1:
                v1, v2 = c1.get(key, 0), c2.get(key, 0)
                max_v = max(abs(v1), abs(v2), 1)
                diffs.append(1 - abs(v1 - v2) / max_v)
            complexity_sim = sum(diffs) / len(diffs) if diffs else 0
        else:
            complexity_sim = 0

        return 0.3 * type_sim + 0.3 * edge_sim + 0.4 * complexity_sim


class PDGComparator:
    """Compares two PDGs for data dependency similarity."""

    @staticmethod
    def _signatures(nodes: list[PDGNode]) -> Counter:
        """Per-node dependency shape that does not depend on absolute node ids.

        The old comparison used sets of raw node-id tuples, so two programs only
        matched if their numbering happened to coincide — adding one earlier
        function shifted every id and zeroed the match. Dependencies are now
        expressed as distances back from the node.
        """
        return Counter(tuple(sorted(n.node_id - d for d in n.dep_from)) for n in nodes)

    @staticmethod
    def compare(pdgs1: list[PDGNode], pdgs2: list[PDGNode]) -> float:
        """
        Compare two PDGs.

        Returns:
            Similarity score in [0, 1]
        """
        if not pdgs1 or not pdgs2:
            return 0.0

        dep_sim = _weighted_jaccard(PDGComparator._signatures(pdgs1), PDGComparator._signatures(pdgs2))
        count_sim = 1.0 - abs(len(pdgs1) - len(pdgs2)) / max(len(pdgs1), len(pdgs2), 1)
        return 0.8 * dep_sim + 0.2 * count_sim


# ---------------------------------------------------------------------------
# Cached normalization + public entry point
# ---------------------------------------------------------------------------

_MISSING = object()


class _ProgramCache:
    """Small thread-safe LRU of normalized programs, bounded by total weight.

    Comparing every pair of N files normalized each file N-1 times. Programs are
    treated as read-only by the comparators.
    """

    def __init__(self, max_weight: int = _CACHE_MAX_WEIGHT) -> None:
        self._max_weight = max_weight
        self._data: OrderedDict[str, tuple[NormalizedProgram | None, int]] = OrderedDict()
        self._weight = 0
        self._lock = threading.Lock()

    def get(self, source: str) -> Any:
        with self._lock:
            entry = self._data.get(source)
            if entry is None:
                return _MISSING
            self._data.move_to_end(source)
            return entry[0]

    def put(self, source: str, program: NormalizedProgram | None) -> None:
        weight = len(source) // 16 + 1
        if program is not None:
            weight += (
                len(program.token_sequence)
                + 2 * len(program.cfg_nodes)
                + len(program.cfg_edges)
                + len(program.pdg_nodes)
            )
        if weight > self._max_weight // 4:  # never let one huge file evict everything
            return
        with self._lock:
            if source in self._data:
                self._weight -= self._data.pop(source)[1]
            self._data[source] = (program, weight)
            self._weight += weight
            while self._weight > self._max_weight and self._data:
                _, (_, evicted) = self._data.popitem(last=False)
                self._weight -= evicted

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._weight = 0


_program_cache = _ProgramCache()


def normalize_cached(source: str) -> NormalizedProgram | None:
    """Normalize ``source``, reusing a previous result for identical text."""
    cached = _program_cache.get(source)
    if cached is not _MISSING:
        return cached
    program = ASTNormalizer().normalize(source)
    _program_cache.put(source, program)
    return program


def compare_robust(code1: str, code2: str) -> dict[str, Any]:
    """
    Robust code comparison resistant to advanced obfuscation.

    Returns:
        {"similarity", "ast_sim", "cfg_sim", "pdg_sim"} as floats plus
        ``exact_structural_match`` (bool).
    """
    prog1 = normalize_cached(code1)
    prog2 = normalize_cached(code2)

    if prog1 is None or prog2 is None:
        return {
            "similarity": 0.0,
            "ast_sim": 0.0,
            "cfg_sim": 0.0,
            "pdg_sim": 0.0,
            "exact_structural_match": False,
        }

    # Structural fingerprint match
    exact_match = prog1.structural_fingerprint == prog2.structural_fingerprint

    # AST token similarity: multiset overlap. The set of node-type NAMES is only
    # ~60 elements, so almost any two Python programs scored close to 1.
    ast_sim = _weighted_jaccard(Counter(prog1.token_sequence), Counter(prog2.token_sequence))

    cfg_sim = CFGComparator.compare(prog1, prog2)
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
