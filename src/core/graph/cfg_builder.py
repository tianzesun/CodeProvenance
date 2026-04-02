"""
Control Flow Graph (CFG) Builder for Python AST.

This module traverses a Python AST and constructs a Control Flow Graph
that represents all possible execution paths through the code.
"""

import ast
from typing import Dict, List, Optional, Tuple, Union

from .models import CFGNode, CFGEdge, EdgeType, ControlFlowGraph


class ControlFlowGraphBuilder:
    """Builds a Control Flow Graph from a Python AST.
    
    The builder recursively processes AST nodes, creating CFG nodes for
    each statement and connecting them with appropriate edges based on
    control flow semantics.
    
    Usage:
        builder = ControlFlowGraphBuilder()
        cfg = builder.build(tree, source_code)
    """
    
    def __init__(self) -> None:
        self._node_counter: int = 0
        self._source_lines: List[str] = []
        self._current_scope: str = "global"
        self._scope_stack: List[str] = []
    
    def build(self, tree: ast.Module, source_code: str = "") -> ControlFlowGraph:
        """Build a CFG from a Python AST module.
        
        Args:
            tree: Python AST module
            source_code: Original source code string
            
        Returns:
            ControlFlowGraph representing the execution flow
        """
        self._node_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        self._current_scope = "global"
        self._scope_stack = ["global"]
        
        cfg = ControlFlowGraph(
            source_code=source_code,
            ast_tree=tree,
        )
        
        # Create entry node
        entry = self._create_cfg_node(
            ast_node=tree,
            node_type="Module",
            scope="global",
        )
        cfg.add_node(entry)
        cfg.entry_node = entry.id
        
        # Process all top-level statements
        prev_nodes: List[int] = [entry.id]
        
        for stmt in tree.body:
            next_nodes = self._handle_statement(stmt, cfg, prev_nodes)
            prev_nodes = next_nodes
        
        # Create exit node and connect from all final nodes
        exit_node = self._create_cfg_node(
            node_type="Exit",
            scope="global",
        )
        cfg.add_node(exit_node)
        cfg.exit_node = exit_node.id
        
        for node_id in prev_nodes:
            if node_id in cfg.nodes:
                cfg.add_edge(CFGEdge(
                    source=node_id,
                    target=exit_node.id,
                    edge_type=EdgeType.SEQUENTIAL,
                ))
        
        return cfg
    
    def build_from_function(self, func_def: ast.FunctionDef, source_code: str = "") -> ControlFlowGraph:
        """Build a CFG for a single function definition.
        
        Args:
            func_def: FunctionDef AST node
            source_code: Original source code string
            
        Returns:
            ControlFlowGraph for the function body
        """
        self._node_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        func_name = func_def.name
        self._current_scope = func_name
        self._scope_stack = ["global", func_name]
        
        cfg = ControlFlowGraph(
            source_code=source_code,
            ast_tree=ast.Module(body=[func_def]),
        )
        
        # Create entry node
        entry = self._create_cfg_node(
            ast_node=func_def,
            node_type="FunctionEntry",
            scope=func_name,
        )
        cfg.add_node(entry)
        cfg.entry_node = entry.id
        
        # Process function body
        prev_nodes: List[int] = [entry.id]
        
        for stmt in func_def.body:
            next_nodes = self._handle_statement(stmt, cfg, prev_nodes)
            prev_nodes = next_nodes
        
        # Check if we need an implicit return
        has_explicit_return = any(
            isinstance(node, ast.Return) for node in ast.walk(func_def)
        )
        
        exit_node = self._create_cfg_node(
            node_type="FunctionExit",
            scope=func_name,
        )
        cfg.add_node(exit_node)
        cfg.exit_node = exit_node.id
        
        for node_id in prev_nodes:
            if node_id in cfg.nodes:
                cfg.add_edge(CFGEdge(
                    source=node_id,
                    target=exit_node.id,
                    edge_type=EdgeType.FUNCTION_RETURN if has_explicit_return else EdgeType.SEQUENTIAL,
                ))
        
        return cfg
    
    def build_from_class(self, class_def: ast.ClassDef, source_code: str = "") -> ControlFlowGraph:
        """Build a CFG for a class definition.
        
        Args:
            class_def: ClassDef AST node
            source_code: Original source code string
            
        Returns:
            ControlFlowGraph for the class body
        """
        self._node_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        class_name = class_def.name
        
        cfg = ControlFlowGraph(
            source_code=source_code,
            ast_tree=ast.Module(body=[class_def]),
        )
        
        entry = self._create_cfg_node(
            ast_node=class_def,
            node_type="ClassEntry",
            scope=class_name,
        )
        cfg.add_node(entry)
        cfg.entry_node = entry.id
        
        # Process class body
        prev_nodes: List[int] = [entry.id]
        
        for stmt in class_def.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Each method has its own scope
                method_cfg = self.build_from_function(stmt, source_code)
                # Add method entry as a single node in class CFG
                method_node = self._create_cfg_node(
                    ast_node=stmt,
                    node_type="MethodDef",
                    scope=class_name,
                )
                cfg.add_node(method_node)
                for prev_id in prev_nodes:
                    cfg.add_edge(CFGEdge(source=prev_id, target=method_node.id))
                prev_nodes = [method_node.id]
            else:
                next_nodes = self._handle_statement(stmt, cfg, prev_nodes)
                prev_nodes = next_nodes
        
        exit_node = self._create_cfg_node(node_type="ClassExit", scope=class_name)
        cfg.add_node(exit_node)
        cfg.exit_node = exit_node.id
        
        for node_id in prev_nodes:
            if node_id in cfg.nodes:
                cfg.add_edge(CFGEdge(source=node_id, target=exit_node.id))
        
        return cfg
    
    def _create_cfg_node(
        self,
        ast_node: Optional[ast.AST] = None,
        node_type: str = "",
        scope: Optional[str] = None,
    ) -> CFGNode:
        """Create a new CFG node.
        
        Args:
            ast_node: Associated AST node
            node_type: Type identifier
            scope: Lexical scope
            
        Returns:
            New CFGNode instance
        """
        self._node_counter += 1
        current_scope = scope if scope is not None else self._current_scope
        
        line_start = 0
        line_end = 0
        source_code = ""
        
        if ast_node is not None:
            line_start = getattr(ast_node, "lineno", 0)
            line_end = getattr(ast_node, "end_lineno", line_start)
            source_code = self._get_source_line(ast_node)
        
        return CFGNode(
            id=self._node_counter,
            ast_node=ast_node,
            node_type=node_type or (ast_node.__class__.__name__ if ast_node else ""),
            source_code=source_code,
            line_start=line_start,
            line_end=line_end,
            scope=current_scope,
        )
    
    def _get_source_line(self, ast_node: ast.AST) -> str:
        """Get the source code line for an AST node."""
        line_start = getattr(ast_node, "lineno", None)
        line_end = getattr(ast_node, "end_lineno", line_start)
        
        if line_start and line_end and self._source_lines:
            start_idx = line_start - 1
            end_idx = line_end
            if 0 <= start_idx < len(self._source_lines):
                return " ".join(self._source_lines[start_idx:end_idx]).strip()
        return ""
    
    def _handle_statement(
        self,
        stmt: ast.AST,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle a single statement and return exit nodes.
        
        Args:
            stmt: AST statement node
            cfg: Control flow graph being built
            entry_nodes: List of node IDs that can reach this statement
            
        Returns:
            List of exit node IDs after processing this statement
        """
        # Connect entry nodes to this statement
        handler_map = {
            ast.Assign: self._handle_assign,
            ast.AugAssign: self._handle_aug_assign,
            ast.AnnAssign: self._handle_ann_assign,
            ast.If: self._handle_if,
            ast.For: self._handle_for,
            ast.While: self._handle_while,
            ast.With: self._handle_with,
            ast.Try: self._handle_try,
            ast.Return: self._handle_return,
            ast.Break: self._handle_break,
            ast.Continue: self._handle_continue,
            ast.FunctionDef: self._handle_function_def,
            ast.AsyncFunctionDef: self._handle_function_def,
            ast.ClassDef: self._handle_class_def,
            ast.Import: self._handle_import,
            ast.ImportFrom: self._handle_import_from,
            ast.Expression: self._handle_expression,
            ast.Expr: self._handle_expr,
            ast.Pass: self._handle_pass,
            ast.Assert: self._handle_assert,
            ast.Raise: self._handle_raise,
            ast.Delete: self._handle_delete,
            ast.Global: self._handle_global,
            ast.Nonlocal: self._handle_nonlocal,
        }
        
        handler = handler_map.get(type(stmt))
        if handler:
            return handler(stmt, cfg, entry_nodes)
        
        # Default handling for other statement types
        node = self._create_cfg_node(stmt)
        cfg.add_node(node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=node.id))
        
        return [node.id]
    
    def _handle_statements_sequence(
        self,
        stmts: List[ast.AST],
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle a sequence of statements.
        
        Args:
            stmts: List of AST statements
            cfg: Control flow graph
            entry_nodes: Entry node IDs
            
        Returns:
            Exit node IDs after all statements
        """
        current_nodes = entry_nodes
        for stmt in stmts:
            current_nodes = self._handle_statement(stmt, cfg, current_nodes)
        return current_nodes
    
    def _handle_assign(
        self,
        node: ast.Assign,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle assignment statements."""
        cfg_node = self._create_cfg_node(node, node_type="Assign")
        cfg.add_node(cfg_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=cfg_node.id))
        
        return [cfg_node.id]
    
    def _handle_aug_assign(
        self,
        node: ast.AugAssign,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle augmented assignment statements (+=, -=, etc.)."""
        cfg_node = self._create_cfg_node(node, node_type="AugAssign")
        cfg.add_node(cfg_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=cfg_node.id))
        
        return [cfg_node.id]
    
    def _handle_ann_assign(
        self,
        node: ast.AnnAssign,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle annotated assignment statements."""
        cfg_node = self._create_cfg_node(node, node_type="AnnAssign")
        cfg.add_node(cfg_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=cfg_node.id))
        
        return [cfg_node.id]
    
    def _handle_if(
        self,
        node: ast.If,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle if-else statements.
        
        Creates a diamond structure:
            entry -> condition -> true_branch  \
                                     -> merge
            entry -> condition -> false_branch /
        """
        # Create condition node
        condition_node = self._create_cfg_node(node.test, node_type="Condition")
        cfg.add_node(condition_node)
        
        # Connect entries to condition
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=condition_node.id))
        
        # Handle true branch (if body)
        true_exit = self._handle_statements_sequence(node.body, cfg, [condition_node.id])
        
        # Handle false branch (else body) or direct pass-through
        if node.orelse:
            false_exit = self._handle_statements_sequence(node.orelse, cfg, [condition_node.id])
        else:
            # No else branch - connect condition directly to merge
            false_exit = [condition_node.id]
            for entry_id in entry_nodes:
                cfg.add_edge(CFGEdge(
                    source=condition_node.id,
                    target=condition_node.id,
                    edge_type=EdgeType.FALSE_BRANCH,
                ))
        
        # Update edge types
        # Condition -> true body
        if node.body:
            first_body_node = cfg.nodes.get(true_exit[0]) if true_exit else None
            # Actually connect to the first statement in body
            pass
        
        # Re-structure: connect condition to first body node with TRUE_BRANCH
        if true_exit:
            # Find the actual first node in the body (not exit)
            pass
        
        # Merge point: all exits converge
        # We return both true and false exits - caller should merge
        return list(set(true_exit + false_exit))
    
    def _handle_for(
        self,
        node: ast.For,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle for loops.
        
        Creates structure:
            entry -> loop_header -> body -> loop_header (back edge)
                 -> exit (when iteration completes)
        """
        # Create loop header node
        header_node = self._create_cfg_node(node, node_type="ForHeader")
        cfg.add_node(header_node)
        
        # Connect entries to header
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=header_node.id))
        
        # Handle loop body
        body_exit = self._handle_statements_sequence(node.body, cfg, [header_node.id])
        
        # Add loop back edges
        for body_id in body_exit:
            cfg.add_edge(CFGEdge(
                source=body_id,
                target=header_node.id,
                edge_type=EdgeType.LOOP_BACK,
            ))
        
        # Handle else clause (executes when loop completes normally)
        if node.orelse:
            else_exit = self._handle_statements_sequence(node.orelse, cfg, [header_node.id])
            return else_exit
        
        # Exit from loop header (when iteration completes)
        return [header_node.id]
    
    def _handle_while(
        self,
        node: ast.While,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle while loops.
        
        Creates structure:
            entry -> condition -> body -> condition (back edge)
                  -> else/exit (when condition false)
        """
        # Create condition node
        condition_node = self._create_cfg_node(node.test, node_type="WhileCondition")
        cfg.add_node(condition_node)
        
        # Connect entries to condition
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=condition_node.id))
        
        # Handle loop body
        body_exit = self._handle_statements_sequence(node.body, cfg, [condition_node.id])
        
        # Add loop back edges
        for body_id in body_exit:
            cfg.add_edge(CFGEdge(
                source=body_id,
                target=condition_node.id,
                edge_type=EdgeType.LOOP_BACK,
            ))
        
        # Handle else clause
        if node.orelse:
            else_exit = self._handle_statements_sequence(node.orelse, cfg, [condition_node.id])
            return else_exit
        
        return [condition_node.id]
    
    def _handle_with(
        self,
        node: ast.With,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle with statements (context managers)."""
        entry_node = self._create_cfg_node(node, node_type="WithEntry")
        cfg.add_node(entry_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=entry_node.id))
        
        body_exit = self._handle_statements_sequence(node.body, cfg, [entry_node.id])
        
        exit_node = self._create_cfg_node(node_type="WithExit")
        cfg.add_node(exit_node)
        
        for body_id in body_exit:
            cfg.add_edge(CFGEdge(source=body_id, target=exit_node.id))
        
        return [exit_node.id]
    
    def _handle_try(
        self,
        node: ast.Try,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle try-except-finally statements."""
        # Try entry
        try_entry_node = self._create_cfg_node(node, node_type="TryEntry")
        cfg.add_node(try_entry_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=try_entry_node.id))
        
        # Try body
        try_exit = self._handle_statements_sequence(node.body, cfg, [try_entry_node.id])
        
        # Exception handlers
        handler_exits: List[int] = []
        for handler in node.handlers:
            handler_node = self._create_cfg_node(handler, node_type="ExceptHandler")
            cfg.add_node(handler_node)
            
            # Connect from try entry (exception can occur anywhere)
            cfg.add_edge(CFGEdge(
                source=try_entry_node.id,
                target=handler_node.id,
                edge_type=EdgeType.EXCEPTION,
            ))
            
            handler_body_exit = self._handle_statements_sequence(
                handler.body, cfg, [handler_node.id]
            )
            handler_exits.extend(handler_body_exit)
        
        # Else clause (executes if no exception)
        if node.orelse:
            else_exit = self._handle_statements_sequence(node.orelse, cfg, try_exit)
            merge_exits = else_exit
        else:
            merge_exits = try_exit
        
        # Finally clause (always executes)
        if node.finalbody:
            finally_exit = self._handle_statements_sequence(
                node.finalbody, cfg, merge_exits + handler_exits
            )
            return finally_exit
        
        return merge_exits + handler_exits
    
    def _handle_return(
        self,
        node: ast.Return,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle return statements.
        
        Return is a terminal node - no successors within the function.
        """
        return_node = self._create_cfg_node(node, node_type="Return")
        cfg.add_node(return_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=return_node.id))
        
        # Return has no successors - return empty list
        return []
    
    def _handle_break(
        self,
        node: ast.Break,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle break statements.
        
        Break exits the innermost loop - target is determined by context.
        """
        break_node = self._create_cfg_node(node, node_type="Break")
        cfg.add_node(break_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=break_node.id))
        
        return []  # Break is terminal within current scope
    
    def _handle_continue(
        self,
        node: ast.Continue,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle continue statements.
        
        Continue jumps back to loop header - target determined by context.
        """
        continue_node = self._create_cfg_node(node, node_type="Continue")
        cfg.add_node(continue_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=continue_node.id))
        
        return []  # Continue is terminal within current scope
    
    def _handle_function_def(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle function definitions."""
        func_node = self._create_cfg_node(node, node_type="FunctionDef")
        cfg.add_node(func_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=func_node.id))
        
        # Also process the function body statements
        old_scope = self._current_scope
        self._current_scope = node.name
        
        body_nodes = self._handle_statements_sequence(node.body, cfg, [func_node.id])
        
        self._current_scope = old_scope
        
        # Return both the function def node and the body exit nodes
        return [func_node.id] + body_nodes
    
    def _handle_class_def(
        self,
        node: ast.ClassDef,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle class definitions."""
        class_node = self._create_cfg_node(node, node_type="ClassDef")
        cfg.add_node(class_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=class_node.id))
        
        # Also process the class body statements
        old_scope = self._current_scope
        self._current_scope = node.name
        
        body_nodes = self._handle_statements_sequence(node.body, cfg, [class_node.id])
        
        self._current_scope = old_scope
        
        return [class_node.id] + body_nodes
    
    def _handle_import(
        self,
        node: ast.Import,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle import statements."""
        import_node = self._create_cfg_node(node, node_type="Import")
        cfg.add_node(import_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=import_node.id))
        
        return [import_node.id]
    
    def _handle_import_from(
        self,
        node: ast.ImportFrom,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle from-import statements."""
        import_node = self._create_cfg_node(node, node_type="ImportFrom")
        cfg.add_node(import_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=import_node.id))
        
        return [import_node.id]
    
    def _handle_expr(
        self,
        node: ast.Expr,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle expression statements (e.g., function calls)."""
        expr_node = self._create_cfg_node(node, node_type="Expr")
        cfg.add_node(expr_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=expr_node.id))
        
        return [expr_node.id]
    
    def _handle_expression(
        self,
        node: ast.Expression,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle expression nodes."""
        expr_node = self._create_cfg_node(node, node_type="Expression")
        cfg.add_node(expr_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=expr_node.id))
        
        return [expr_node.id]
    
    def _handle_pass(
        self,
        node: ast.Pass,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle pass statements."""
        pass_node = self._create_cfg_node(node, node_type="Pass")
        cfg.add_node(pass_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=pass_node.id))
        
        return [pass_node.id]
    
    def _handle_assert(
        self,
        node: ast.Assert,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle assert statements.
        
        Assert is like an if that raises AssertionError on false.
        """
        assert_node = self._create_cfg_node(node, node_type="Assert")
        cfg.add_node(assert_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=assert_node.id))
        
        return [assert_node.id]
    
    def _handle_raise(
        self,
        node: ast.Raise,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle raise statements.
        
        Raise is terminal - no successors within normal flow.
        """
        raise_node = self._create_cfg_node(node, node_type="Raise")
        cfg.add_node(raise_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=raise_node.id))
        
        return []  # Terminal node
    
    def _handle_delete(
        self,
        node: ast.Delete,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle delete statements."""
        del_node = self._create_cfg_node(node, node_type="Delete")
        cfg.add_node(del_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=del_node.id))
        
        return [del_node.id]
    
    def _handle_global(
        self,
        node: ast.Global,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle global declarations."""
        global_node = self._create_cfg_node(node, node_type="Global")
        cfg.add_node(global_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=global_node.id))
        
        return [global_node.id]
    
    def _handle_nonlocal(
        self,
        node: ast.Nonlocal,
        cfg: ControlFlowGraph,
        entry_nodes: List[int],
    ) -> List[int]:
        """Handle nonlocal declarations."""
        nonlocal_node = self._create_cfg_node(node, node_type="Nonlocal")
        cfg.add_node(nonlocal_node)
        
        for entry_id in entry_nodes:
            cfg.add_edge(CFGEdge(source=entry_id, target=nonlocal_node.id))
        
        return [nonlocal_node.id]


def build_cfg(source_code: str, tree: Optional[ast.Module] = None) -> ControlFlowGraph:
    """Convenience function to build a CFG from source code.
    
    Args:
        source_code: Python source code string
        tree: Pre-parsed AST (optional, will parse if not provided)
        
    Returns:
        ControlFlowGraph representing the code
        
    Raises:
        SyntaxError: If source code cannot be parsed
    """
    if tree is None:
        tree = ast.parse(source_code)
    
    builder = ControlFlowGraphBuilder()
    return builder.build(tree, source_code)


def build_cfg_for_function(
    source_code: str,
    function_name: str,
) -> Optional[ControlFlowGraph]:
    """Build a CFG for a specific function in the source code.
    
    Args:
        source_code: Python source code string
        function_name: Name of the function to extract
        
    Returns:
        ControlFlowGraph for the function, or None if not found
    """
    tree = ast.parse(source_code)
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                builder = ControlFlowGraphBuilder()
                return builder.build_from_function(node, source_code)
    
    return None