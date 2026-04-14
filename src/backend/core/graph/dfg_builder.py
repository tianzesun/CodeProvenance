"""
Data Flow Graph (DFG) Builder for Python AST.

This module analyzes a Python AST (along with its CFG) to construct a Data Flow Graph
that represents data dependencies between variable definitions and uses.
"""

import ast
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    CFGNode,
    ControlFlowGraph,
    DataFlowGraph,
    DFEdge,
    DFNode,
    VariableState,
)


class ScopeInfo:
    """Tracks variable definitions within a scope.
    
    Attributes:
        name: Scope name (e.g., function name)
        definitions: Maps variable name to list of DFNode IDs that define it
        parent: Parent scope (for closure analysis)
    """
    
    def __init__(self, name: str, parent: Optional['ScopeInfo'] = None) -> None:
        self.name = name
        self.parent = parent
        self.definitions: Dict[str, List[int]] = {}
    
    def add_definition(self, var_name: str, node_id: int) -> None:
        """Record a variable definition in this scope."""
        if var_name not in self.definitions:
            self.definitions[var_name] = []
        self.definitions[var_name].append(node_id)
    
    def get_definitions(self, var_name: str) -> List[int]:
        """Get all definitions of a variable, searching parent scopes."""
        if var_name in self.definitions:
            return self.definitions[var_name]
        if self.parent:
            return self.parent.get_definitions(var_name)
        return []


class DataFlowGraphBuilder:
    """Builds a Data Flow Graph from a Python AST and its CFG.
    
    The builder:
    1. Traverses the AST to identify variable definitions and uses
    2. Creates DFNodes for each def/use point
    3. Connects definitions to their uses based on reaching definitions analysis
    4. Produces a DFG that captures data dependencies
    
    Usage:
        dfg_builder = DataFlowGraphBuilder()
        dfg = dfg_builder.build(tree, cfg, source_code)
    """
    
    # Built-in names that should not be tracked as user variables
    BUILTINS: Set[str] = {
        'True', 'False', 'None', 'print', 'len', 'range', 'int', 'str',
        'float', 'bool', 'list', 'dict', 'set', 'tuple', 'type', 'object',
        'list', 'dict', 'set', 'tuple', 'frozenset', 'bytes', 'bytearray',
        'complex', 'Ellipsis', 'NotImplemented', '__debug__', 'quit',
        'exit', 'copyright', 'credits', 'license', 'help', 'input',
        'open', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed',
        'min', 'max', 'sum', 'abs', 'round', 'pow', 'divmod', 'hash',
        'id', 'repr', 'format', 'ascii', 'bin', 'oct', 'hex', 'chr',
        'ord', 'dir', 'vars', 'globals', 'locals', 'hasattr', 'getattr',
        'setattr', 'delattr', 'isinstance', 'issubclass', 'callable',
    }
    
    def __init__(self) -> None:
        self._node_counter: int = 0
        self._scopes: Dict[str, ScopeInfo] = {}
        self._current_scope: str = "global"
        self._source_lines: List[str] = []
        self._global_names: Set[str] = set()
        self._nonlocal_names: Set[str] = set()
    
    def build(
        self,
        tree: ast.Module,
        cfg: ControlFlowGraph,
        source_code: str = "",
    ) -> DataFlowGraph:
        """Build a DFG from AST and CFG.
        
        Args:
            tree: Python AST module
            cfg: Control Flow Graph for the same code
            source_code: Original source code string
            
        Returns:
            DataFlowGraph representing data dependencies
        """
        self._node_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        self._current_scope = "global"
        self._scopes = {"global": ScopeInfo("global")}
        self._global_names = set()
        self._nonlocal_names = set()
        
        dfg = DataFlowGraph(
            cfg_reference=cfg,
            source_code=source_code,
        )
        
        # First pass: identify all definitions and their locations
        self._collect_declarations(tree, dfg, cfg)
        
        # Second pass: build definition-use chains
        self._build_def_use_chains(dfg, cfg)
        
        return dfg
    
    def build_for_function(
        self,
        func_def: ast.FunctionDef,
        cfg: ControlFlowGraph,
        source_code: str = "",
    ) -> DataFlowGraph:
        """Build a DFG for a specific function.
        
        Args:
            func_def: FunctionDef AST node
            cfg: CFG for the function
            source_code: Original source code
            
        Returns:
            DataFlowGraph for the function
        """
        self._node_counter = 0
        self._source_lines = source_code.splitlines() if source_code else []
        func_name = func_def.name
        self._current_scope = func_name
        self._scopes = {func_name: ScopeInfo(func_name)}
        self._global_names = set()
        self._nonlocal_names = set()
        
        dfg = DataFlowGraph(
            cfg_reference=cfg,
            source_code=source_code,
        )
        
        # Parameters are definitions
        for param in func_def.args.args:
            if param.arg != 'self':
                df_node = self._create_df_node(
                    variable_name=param.arg,
                    state=VariableState.DEFINED,
                    cfg_node_id=self._find_cfg_node_for_line(cfg, getattr(param, 'lineno', 0)),
                    line_number=getattr(param, 'lineno', 0),
                    scope=func_name,
                )
                dfg.add_node(df_node)
                self._scopes[func_name].add_definition(param.arg, df_node.id)
        
        self._collect_declarations(func_def, dfg, cfg)
        self._build_def_use_chains(dfg, cfg)
        
        return dfg
    
    def _create_df_node(
        self,
        variable_name: str,
        state: VariableState,
        cfg_node_id: int = 0,
        line_number: int = 0,
        source_code: str = "",
        scope: str = "global",
    ) -> DFNode:
        """Create a new DFNode.
        
        Args:
            variable_name: Name of the variable
            state: State of the variable (defined, used, modified)
            cfg_node_id: Associated CFG node ID
            line_number: Line number in source
            source_code: Source code snippet
            scope: Lexical scope
            
        Returns:
            New DFNode instance
        """
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
    
    def _find_cfg_node_for_line(self, cfg: ControlFlowGraph, line: int) -> int:
        """Find CFG node that contains the given line number.
        
        Args:
            cfg: Control Flow Graph
            line: Line number to find
            
        Returns:
            Node ID if found, 0 otherwise
        """
        for node_id, node in cfg.nodes.items():
            if node.line_start <= line <= (node.line_end or node.line_start):
                return node_id
        # Return entry node as fallback
        return cfg.entry_node or 0
    
    def _is_user_variable(self, name: str) -> bool:
        """Check if a name should be tracked as a user variable.
        
        Args:
            name: Variable name
            
        Returns:
            True if variable should be tracked
        """
        return not (name.startswith('_') and name.endswith('_')) and \
               name not in self.BUILTINS
    
    def _collect_declarations(
        self,
        node: ast.AST,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """First pass: collect all variable declarations and their locations.
        
        This identifies all points where variables are defined (assigned)
        and used (read).
        """
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Assign):
                self._handle_assign(child, dfg, cfg)
            elif isinstance(child, ast.AugAssign):
                self._handle_aug_assign(child, dfg, cfg)
            elif isinstance(child, ast.AnnAssign):
                self._handle_ann_assign(child, dfg, cfg)
            elif isinstance(child, ast.For):
                self._handle_for(child, dfg, cfg)
            elif isinstance(child, ast.comprehension):
                self._handle_comprehension_var(child, dfg, cfg)
            elif isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
                self._handle_nested_function(child, dfg, cfg)
            elif isinstance(child, ast.ClassDef):
                self._handle_class_def(child, dfg, cfg)
            elif isinstance(child, ast.With):
                self._handle_with(child, dfg, cfg)
            elif isinstance(child, ast.ExceptHandler):
                self._handle_except_handler(child, dfg, cfg)
            elif isinstance(child, ast.Global):
                self._handle_global(child)
            elif isinstance(child, ast.Nonlocal):
                self._handle_nonlocal(child)
            else:
                # Look for variable uses in expressions
                self._collect_uses(child, dfg, cfg)
                self._collect_declarations(child, dfg, cfg)
    
    def _handle_assign(
        self,
        node: ast.Assign,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle simple assignments (x = value)."""
        line = getattr(node, 'lineno', 0)
        cfg_node_id = self._find_cfg_node_for_line(cfg, line)
        source = self._get_source_line(node)
        
        # Record uses on RHS
        self._collect_uses(node.value, dfg, cfg)
        
        # Record definitions on LHS
        for target in node.targets:
            if isinstance(target, ast.Name) and self._is_user_variable(target.id):
                df_node = self._create_df_node(
                    variable_name=target.id,
                    state=VariableState.DEFINED,
                    cfg_node_id=cfg_node_id,
                    line_number=line,
                    source_code=source,
                    scope=self._current_scope,
                )
                dfg.add_node(df_node)
                self._get_scope().add_definition(target.id, df_node.id)
            elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                # Unpacking: x, y = ...
                for elt in target.elts:
                    if isinstance(elt, ast.Name) and self._is_user_variable(elt.id):
                        df_node = self._create_df_node(
                            variable_name=elt.id,
                            state=VariableState.DEFINED,
                            cfg_node_id=cfg_node_id,
                            line_number=line,
                            source_code=source,
                            scope=self._current_scope,
                        )
                        dfg.add_node(df_node)
                        self._get_scope().add_definition(elt.id, df_node.id)
            elif isinstance(target, ast.Attribute):
                # Attribute assignment - track the base variable
                if isinstance(target.value, ast.Name) and self._is_user_variable(target.value.id):
                    df_node = self._create_df_node(
                        variable_name=target.value.id,
                        state=VariableState.USED,  # Using to set attribute
                        cfg_node_id=cfg_node_id,
                        line_number=line,
                        source_code=source,
                        scope=self._current_scope,
                    )
                    dfg.add_node(df_node)
    
    def _handle_aug_assign(
        self,
        node: ast.AugAssign,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle augmented assignments (x += value)."""
        line = getattr(node, 'lineno', 0)
        cfg_node_id = self._find_cfg_node_for_line(cfg, line)
        source = self._get_source_line(node)
        
        if isinstance(node.target, ast.Name) and self._is_user_variable(node.target.id):
            # Augmented assign is both a use and a definition
            df_node = self._create_df_node(
                variable_name=node.target.id,
                state=VariableState.MODIFIED,
                cfg_node_id=cfg_node_id,
                line_number=line,
                source_code=source,
                scope=self._current_scope,
            )
            dfg.add_node(df_node)
            self._get_scope().add_definition(node.target.id, df_node.id)
        
        self._collect_uses(node.value, dfg, cfg)
    
    def _handle_ann_assign(
        self,
        node: ast.AnnAssign,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle annotated assignments (x: int = value)."""
        if node.value is None:
            return  # Just annotation, not a definition
        
        line = getattr(node, 'lineno', 0)
        cfg_node_id = self._find_cfg_node_for_line(cfg, line)
        source = self._get_source_line(node)
        
        if isinstance(node.target, ast.Name) and self._is_user_variable(node.target.id):
            df_node = self._create_df_node(
                variable_name=node.target.id,
                state=VariableState.DEFINED,
                cfg_node_id=cfg_node_id,
                line_number=line,
                source_code=source,
                scope=self._current_scope,
            )
            dfg.add_node(df_node)
            self._get_scope().add_definition(node.target.id, df_node.id)
        
        self._collect_uses(node.value, dfg, cfg)
    
    def _handle_for(
        self,
        node: ast.For,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle for loop variable definition."""
        line = getattr(node, 'lineno', 0)
        cfg_node_id = self._find_cfg_node_for_line(cfg, line)
        source = self._get_source_line(node)
        
        # Loop variable is defined by iteration
        if isinstance(node.target, ast.Name) and self._is_user_variable(node.target.id):
            df_node = self._create_df_node(
                variable_name=node.target.id,
                state=VariableState.DEFINED,
                cfg_node_id=cfg_node_id,
                line_number=line,
                source_code=source,
                scope=self._current_scope,
            )
            dfg.add_node(df_node)
            self._get_scope().add_definition(node.target.id, df_node.id)
        elif isinstance(node.target, ast.Tuple):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name) and self._is_user_variable(elt.id):
                    df_node = self._create_df_node(
                        variable_name=elt.id,
                        state=VariableState.DEFINED,
                        cfg_node_id=cfg_node_id,
                        line_number=line,
                        source_code=source,
                        scope=self._current_scope,
                    )
                    dfg.add_node(df_node)
                    self._get_scope().add_definition(elt.id, df_node.id)
        
        # Collect uses in iterable
        self._collect_uses(node.iter, dfg, cfg)
        
        # Recurse into body
        self._collect_declarations(ast.Module(body=node.body), dfg, cfg)
        if node.orelse:
            self._collect_declarations(ast.Module(body=node.orelse), dfg, cfg)
    
    def _handle_comprehension_var(
        self,
        node: ast.comprehension,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle comprehension loop variable."""
        if isinstance(node.target, ast.Name) and self._is_user_variable(node.target.id):
            line = getattr(node, 'lineno', 0)
            df_node = self._create_df_node(
                variable_name=node.target.id,
                state=VariableState.DEFINED,
                line_number=line,
                scope=self._current_scope,
            )
            dfg.add_node(df_node)
    
    def _handle_nested_function(
        self,
        node: ast.AST,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle nested function definitions."""
        func_name = node.name  # type: ignore
        self._scopes[func_name] = ScopeInfo(func_name, self._get_scope())
        old_scope = self._current_scope
        self._current_scope = func_name
        
        # Parameters are definitions
        for param in node.args.args:  # type: ignore
            if param.arg != 'self' and self._is_user_variable(param.arg):
                line = getattr(param, 'lineno', 0)
                df_node = self._create_df_node(
                    variable_name=param.arg,
                    state=VariableState.DEFINED,
                    line_number=line,
                    scope=func_name,
                )
                dfg.add_node(df_node)
                self._scopes[func_name].add_definition(param.arg, df_node.id)
        
        # Process function body
        self._collect_declarations(ast.Module(body=node.body), dfg, cfg)  # type: ignore
        
        self._current_scope = old_scope
    
    def _handle_class_def(
        self,
        node: ast.ClassDef,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle class definitions."""
        class_name = node.name
        self._scopes[class_name] = ScopeInfo(class_name, self._get_scope())
        old_scope = self._current_scope
        self._current_scope = class_name
        
        self._collect_declarations(ast.Module(body=node.body), dfg, cfg)
        
        self._current_scope = old_scope
    
    def _handle_with(
        self,
        node: ast.With,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle with statement context managers."""
        line = getattr(node, 'lineno', 0)
        cfg_node_id = self._find_cfg_node_for_line(cfg, line)
        
        for item in node.items:
            # Collect uses in context expression
            self._collect_uses(item.context_expr, dfg, cfg)
            
            # Record variable binding if present
            if item.optional_vars:
                if isinstance(item.optional_vars, ast.Name):
                    if self._is_user_variable(item.optional_vars.id):
                        df_node = self._create_df_node(
                            variable_name=item.optional_vars.id,
                            state=VariableState.DEFINED,
                            cfg_node_id=cfg_node_id,
                            line_number=line,
                            scope=self._current_scope,
                        )
                        dfg.add_node(df_node)
                        self._get_scope().add_definition(item.optional_vars.id, df_node.id)
        
        self._collect_declarations(ast.Module(body=node.body), dfg, cfg)
    
    def _handle_except_handler(
        self,
        node: ast.ExceptHandler,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Handle except clause variable definition."""
        if node.name and self._is_user_variable(node.name):
            line = getattr(node, 'lineno', 0)
            cfg_node_id = self._find_cfg_node_for_line(cfg, line)
            df_node = self._create_df_node(
                variable_name=node.name,
                state=VariableState.DEFINED,
                cfg_node_id=cfg_node_id,
                line_number=line,
                scope=self._current_scope,
            )
            dfg.add_node(df_node)
            self._get_scope().add_definition(node.name, df_node.id)
        
        self._collect_declarations(ast.Module(body=node.body), dfg, cfg)
    
    def _handle_global(self, node: ast.Global) -> None:
        """Handle global declarations."""
        self._global_names.update(node.names)
    
    def _handle_nonlocal(self, node: ast.Nonlocal) -> None:
        """Handle nonlocal declarations."""
        self._nonlocal_names.update(node.names)
    
    def _collect_uses(
        self,
        node: ast.AST,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Collect all variable uses in an AST subtree."""
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if self._is_user_variable(child.id) and child.id not in self._global_names:
                    line = getattr(child, 'lineno', 0)
                    cfg_node_id = self._find_cfg_node_for_line(cfg, line)
                    source = self._get_source_line(child)
                    
                    df_node = self._create_df_node(
                        variable_name=child.id,
                        state=VariableState.USED,
                        cfg_node_id=cfg_node_id,
                        line_number=line,
                        source_code=source,
                        scope=self._current_scope,
                    )
                    dfg.add_node(df_node)
            elif isinstance(child, ast.Attribute):
                # Track attribute access as use of the base object
                if isinstance(child.value, ast.Name):
                    if self._is_user_variable(child.value.id):
                        line = getattr(child, 'lineno', 0)
                        cfg_node_id = self._find_cfg_node_for_line(cfg, line)
                        df_node = self._create_df_node(
                            variable_name=child.value.id,
                            state=VariableState.USED,
                            cfg_node_id=cfg_node_id,
                            line_number=line,
                            scope=self._current_scope,
                        )
                        dfg.add_node(df_node)
    
    def _build_def_use_chains(
        self,
        dfg: DataFlowGraph,
        cfg: ControlFlowGraph,
    ) -> None:
        """Build definition-use chains connecting definitions to uses.
        
        For each use of a variable, find all definitions that could reach
        that use and create edges in the DFG.
        """
        # Group nodes by scope and variable
        by_scope_var: Dict[str, Dict[str, Dict[VariableState, List[DFNode]]]] = {}
        
        for df_node in dfg.nodes.values():
            scope = df_node.scope
            var = df_node.variable_name
            
            if scope not in by_scope_var:
                by_scope_var[scope] = {}
            if var not in by_scope_var[scope]:
                by_scope_var[scope][var] = {
                    VariableState.DEFINED: [],
                    VariableState.USED: [],
                    VariableState.MODIFIED: [],
                }
            
            by_scope_var[scope][var][df_node.state].append(df_node)
        
        # For each scope and variable, connect defs to uses
        for scope, var_dict in by_scope_var.items():
            for var_name, state_dict in var_dict.items():
                defs = state_dict.get(VariableState.DEFINED, [])
                mods = state_dict.get(VariableState.MODIFIED, [])
                uses = state_dict.get(VariableState.USED, [])
                
                all_defs = defs + mods
                
                # For each use, connect to definitions
                # Simple approach: connect to all previous definitions
                # More sophisticated: use CFG ordering to determine reaching defs
                
                for use_node in uses:
                    for def_node in all_defs:
                        if def_node.id != use_node.id:
                            # Check if definition could reach use via CFG
                            if self._could_reach(cfg, def_node, use_node):
                                dfg.add_edge(DFEdge(
                                    source=def_node.id,
                                    target=use_node.id,
                                    variable=var_name,
                                ))
                
                # Connect modifications to subsequent uses/definitions
                for mod_node in mods:
                    for use_node in uses:
                        if mod_node.id != use_node.id and self._could_reach(cfg, mod_node, use_node):
                            dfg.add_edge(DFEdge(
                                source=mod_node.id,
                                target=use_node.id,
                                variable=var_name,
                            ))
    
    def _could_reach(
        self,
        cfg: ControlFlowGraph,
        def_node: DFNode,
        use_node: DFNode,
    ) -> bool:
        """Check if a definition could reach a use based on CFG structure.
        
        Uses a simple topological check: if there's a path from the
        definition's CFG node to the use's CFG node, the definition
        could reach the use.
        
        Args:
            cfg: Control Flow Graph
            def_node: Definition node
            use_node: Use node
            
        Returns:
            True if definition could reach use
        """
        # Simple heuristic: if definition line <= use line, assume reachable
        # This is not precise for all cases but works for most structured code
        if def_node.line_number == 0 or use_node.line_number == 0:
            return True  # Unknown, assume reachable
        
        if def_node.line_number > use_node.line_number:
            return False  # Definition after use - can't reach
        
        # Same scope check
        if def_node.scope == use_node.scope:
            return True
        
        # Cross-scope: definition in outer scope can reach inner scope
        # Check if def_node's scope is an ancestor of use_node's scope
        def_scope = self._scopes.get(def_node.scope)
        use_scope = self._scopes.get(use_node.scope)
        
        if def_scope and use_scope:
            current = use_scope
            while current:
                if current.name == def_scope.name:
                    return True
                current = current.parent
        
        return True
    
    def _get_scope(self) -> ScopeInfo:
        """Get the current scope info."""
        return self._scopes[self._current_scope]
    
    def _get_source_line(self, node: ast.AST) -> str:
        """Get the source code line for an AST node."""
        line_start = getattr(node, 'lineno', None)
        line_end = getattr(node, 'end_lineno', line_start)
        
        if line_start and line_end and self._source_lines:
            start_idx = line_start - 1
            end_idx = line_end
            if 0 <= start_idx < len(self._source_lines):
                return " ".join(self._source_lines[start_idx:end_idx]).strip()
        return ""


def build_dfg(
    tree: ast.Module,
    cfg: ControlFlowGraph,
    source_code: str = "",
) -> DataFlowGraph:
    """Convenience function to build a DFG from AST and CFG.
    
    Args:
        tree: Python AST module
        cfg: Control Flow Graph for the code
        source_code: Original source code string
        
    Returns:
        DataFlowGraph representing data dependencies
    """
    builder = DataFlowGraphBuilder()
    return builder.build(tree, cfg, source_code)