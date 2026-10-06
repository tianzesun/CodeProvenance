"""
Control Flow Graph (CFG) Builder for Python AST.

This module traverses a Python AST and constructs a Control Flow Graph
that represents all possible execution paths through the code.

Design notes
------------
* Every edge is typed (TRUE_BRANCH / FALSE_BRANCH / LOOP_BACK / LOOP_EXIT /
  BREAK / CONTINUE / EXCEPTION / FUNCTION_RETURN ...). Handlers return the
  *pending* exits ``(node_id, edge_type)`` of a statement, so the type of the
  edge that eventually leaves it is preserved.
* ``return``/``raise`` are wired to the exit node (or to exception handlers),
  ``break`` to the loop exit and ``continue`` to the loop header.
* A nested ``def`` is a single statement in the enclosing flow; its body is a
  separate sub-graph (FunctionEntry ... FunctionExit) hanging off the def node
  via a FUNCTION_CALL edge, because the body does not run at definition time.
  A class body *does* run at definition time, so it is inlined.
* Scopes are qualified (``Outer.inner``, ``Class.method``) so same-named
  methods in different classes no longer share a scope.

Known simplifications: ``return``/``break`` inside ``try`` do not route through
``finally``; only ``raise`` and the try-entry are linked to handlers.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from ._ast_utils import header_end_line, source_for_node
from .models import CFGEdge, CFGNode, ControlFlowGraph, EdgeType

Pending = tuple[int, EdgeType]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass
class _LoopContext:
    header: int
    breaks: list[Pending] = field(default_factory=list)


@dataclass
class _Frame:
    """Per-function (or module) state for abrupt control flow."""

    return_edge: EdgeType
    returns: list[Pending] = field(default_factory=list)
    raises: list[Pending] = field(default_factory=list)
    loops: list[_LoopContext] = field(default_factory=list)
    handlers: list[list[int]] = field(default_factory=list)


def _dedupe(pending: list[Pending]) -> list[Pending]:
    seen: set[Pending] = set()
    out: list[Pending] = []
    for item in pending:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


class ControlFlowGraphBuilder:
    """Builds a Control Flow Graph from a Python AST.

    Usage:
        builder = ControlFlowGraphBuilder()
        cfg = builder.build(tree, source_code)

    A builder instance is reusable but not thread-safe.
    """

    def __init__(self) -> None:
        self._node_counter: int = 0
        self._source_lines: list[str] = []
        self._current_scope: str = "global"
        self._frames: list[_Frame] = []
        self._handlers = {
            ast.If: self._handle_if,
            ast.For: self._handle_for,
            ast.AsyncFor: self._handle_for,
            ast.While: self._handle_while,
            ast.With: self._handle_with,
            ast.AsyncWith: self._handle_with,
            ast.Try: self._handle_try,
            ast.Return: self._handle_return,
            ast.Break: self._handle_break,
            ast.Continue: self._handle_continue,
            ast.Raise: self._handle_raise,
            ast.FunctionDef: self._handle_function_def,
            ast.AsyncFunctionDef: self._handle_function_def,
            ast.ClassDef: self._handle_class_def,
        }
        if hasattr(ast, "TryStar"):  # Python 3.11+
            self._handlers[ast.TryStar] = self._handle_try
        if hasattr(ast, "Match"):  # Python 3.10+
            self._handlers[ast.Match] = self._handle_match

    # ── public API ──────────────────────────────────────────────────

    def build(self, tree: ast.Module, source_code: str = "") -> ControlFlowGraph:
        """Build a CFG from a Python AST module."""
        self._reset(source_code, "global", EdgeType.RETURN)
        cfg = ControlFlowGraph(source_code=source_code, ast_tree=tree)

        entry = self._new_node(cfg, tree, "Module")
        cfg.entry_node = entry.id
        exits = self._sequence(tree.body, cfg, [(entry.id, EdgeType.SEQUENTIAL)])

        exit_node = self._new_node(cfg, None, "Exit")
        cfg.exit_node = exit_node.id
        self._finish_frame(cfg, exit_node.id, exits)
        return cfg

    def build_from_function(
        self, func_def: FunctionNode, source_code: str = ""
    ) -> ControlFlowGraph:
        """Build a CFG for a single function (FunctionEntry ... FunctionExit)."""
        self._reset(source_code, func_def.name, EdgeType.FUNCTION_RETURN)
        cfg = ControlFlowGraph(
            source_code=source_code,
            ast_tree=ast.Module(body=[func_def], type_ignores=[]),
        )
        entry = self._new_node(cfg, func_def, "FunctionEntry")
        cfg.entry_node = entry.id
        exits = self._sequence(func_def.body, cfg, [(entry.id, EdgeType.SEQUENTIAL)])

        exit_node = self._new_node(cfg, None, "FunctionExit")
        cfg.exit_node = exit_node.id
        self._finish_frame(cfg, exit_node.id, exits)
        return cfg

    def build_from_class(
        self, class_def: ast.ClassDef, source_code: str = ""
    ) -> ControlFlowGraph:
        """Build a CFG for a class body (methods become sub-graphs).

        The old version called ``build_from_function`` for each method, which
        reset the node counter mid-build: later nodes reused IDs 1, 2, ... and
        silently overwrote the entry node.
        """
        self._reset(source_code, class_def.name, EdgeType.RETURN)
        cfg = ControlFlowGraph(
            source_code=source_code,
            ast_tree=ast.Module(body=[class_def], type_ignores=[]),
        )
        entry = self._new_node(cfg, class_def, "ClassEntry")
        cfg.entry_node = entry.id

        exits: list[Pending] = [(entry.id, EdgeType.SEQUENTIAL)]
        for stmt in class_def.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                exits = self._handle_function_def(
                    stmt, cfg, exits, node_type="MethodDef"
                )
            else:
                exits = self._handle_statement(stmt, cfg, exits)

        exit_node = self._new_node(cfg, None, "ClassExit")
        cfg.exit_node = exit_node.id
        self._finish_frame(cfg, exit_node.id, exits)
        return cfg

    # ── infrastructure ──────────────────────────────────────────────

    def _reset(self, source_code: str, scope: str, return_edge: EdgeType) -> None:
        self._node_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        self._current_scope = scope
        self._frames = [_Frame(return_edge)]

    def _qualify(self, name: str) -> str:
        return (
            name if self._current_scope == "global" else f"{self._current_scope}.{name}"
        )

    def _new_node(
        self,
        cfg: ControlFlowGraph,
        ast_node: ast.AST | None,
        node_type: str,
        scope: str | None = None,
    ) -> CFGNode:
        self._node_counter += 1
        line_start = line_end = 0
        source = ""
        if ast_node is not None:
            line_start = getattr(ast_node, "lineno", 0)
            line_end = header_end_line(ast_node, self._source_lines) or line_start
            source = source_for_node(self._source_lines, ast_node)
        node = CFGNode(
            id=self._node_counter,
            ast_node=ast_node,
            node_type=node_type or (type(ast_node).__name__ if ast_node else ""),
            source_code=source,
            line_start=line_start,
            line_end=line_end,
            scope=scope if scope is not None else self._current_scope,
        )
        cfg.add_node(node)
        return node

    @staticmethod
    def _link(cfg: ControlFlowGraph, entries: list[Pending], target: int) -> None:
        for source, edge_type in entries:
            cfg.add_edge(CFGEdge(source=source, target=target, edge_type=edge_type))

    def _make(
        self,
        cfg: ControlFlowGraph,
        ast_node: ast.AST,
        node_type: str,
        entries: list[Pending],
    ) -> CFGNode:
        node = self._new_node(cfg, ast_node, node_type)
        self._link(cfg, entries, node.id)
        return node

    def _finish_frame(
        self, cfg: ControlFlowGraph, exit_id: int, fallthrough: list[Pending]
    ) -> None:
        frame = self._frames.pop()
        self._link(cfg, _dedupe(fallthrough + frame.returns + frame.raises), exit_id)

    def _handle_statement(
        self, stmt: ast.AST, cfg: ControlFlowGraph, entries: list[Pending]
    ) -> list[Pending]:
        handler = self._handlers.get(type(stmt))
        if handler is not None:
            return handler(stmt, cfg, entries)
        node = self._make(cfg, stmt, type(stmt).__name__, entries)
        return [(node.id, EdgeType.SEQUENTIAL)]

    def _sequence(
        self, stmts: list[ast.stmt], cfg: ControlFlowGraph, entries: list[Pending]
    ) -> list[Pending]:
        current = entries
        for stmt in stmts:
            current = self._handle_statement(stmt, cfg, current)
        return current

    # ── compound statements ─────────────────────────────────────────

    def _handle_if(self, node: ast.If, cfg, entries):
        """entry -> Condition -(true)-> body ... ; Condition -(false)-> else/next."""
        cond = self._make(cfg, node.test, "Condition", entries)
        true_exits = self._sequence(node.body, cfg, [(cond.id, EdgeType.TRUE_BRANCH)])
        false_entry = [(cond.id, EdgeType.FALSE_BRANCH)]
        if node.orelse:
            false_exits = self._sequence(node.orelse, cfg, false_entry)
        else:
            false_exits = false_entry
        return _dedupe(true_exits + false_exits)

    def _loop(self, node, cfg, header_id: int, infinite: bool = False) -> list[Pending]:
        frame = self._frames[-1]
        ctx = _LoopContext(header_id)
        frame.loops.append(ctx)
        body_exits = self._sequence(node.body, cfg, [(header_id, EdgeType.TRUE_BRANCH)])
        frame.loops.pop()

        for source, _ in body_exits:
            cfg.add_edge(CFGEdge(source, header_id, EdgeType.LOOP_BACK))

        if infinite:  # `while True`: only `break` leaves the loop
            exits: list[Pending] = []
        elif node.orelse:  # else runs on normal exit, never after `break`
            exits = self._sequence(node.orelse, cfg, [(header_id, EdgeType.LOOP_EXIT)])
        else:
            exits = [(header_id, EdgeType.LOOP_EXIT)]
        return _dedupe(exits + ctx.breaks)

    def _handle_for(self, node, cfg, entries):
        header = self._make(cfg, node, "ForHeader", entries)
        return self._loop(node, cfg, header.id)

    def _handle_while(self, node: ast.While, cfg, entries):
        cond = self._make(cfg, node.test, "WhileCondition", entries)
        infinite = isinstance(node.test, ast.Constant) and bool(node.test.value)
        return self._loop(node, cfg, cond.id, infinite=infinite)

    def _handle_with(self, node, cfg, entries):
        entry = self._make(cfg, node, "WithEntry", entries)
        body_exits = self._sequence(node.body, cfg, [(entry.id, EdgeType.SEQUENTIAL)])
        if not body_exits:  # body always returns/raises/breaks
            return []
        exit_node = self._new_node(cfg, None, "WithExit")
        self._link(cfg, body_exits, exit_node.id)
        return [(exit_node.id, EdgeType.SEQUENTIAL)]

    def _handle_try(self, node, cfg, entries):
        entry = self._make(cfg, node, "TryEntry", entries)
        frame = self._frames[-1]

        handler_nodes = [self._new_node(cfg, h, "ExceptHandler") for h in node.handlers]
        for h in handler_nodes:  # an exception may arise anywhere in the body
            cfg.add_edge(CFGEdge(entry.id, h.id, EdgeType.EXCEPTION))

        frame.handlers.append([h.id for h in handler_nodes])
        body_exits = self._sequence(node.body, cfg, [(entry.id, EdgeType.SEQUENTIAL)])
        frame.handlers.pop()

        ok_exits = (
            self._sequence(node.orelse, cfg, body_exits) if node.orelse else body_exits
        )

        handler_exits: list[Pending] = []
        for handler, h_node in zip(node.handlers, handler_nodes, strict=True):
            handler_exits += self._sequence(
                handler.body, cfg, [(h_node.id, EdgeType.SEQUENTIAL)]
            )

        merged = _dedupe(ok_exits + handler_exits)
        if node.finalbody:
            # If every path leaves early, keep `finally` reachable from the try.
            return self._sequence(
                node.finalbody, cfg, merged or [(entry.id, EdgeType.SEQUENTIAL)]
            )
        return merged

    def _handle_match(self, node, cfg, entries):
        subject = self._make(cfg, node.subject, "Match", entries)
        exits: list[Pending] = []
        previous: list[Pending] = [(subject.id, EdgeType.SEQUENTIAL)]
        irrefutable = False
        for case in node.cases:
            case_node = self._make(cfg, case.pattern, "MatchCase", previous)
            exits += self._sequence(
                case.body, cfg, [(case_node.id, EdgeType.TRUE_BRANCH)]
            )
            previous = [(case_node.id, EdgeType.FALSE_BRANCH)]
            pattern = case.pattern
            irrefutable = (
                case.guard is None
                and type(pattern).__name__ == "MatchAs"
                and pattern.pattern is None
            )
        if not irrefutable:  # no case matched: fall through
            exits += previous
        return _dedupe(exits)

    # ── definitions ─────────────────────────────────────────────────

    def _handle_function_def(self, node, cfg, entries, node_type: str = "FunctionDef"):
        """The def statement flows on; its body is a detached sub-graph."""
        def_node = self._make(cfg, node, node_type, entries)

        scope = self._qualify(node.name)
        entry = self._new_node(cfg, node, "FunctionEntry", scope=scope)
        cfg.add_edge(CFGEdge(def_node.id, entry.id, EdgeType.FUNCTION_CALL))

        outer_scope = self._current_scope
        self._current_scope = scope
        self._frames.append(_Frame(EdgeType.FUNCTION_RETURN))
        body_exits = self._sequence(node.body, cfg, [(entry.id, EdgeType.SEQUENTIAL)])
        exit_node = self._new_node(cfg, None, "FunctionExit")
        self._finish_frame(cfg, exit_node.id, body_exits)
        self._current_scope = outer_scope

        return [(def_node.id, EdgeType.SEQUENTIAL)]

    def _handle_class_def(self, node: ast.ClassDef, cfg, entries):
        """A class body executes at definition time, so it is inlined."""
        class_node = self._make(cfg, node, "ClassDef", entries)
        outer_scope = self._current_scope
        self._current_scope = self._qualify(node.name)
        exits = self._sequence(node.body, cfg, [(class_node.id, EdgeType.SEQUENTIAL)])
        self._current_scope = outer_scope
        return exits

    # ── abrupt control flow ─────────────────────────────────────────

    def _handle_return(self, node, cfg, entries):
        ret = self._make(cfg, node, "Return", entries)
        frame = self._frames[-1]
        frame.returns.append((ret.id, frame.return_edge))
        return []

    def _handle_raise(self, node, cfg, entries):
        raise_node = self._make(cfg, node, "Raise", entries)
        frame = self._frames[-1]
        targets = next((h for h in reversed(frame.handlers) if h), [])
        if targets:
            for handler_id in targets:
                cfg.add_edge(CFGEdge(raise_node.id, handler_id, EdgeType.EXCEPTION))
        else:
            frame.raises.append((raise_node.id, EdgeType.EXCEPTION))
        return []

    def _handle_break(self, node, cfg, entries):
        brk = self._make(cfg, node, "Break", entries)
        frame = self._frames[-1]
        if frame.loops:
            frame.loops[-1].breaks.append((brk.id, EdgeType.BREAK))
        else:  # `break` outside a loop (parses, never compiles)
            frame.returns.append((brk.id, EdgeType.BREAK))
        return []

    def _handle_continue(self, node, cfg, entries):
        cont = self._make(cfg, node, "Continue", entries)
        frame = self._frames[-1]
        if frame.loops:
            cfg.add_edge(CFGEdge(cont.id, frame.loops[-1].header, EdgeType.CONTINUE))
        else:
            frame.returns.append((cont.id, EdgeType.CONTINUE))
        return []


def build_cfg(source_code: str, tree: ast.Module | None = None) -> ControlFlowGraph:
    """Convenience function to build a CFG from source code.

    Raises:
        SyntaxError: If source code cannot be parsed
    """
    if tree is None:
        tree = ast.parse(source_code)
    return ControlFlowGraphBuilder().build(tree, source_code)


def build_cfg_for_function(
    source_code: str,
    function_name: str,
) -> ControlFlowGraph | None:
    """Build a CFG for a specific function in the source code (``None`` if absent)."""
    tree = ast.parse(source_code)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ):
            return ControlFlowGraphBuilder().build_from_function(node, source_code)
    return None
