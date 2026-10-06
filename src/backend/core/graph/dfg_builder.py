"""
Data Flow Graph (DFG) Builder for Python AST.

This module analyzes a Python AST (along with its CFG) to construct a Data Flow
Graph that represents data dependencies between variable definitions and uses.

Approach
--------
1. A pre-pass builds a scope table (qualified names identical to the CFG's) with
   the names *bound* in each scope plus ``global``/``nonlocal`` declarations.
2. A walk mirrors the CFG's structure and creates DF nodes, anchoring each one
   to the CFG node of its statement (by AST identity, falling back to the
   narrowest enclosing line range).
3. Reaching definitions are computed over the CFG per (owner scope, variable);
   def->use edges come from that analysis. Uses of a variable owned by another
   scope (globals, closures) link flow-insensitively to every definition.
"""

from __future__ import annotations

import ast
import builtins
from typing import ClassVar

from ._ast_utils import source_for_node
from .models import (
    ControlFlowGraph,
    DataFlowGraph,
    DFEdge,
    DFNode,
    VariableState,
)

_MATCH = getattr(ast, "Match", None)


class ScopeInfo:
    """Tracks variables in one lexical scope.

    Attributes:
        name: Qualified scope name (``Class.method``), matching ``CFGNode.scope``
        parent: Enclosing scope
        kind: "module", "function" or "class"
        definitions: Variable name -> DF node IDs defined in this scope
        bound: Names bound (assigned, parameter, import, def, ...) here
        global_names / nonlocal_names: Declared ``global`` / ``nonlocal`` names
    """

    def __init__(
        self, name: str, parent: ScopeInfo | None = None, kind: str = "function"
    ) -> None:
        self.name = name
        self.parent = parent
        self.kind = kind
        self.definitions: dict[str, list[int]] = {}
        self.bound: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def add_definition(self, var_name: str, node_id: int) -> None:
        """Record a variable definition in this scope."""
        self.definitions.setdefault(var_name, []).append(node_id)

    def get_definitions(self, var_name: str) -> list[int]:
        """Get all definitions of a variable, searching parent scopes."""
        if var_name in self.definitions:
            return self.definitions[var_name]
        if self.parent:
            return self.parent.get_definitions(var_name)
        return []


def _param_names(args: ast.arguments) -> list[ast.arg]:
    """All parameters (the old code saw only ``args.args``: no kw-only,
    positional-only, ``*args`` or ``**kwargs``)."""
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg:
        params.append(args.vararg)
    if args.kwarg:
        params.append(args.kwarg)
    return params


def _pattern_captures(pattern: ast.AST) -> list[str]:
    names: list[str] = []
    for n in ast.walk(pattern):
        kind = type(n).__name__
        if kind in ("MatchAs", "MatchStar") and getattr(n, "name", None):
            names.append(n.name)  # type: ignore[attr-defined]
        elif kind == "MatchMapping" and getattr(n, "rest", None):
            names.append(n.rest)  # type: ignore[attr-defined]
    return names


class DataFlowGraphBuilder:
    """Builds a Data Flow Graph from a Python AST and its CFG.

    Usage:
        dfg_builder = DataFlowGraphBuilder()
        dfg = dfg_builder.build(tree, cfg, source_code)

    A builder instance is reusable but not thread-safe.
    """

    # All builtin names. A builtin name is skipped only when the program never
    # binds it: ``sum = 0`` / ``max = x`` / ``list = []`` are ordinary variables
    # (the old code ignored them entirely).
    BUILTINS: ClassVar[frozenset[str]] = frozenset(dir(builtins)) | {
        "quit",
        "exit",
        "copyright",
        "credits",
        "license",
    }

    def __init__(self) -> None:
        self._node_counter = 0
        self._comp_counter = 0
        self._scopes: dict[str, ScopeInfo] = {}
        self._current_scope = "global"
        self._source_lines: list[str] = []
        self._cfg: ControlFlowGraph | None = None
        self._cfg_index: dict[int, dict[str, int]] = {}
        # context of the statement currently being visited
        self._anchor: ast.AST | None = None
        self._pref: str | None = None
        self._stmt_source = ""
        self._stmt_line = 0

    # ── public API ──────────────────────────────────────────────────

    def build(
        self,
        tree: ast.Module,
        cfg: ControlFlowGraph,
        source_code: str = "",
    ) -> DataFlowGraph:
        """Build a DFG from AST and CFG."""
        root = ScopeInfo("global", None, "module")
        return self._run(root, tree.body, None, cfg, source_code)

    def build_for_function(
        self,
        func_def: ast.FunctionDef | ast.AsyncFunctionDef,
        cfg: ControlFlowGraph,
        source_code: str = "",
    ) -> DataFlowGraph:
        """Build a DFG for a specific function (CFG from ``build_from_function``)."""
        root = ScopeInfo(func_def.name, None, "function")
        return self._run(root, func_def.body, func_def, cfg, source_code)

    def build_for_class(
        self,
        class_def: ast.ClassDef,
        cfg: ControlFlowGraph,
        source_code: str = "",
    ) -> DataFlowGraph:
        """Build a DFG for a class body (CFG from ``build_from_class``)."""
        root = ScopeInfo(class_def.name, None, "class")
        return self._run(root, class_def.body, None, cfg, source_code)

    # ── driver ──────────────────────────────────────────────────────

    def _run(
        self,
        root: ScopeInfo,
        body: list[ast.stmt],
        func_def: ast.FunctionDef | ast.AsyncFunctionDef | None,
        cfg: ControlFlowGraph,
        source_code: str,
    ) -> DataFlowGraph:
        self._node_counter = 0
        self._comp_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        self._cfg = cfg
        self._scopes = {root.name: root}
        self._current_scope = root.name
        self._index_cfg(cfg)

        if func_def is not None:
            root.bound.update(a.arg for a in _param_names(func_def.args))
        self._scan_block(body, root)
        # `global x` + assignment inside a function binds x in the module scope.
        module = self._scopes.get("global")
        if module is not None:
            for scope in self._scopes.values():
                module.bound |= scope.global_names & scope.bound

        dfg = DataFlowGraph(cfg_reference=cfg, source_code=source_code)

        if func_def is not None:
            self._at(func_def, func_def, "FunctionEntry")
            for arg in _param_names(func_def.args):
                self._emit_def(dfg, arg.arg, line=getattr(arg, "lineno", 0))
        self._visit_block(body, dfg)

        self._build_def_use_chains(dfg, cfg)
        return dfg

    # ── pass 1: scope table ─────────────────────────────────────────

    def _qualify(self, parent: ScopeInfo, name: str) -> str:
        return name if parent.name == "global" else f"{parent.name}.{name}"

    def _bind_names(self, target: ast.AST, scope: ScopeInfo) -> None:
        if isinstance(target, ast.Name):
            scope.bound.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._bind_names(elt, scope)
        elif isinstance(target, ast.Starred):
            self._bind_names(target.value, scope)

    def _scan_walrus(self, stmt: ast.AST, scope: ScopeInfo) -> None:
        for name, value in ast.iter_fields(stmt):
            if name in ("body", "orelse", "finalbody", "handlers", "cases"):
                continue
            children = value if isinstance(value, list) else [value]
            for child in children:
                if isinstance(child, ast.AST) and not isinstance(child, ast.stmt):
                    for n in ast.walk(child):
                        if isinstance(n, ast.NamedExpr) and isinstance(
                            n.target, ast.Name
                        ):
                            scope.bound.add(n.target.id)

    def _scan_block(self, stmts: list[ast.stmt], scope: ScopeInfo) -> None:
        for stmt in stmts:
            self._scan_stmt(stmt, scope)

    def _scan_stmt(self, stmt: ast.stmt, scope: ScopeInfo) -> None:
        self._scan_walrus(stmt, scope)
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope.bound.add(stmt.name)
            child = ScopeInfo(self._qualify(scope, stmt.name), scope, "function")
            child.bound.update(a.arg for a in _param_names(stmt.args))
            self._scopes[child.name] = child
            self._scan_block(stmt.body, child)
        elif isinstance(stmt, ast.ClassDef):
            scope.bound.add(stmt.name)
            child = ScopeInfo(self._qualify(scope, stmt.name), scope, "class")
            self._scopes[child.name] = child
            self._scan_block(stmt.body, child)
        elif isinstance(stmt, ast.Global):
            scope.global_names.update(stmt.names)
        elif isinstance(stmt, ast.Nonlocal):
            scope.nonlocal_names.update(stmt.names)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                self._bind_names(target, scope)
        elif isinstance(stmt, ast.AugAssign):
            self._bind_names(stmt.target, scope)
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                self._bind_names(stmt.target, scope)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            self._bind_names(stmt.target, scope)
            self._scan_block(stmt.body, scope)
            self._scan_block(stmt.orelse, scope)
        elif isinstance(stmt, (ast.While, ast.If)):
            self._scan_block(stmt.body, scope)
            self._scan_block(stmt.orelse, scope)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if item.optional_vars is not None:
                    self._bind_names(item.optional_vars, scope)
            self._scan_block(stmt.body, scope)
        elif isinstance(stmt, ast.Try) or type(stmt).__name__ == "TryStar":
            self._scan_block(stmt.body, scope)  # type: ignore[attr-defined]
            for handler in stmt.handlers:  # type: ignore[attr-defined]
                if handler.name:
                    scope.bound.add(handler.name)
                self._scan_block(handler.body, scope)
            self._scan_block(stmt.orelse, scope)  # type: ignore[attr-defined]
            self._scan_block(stmt.finalbody, scope)  # type: ignore[attr-defined]
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                scope.bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                if alias.name != "*":
                    scope.bound.add(alias.asname or alias.name)
        elif _MATCH is not None and isinstance(stmt, _MATCH):
            for case in stmt.cases:
                scope.bound.update(_pattern_captures(case.pattern))
                self._scan_block(case.body, scope)

    def _resolve(self, scope_name: str, var: str) -> str | None:
        """Name of the scope that owns ``var`` as seen from ``scope_name``."""
        scope = self._scopes.get(scope_name)
        if scope is None:
            return None
        if var in scope.global_names:
            return "global"
        if var in scope.nonlocal_names:
            parent = scope.parent
            while parent is not None:
                if parent.kind == "function" and var in parent.bound:
                    return parent.name
                parent = parent.parent
            return None
        if var in scope.bound:
            return scope.name
        parent = scope.parent  # free variable: class scopes are not visible
        while parent is not None:
            if (
                parent.kind != "class"
                and var in parent.bound
                and var not in parent.global_names
            ):
                return parent.name
            parent = parent.parent
        return None

    # ── CFG anchoring ───────────────────────────────────────────────

    def _index_cfg(self, cfg: ControlFlowGraph) -> None:
        self._cfg_index = {}
        for node_id, node in cfg.nodes.items():
            if node.ast_node is not None:
                self._cfg_index.setdefault(id(node.ast_node), {}).setdefault(
                    node.node_type, node_id
                )

    def _find_cfg_node_for_line(self, cfg: ControlFlowGraph, line: int) -> int:
        """CFG node with the *narrowest* span containing ``line`` (else entry).

        The old version returned the first node whose span contained the line,
        which was typically an enclosing def/loop rather than the statement.
        """
        best: tuple[int, int] | None = None
        best_id = cfg.entry_node or 0
        for node_id, node in cfg.nodes.items():
            if not node.line_start:
                continue
            end = node.line_end or node.line_start
            if node.line_start <= line <= end:
                key = (end - node.line_start, node_id)
                if best is None or key < best:
                    best, best_id = key, node_id
        return best_id

    def _cfg_id(self, line: int) -> int:
        cfg = self._cfg
        assert cfg is not None
        entry = (
            self._cfg_index.get(id(self._anchor)) if self._anchor is not None else None
        )
        if entry:
            if self._pref in entry:
                return entry[self._pref]  # type: ignore[index]
            return next(iter(entry.values()))
        return self._find_cfg_node_for_line(cfg, line or self._stmt_line)

    def _at(
        self, stmt: ast.AST, anchor: ast.AST | None = None, pref: str | None = None
    ) -> None:
        """Set the context (CFG anchor + source text) for the following emits."""
        self._anchor = anchor if anchor is not None else stmt
        self._pref = pref
        self._stmt_source = self._get_source_line(stmt)
        self._stmt_line = getattr(self._anchor, "lineno", 0) or getattr(
            stmt, "lineno", 0
        )

    # ── node creation ───────────────────────────────────────────────

    def _is_ignored_name(self, name: str) -> bool:
        return name == "_" or (
            len(name) > 4 and name.startswith("__") and name.endswith("__")
        )

    def _is_user_variable(self, name: str) -> bool:
        """Should an *unbound* name be tracked? (not a dunder / builtin)"""
        return not self._is_ignored_name(name) and name not in self.BUILTINS

    def _create_df_node(
        self,
        variable_name: str,
        state: VariableState,
        cfg_node_id: int = 0,
        line_number: int = 0,
        source_code: str = "",
        scope: str = "global",
    ) -> DFNode:
        self._node_counter += 1
        return DFNode(
            id=self._node_counter,
            variable_name=variable_name,
            state=state,
            cfg_node_id=cfg_node_id,
            line_number=line_number,
            source_code=source_code,
            scope=scope,
        )

    def _emit(
        self,
        dfg: DataFlowGraph,
        name: str,
        state: VariableState,
        owner: str | None,
        line: int,
        extra: dict | None = None,
    ) -> DFNode:
        node = self._create_df_node(
            variable_name=name,
            state=state,
            cfg_node_id=self._cfg_id(line),
            line_number=line or self._stmt_line,
            source_code=self._stmt_source,
            scope=self._current_scope,
        )
        node.metadata["owner"] = owner
        if extra:
            node.metadata.update(extra)
        dfg.add_node(node)
        if state in (VariableState.DEFINED, VariableState.MODIFIED):
            scope = self._scopes.get(self._current_scope)
            if scope is not None:
                scope.add_definition(name, node.id)
        return node

    def _emit_def(
        self,
        dfg: DataFlowGraph,
        name: str,
        *,
        state: VariableState = VariableState.DEFINED,
        owner: str | None = None,
        line: int = 0,
        extra: dict | None = None,
    ) -> DFNode | None:
        if self._is_ignored_name(name):
            return None
        if owner is None:
            owner = self._resolve(self._current_scope, name) or self._current_scope
        return self._emit(dfg, name, state, owner, line, extra)

    def _emit_use(
        self, dfg: DataFlowGraph, node: ast.Name, shadow: dict[str, str]
    ) -> DFNode | None:
        name = node.id
        if self._is_ignored_name(name):
            return None
        if name in shadow:
            owner: str | None = shadow[name]
        else:
            owner = self._resolve(self._current_scope, name)
            if owner is None and name in self.BUILTINS:
                return None
        return self._emit(
            dfg, name, VariableState.USED, owner, getattr(node, "lineno", 0)
        )

    # ── pass 2: expression / statement walk ─────────────────────────

    def _collect_uses(
        self,
        node: ast.AST | None,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph | None = None,
    ) -> None:
        """Collect variable uses in an expression subtree."""
        if node is not None:
            self._visit_expr(node, dfg, {})

    def _visit_expr(
        self, node: ast.AST, dfg: DataFlowGraph, shadow: dict[str, str]
    ) -> None:
        if isinstance(node, ast.Name):
            # Store-context names are bindings handled by the enclosing statement;
            # the old walker counted them as uses too.
            if isinstance(node.ctx, (ast.Load, ast.Del)):
                self._emit_use(dfg, node, shadow)
        elif isinstance(
            node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
        ):
            self._visit_comprehension(node, dfg, shadow)
        elif isinstance(node, ast.Lambda):
            self._visit_lambda(node, dfg, shadow)
        elif isinstance(node, ast.NamedExpr):
            self._visit_expr(node.value, dfg, shadow)
            self._bind_target(node.target, dfg, shadow=shadow)
        else:
            # `obj.attr` is one use of `obj` (the old walker produced two).
            for child in ast.iter_child_nodes(node):
                self._visit_expr(child, dfg, shadow)

    def _visit_comprehension(
        self, node, dfg: DataFlowGraph, shadow: dict[str, str]
    ) -> None:
        """Comprehension variables are private: they shadow outer names."""
        self._comp_counter += 1
        owner = f"{self._current_scope}.<comp{self._comp_counter}>"
        inner = dict(shadow)
        for index, gen in enumerate(node.generators):
            self._visit_expr(gen.iter, dfg, shadow if index == 0 else inner)
            self._bind_target(gen.target, dfg, owner=owner, shadow=inner, comp=True)
            for cond in gen.ifs:
                self._visit_expr(cond, dfg, inner)
        if isinstance(node, ast.DictComp):
            self._visit_expr(node.key, dfg, inner)
            self._visit_expr(node.value, dfg, inner)
        else:
            self._visit_expr(node.elt, dfg, inner)

    def _visit_lambda(
        self, node: ast.Lambda, dfg: DataFlowGraph, shadow: dict[str, str]
    ) -> None:
        self._comp_counter += 1
        owner = f"{self._current_scope}.<lambda{self._comp_counter}>"
        for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d]]:
            self._visit_expr(default, dfg, shadow)
        inner = dict(shadow)
        for arg in _param_names(node.args):
            self._emit_def(
                dfg,
                arg.arg,
                owner=owner,
                line=getattr(arg, "lineno", 0),
                extra={"local_only": True},
            )
            inner[arg.arg] = owner
        self._visit_expr(node.body, dfg, inner)

    def _bind_target(
        self,
        target: ast.AST,
        dfg: DataFlowGraph,
        *,
        owner: str | None = None,
        shadow: dict[str, str] | None = None,
        comp: bool = False,
        state: VariableState = VariableState.DEFINED,
    ) -> None:
        """Define the names bound by an assignment target.

        Attribute/subscript targets (``a.b = v``, ``a[i] = v``) define nothing
        but *use* their sub-expressions; the old code ignored subscript targets
        and nested tuple/starred unpacking altogether.
        """
        if isinstance(target, ast.Name):
            node = self._emit_def(
                dfg,
                target.id,
                state=state,
                owner=owner,
                line=getattr(target, "lineno", 0),
                extra={"comprehension": True} if comp else None,
            )
            if shadow is not None and owner is not None and node is not None:
                shadow[target.id] = owner
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._bind_target(elt, dfg, owner=owner, shadow=shadow, comp=comp)
        elif isinstance(target, ast.Starred):
            self._bind_target(target.value, dfg, owner=owner, shadow=shadow, comp=comp)
        else:
            self._visit_expr(target, dfg, shadow or {})

    def _visit_block(self, stmts: list[ast.stmt], dfg: DataFlowGraph) -> None:
        for stmt in stmts:
            self._visit_stmt(stmt, dfg)

    def _visit_stmt(self, stmt: ast.stmt, dfg: DataFlowGraph) -> None:
        if isinstance(stmt, ast.Assign):
            self._at(stmt)
            self._collect_uses(stmt.value, dfg)
            for target in stmt.targets:
                self._bind_target(target, dfg)
        elif isinstance(stmt, ast.AugAssign):
            self._at(stmt)
            self._collect_uses(stmt.value, dfg)
            if isinstance(stmt.target, ast.Name):
                # read-modify-write: a definition and a use of the old value
                self._emit_def(
                    dfg,
                    stmt.target.id,
                    state=VariableState.MODIFIED,
                    line=getattr(stmt, "lineno", 0),
                )
            else:
                self._visit_expr(stmt.target, dfg, {})
        elif isinstance(stmt, ast.AnnAssign):
            self._at(stmt)
            if stmt.value is not None:  # a bare annotation defines nothing
                self._collect_uses(stmt.value, dfg)
                self._bind_target(stmt.target, dfg)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            self._at(stmt)
            self._collect_uses(stmt.iter, dfg)
            self._bind_target(stmt.target, dfg)
            self._visit_block(stmt.body, dfg)
            self._visit_block(stmt.orelse, dfg)
        elif isinstance(stmt, ast.While):
            self._at(stmt, stmt.test, "WhileCondition")
            self._collect_uses(stmt.test, dfg)
            self._visit_block(stmt.body, dfg)
            self._visit_block(stmt.orelse, dfg)
        elif isinstance(stmt, ast.If):
            self._at(stmt, stmt.test, "Condition")
            self._collect_uses(stmt.test, dfg)
            self._visit_block(stmt.body, dfg)
            self._visit_block(stmt.orelse, dfg)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            self._at(stmt)
            for item in stmt.items:
                self._collect_uses(item.context_expr, dfg)
                if item.optional_vars is not None:
                    self._bind_target(item.optional_vars, dfg)
            self._visit_block(stmt.body, dfg)
        elif isinstance(stmt, ast.Try) or type(stmt).__name__ == "TryStar":
            self._visit_block(stmt.body, dfg)  # type: ignore[attr-defined]
            for handler in stmt.handlers:  # type: ignore[attr-defined]
                self._at(handler)
                self._collect_uses(handler.type, dfg)
                if handler.name:
                    self._emit_def(
                        dfg, handler.name, line=getattr(handler, "lineno", 0)
                    )
                self._visit_block(handler.body, dfg)
            self._visit_block(stmt.orelse, dfg)  # type: ignore[attr-defined]
            self._visit_block(stmt.finalbody, dfg)  # type: ignore[attr-defined]
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._visit_function(stmt, dfg)
        elif isinstance(stmt, ast.ClassDef):
            self._visit_class(stmt, dfg)
        elif isinstance(stmt, ast.Import):
            self._at(stmt)
            for alias in stmt.names:
                self._emit_def(
                    dfg, alias.asname or alias.name.split(".")[0], line=stmt.lineno
                )
        elif isinstance(stmt, ast.ImportFrom):
            self._at(stmt)
            for alias in stmt.names:
                if alias.name != "*":
                    self._emit_def(dfg, alias.asname or alias.name, line=stmt.lineno)
        elif isinstance(
            stmt, (ast.Global, ast.Nonlocal, ast.Pass, ast.Break, ast.Continue)
        ):
            return
        elif _MATCH is not None and isinstance(stmt, _MATCH):
            self._visit_match(stmt, dfg)
        else:  # Expr, Return, Raise, Assert, Delete, ...
            self._at(stmt)
            self._collect_uses(stmt, dfg)

    def _visit_function(self, node, dfg: DataFlowGraph) -> None:
        self._at(node, node, "FunctionDef")
        # decorators and defaults run at definition time, in the enclosing scope
        for expr in node.decorator_list:
            self._collect_uses(expr, dfg)
        for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d]]:
            self._collect_uses(default, dfg)
        self._emit_def(dfg, node.name, line=node.lineno)

        outer = self._current_scope
        self._current_scope = node.name if outer == "global" else f"{outer}.{node.name}"
        self._at(node, node, "FunctionEntry")
        for arg in _param_names(node.args):
            self._emit_def(dfg, arg.arg, line=getattr(arg, "lineno", 0))
        self._visit_block(node.body, dfg)
        self._current_scope = outer

    def _visit_class(self, node: ast.ClassDef, dfg: DataFlowGraph) -> None:
        self._at(node, node, "ClassDef")
        for expr in [
            *node.decorator_list,
            *node.bases,
            *[k.value for k in node.keywords],
        ]:
            self._collect_uses(expr, dfg)
        self._emit_def(dfg, node.name, line=node.lineno)

        outer = self._current_scope
        self._current_scope = node.name if outer == "global" else f"{outer}.{node.name}"
        self._visit_block(node.body, dfg)
        self._current_scope = outer

    def _visit_match(self, node, dfg: DataFlowGraph) -> None:
        self._at(node, node.subject, "Match")
        self._collect_uses(node.subject, dfg)
        for case in node.cases:
            self._at(case.pattern, case.pattern, "MatchCase")
            for n in ast.walk(case.pattern):
                kind = type(n).__name__
                if kind == "MatchValue":
                    self._collect_uses(n.value, dfg)
                elif kind == "MatchClass":
                    self._collect_uses(n.cls, dfg)
                elif kind == "MatchMapping":
                    for key in n.keys:
                        self._collect_uses(key, dfg)
            for name in _pattern_captures(case.pattern):
                self._emit_def(dfg, name, line=getattr(case.pattern, "lineno", 0))
            self._collect_uses(case.guard, dfg)
            self._visit_block(case.body, dfg)

    # ── def-use chains ──────────────────────────────────────────────

    def _build_def_use_chains(self, dfg: DataFlowGraph, cfg: ControlFlowGraph) -> None:
        """Create def -> use edges from reaching definitions.

        The old heuristic linked a use to *every* earlier-line definition of the
        name: it ignored kills (``x=1; x=2; use(x)`` got two edges), loops
        (a def later in the body never reached an earlier use), branches, and
        never connected a def to the read half of ``x += 1``.
        """
        reaching = dfg.compute_reaching_definitions()
        defining = (VariableState.DEFINED, VariableState.MODIFIED)
        defs_by_key: dict[tuple[str, str], list[DFNode]] = {}
        for node in dfg.nodes.values():
            if node.state in defining:
                defs_by_key.setdefault(node.key, []).append(node)

        seen: set[tuple[int, int]] = set()
        for use in sorted(dfg.nodes.values(), key=lambda n: n.id):
            if use.state not in (VariableState.USED, VariableState.MODIFIED):
                continue
            owner = use.metadata.get("owner")
            if owner is None:
                continue  # unresolved name (e.g. star-import): nothing to link
            candidates = defs_by_key.get(use.key, [])

            if use.scope == owner:  # flow-sensitive within the owning scope
                # A MODIFIED node may legitimately depend on itself (loop-carried).
                sources = sorted(reaching.get(use.id, ()))
                if not sources:  # e.g. module code reading a global set in a function
                    sources = [d.id for d in candidates if d.scope != use.scope]
            else:  # global / closure / comprehension variable: any definition may reach
                sources = [d.id for d in candidates if d.id != use.id]

            for source_id in sources:
                if (source_id, use.id) not in seen:
                    seen.add((source_id, use.id))
                    dfg.add_edge(
                        DFEdge(
                            source=source_id, target=use.id, variable=use.variable_name
                        )
                    )

    def _get_scope(self) -> ScopeInfo:
        return self._scopes[self._current_scope]

    def _get_source_line(self, node: ast.AST) -> str:
        """Source text of a node (header only for compound statements)."""
        return source_for_node(self._source_lines, node)


def build_dfg(
    tree: ast.Module,
    cfg: ControlFlowGraph,
    source_code: str = "",
) -> DataFlowGraph:
    """Convenience function to build a DFG from AST and CFG."""
    return DataFlowGraphBuilder().build(tree, cfg, source_code)
