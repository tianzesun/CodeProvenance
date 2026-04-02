"""
Data models for Control Flow Graph (CFG) and Data Flow Graph (DFG).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import ast


class EdgeType(Enum):
    """Types of edges in the Control Flow Graph."""
    SEQUENTIAL = "sequential"           # Normal flow to next statement
    TRUE_BRANCH = "true_branch"         # Conditional branch when condition is True
    FALSE_BRANCH = "false_branch"       # Conditional branch when condition is False
    LOOP_BACK = "loop_back"            # Back edge in loops
    LOOP_EXIT = "loop_exit"            # Exit edge from loops
    BREAK = "break"                    # Break statement
    CONTINUE = "continue"              # Continue statement
    RETURN = "return"                  # Return statement
    EXCEPTION = "exception"            # Exception flow
    FUNCTION_CALL = "function_call"    # Function call edge
    FUNCTION_RETURN = "function_return"  # Function return edge


class VariableState(Enum):
    """State of a variable at a program point."""
    DEFINED = "defined"        # Variable is assigned
    USED = "used"             # Variable is read
    MODIFIED = "modified"     # Variable is modified (e.g., +=)
    KILLED = "killed"         # Variable is no longer live


@dataclass
class CFGNode:
    """A node in the Control Flow Graph representing a program statement or expression.
    
    Attributes:
        id: Unique identifier for this node
        ast_node: The original AST node this represents
        node_type: Type of AST node (e.g., 'Assign', 'If', 'For')
        source_code: Source code string for this node
        line_start: Starting line number in source
        line_end: Ending line number in source
        successors: List of (node_id, edge_type) tuples
        predecessors: List of (node_id, edge_type) tuples
        scope: Lexical scope identifier (for nested functions/classes)
        metadata: Additional metadata
    """
    id: int
    ast_node: Optional[ast.AST] = None
    node_type: str = ""
    source_code: str = ""
    line_start: int = 0
    line_end: int = 0
    successors: List[Tuple[int, EdgeType]] = field(default_factory=list)
    predecessors: List[Tuple[int, EdgeType]] = field(default_factory=list)
    scope: str = "global"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Computed fields for analysis
    dominated_nodes: Set[int] = field(default_factory=set, init=False)
    post_dominated_nodes: Set[int] = field(default_factory=set, init=False)
    
    def __repr__(self) -> str:
        return f"CFGNode({self.id}: {self.node_type} at line {self.line_start})"
    
    def add_successor(self, node_id: int, edge_type: EdgeType = EdgeType.SEQUENTIAL) -> None:
        """Add a successor edge to this node."""
        if node_id not in [s[0] for s in self.successors]:
            self.successors.append((node_id, edge_type))
    
    def add_predecessor(self, node_id: int, edge_type: EdgeType = EdgeType.SEQUENTIAL) -> None:
        """Add a predecessor edge to this node."""
        if node_id not in [p[0] for p in self.predecessors]:
            self.predecessors.append((node_id, edge_type))
    
    def get_successor_ids(self, edge_type: Optional[EdgeType] = None) -> List[int]:
        """Get IDs of successor nodes, optionally filtered by edge type."""
        if edge_type is None:
            return [s[0] for s in self.successors]
        return [s[0] for s in self.successors if s[1] == edge_type]
    
    def get_predecessor_ids(self, edge_type: Optional[EdgeType] = None) -> List[int]:
        """Get IDs of predecessor nodes, optionally filtered by edge type."""
        if edge_type is None:
            return [p[0] for p in self.predecessors]
        return [p[0] for p in self.predecessors if p[1] == edge_type]


@dataclass
class CFGEdge:
    """An edge in the Control Flow Graph.
    
    Attributes:
        source: Source node ID
        target: Target node ID
        edge_type: Type of control flow
        condition: Condition expression (for conditional branches)
        metadata: Additional metadata
    """
    source: int
    target: int
    edge_type: EdgeType = EdgeType.SEQUENTIAL
    condition: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"CFGEdge({self.source} -> {self.target}: {self.edge_type.value})"


@dataclass
class ControlFlowGraph:
    """A Control Flow Graph representing the execution flow of a program.
    
    Attributes:
        nodes: Dictionary mapping node ID to CFGNode
        edges: List of CFGEdge objects
        entry_node: Entry point node ID
        exit_node: Exit point node ID  
        source_code: Original source code
        ast_tree: Original AST tree
        scopes: Dictionary mapping scope name to list of node IDs in that scope
    """
    nodes: Dict[int, CFGNode] = field(default_factory=dict)
    edges: List[CFGEdge] = field(default_factory=list)
    entry_node: Optional[int] = None
    exit_node: Optional[int] = None
    source_code: str = ""
    ast_tree: Optional[ast.Module] = None
    scopes: Dict[str, List[int]] = field(default_factory=dict)
    
    @property
    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)
    
    @property
    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self.edges)
    
    def add_node(self, node: CFGNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        if node.scope not in self.scopes:
            self.scopes[node.scope] = []
        self.scopes[node.scope].append(node.id)
    
    def add_edge(self, edge: CFGEdge) -> None:
        """Add an edge to the graph and update node successor/predecessor lists."""
        self.edges.append(edge)
        if edge.source in self.nodes:
            self.nodes[edge.source].add_successor(edge.target, edge.edge_type)
        if edge.target in self.nodes:
            self.nodes[edge.target].add_predecessor(edge.source, edge.edge_type)
    
    def get_edge(self, source: int, target: int) -> Optional[CFGEdge]:
        """Get the edge between two nodes."""
        for edge in self.edges:
            if edge.source == source and edge.target == target:
                return edge
        return None
    
    def get_edges(self, source: int, target: Optional[int] = None) -> List[CFGEdge]:
        """Get all edges from a source node, optionally to a specific target."""
        result = []
        for edge in self.edges:
            if edge.source == source:
                if target is None or edge.target == target:
                    result.append(edge)
        return result
    
    def get_nodes_in_scope(self, scope: str) -> List[CFGNode]:
        """Get all nodes in a given scope."""
        return [self.nodes[nid] for nid in self.scopes.get(scope, []) if nid in self.nodes]
    
    def get_all_scopes(self) -> List[str]:
        """Get all scope names in the graph."""
        return list(self.scopes.keys())
    
    def compute_dominators(self) -> Dict[int, Set[int]]:
        """Compute dominator sets for all nodes.
        
        Returns:
            Dictionary mapping node ID to set of nodes that dominate it.
        """
        if self.entry_node is None:
            return {}
        
        # Initialize dominators
        all_nodes = set(self.nodes.keys())
        dom: Dict[int, Set[int]] = {n: all_nodes.copy() for n in all_nodes}
        dom[self.entry_node] = {self.entry_node}
        
        # Iterative fixed-point algorithm
        changed = True
        while changed:
            changed = False
            for node_id in all_nodes:
                if node_id == self.entry_node:
                    continue
                
                node = self.nodes[node_id]
                preds = node.get_predecessor_ids()
                if not preds:
                    continue
                
                # Intersection of predecessors' dominators
                new_dom = set.intersection(*[dom[p] for p in preds if p in dom])
                new_dom.add(node_id)
                
                if new_dom != dom[node_id]:
                    dom[node_id] = new_dom
                    changed = True
        
        # Update nodes with dominator information
        for node_id, dominators in dom.items():
            if node_id in self.nodes:
                self.nodes[node_id].dominated_nodes = dominators
        
        return dom
    
    def compute_post_dominators(self) -> Dict[int, Set[int]]:
        """Compute post-dominator sets for all nodes.
        
        Returns:
            Dictionary mapping node ID to set of nodes that post-dominate it.
        """
        if self.exit_node is None:
            return {}
        
        # Initialize post-dominators (reverse graph)
        all_nodes = set(self.nodes.keys())
        post_dom: Dict[int, Set[int]] = {n: all_nodes.copy() for n in all_nodes}
        post_dom[self.exit_node] = {self.exit_node}
        
        # Build reverse adjacency
        reverse_adj: Dict[int, List[int]] = {n: [] for n in all_nodes}
        for edge in self.edges:
            reverse_adj[edge.target].append(edge.source)
        
        # Iterative fixed-point algorithm
        changed = True
        while changed:
            changed = False
            for node_id in all_nodes:
                if node_id == self.exit_node:
                    continue
                
                succs = reverse_adj.get(node_id, [])
                if not succs:
                    continue
                
                # Intersection of successors' post-dominators
                new_dom = set.intersection(*[post_dom[s] for s in succs if s in post_dom])
                new_dom.add(node_id)
                
                if new_dom != post_dom[node_id]:
                    post_dom[node_id] = new_dom
                    changed = True
        
        # Update nodes with post-dominator information
        for node_id, post_dominators in post_dom.items():
            if node_id in self.nodes:
                self.nodes[node_id].post_dominated_nodes = post_dominators
        
        return post_dom
    
    def to_dict(self) -> Dict[str, Any]:
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
        }


# ─────────────────────────────────────────────
# Data Flow Graph Models
# ─────────────────────────────────────────────


@dataclass
class DFNode:
    """A node in the Data Flow Graph representing a variable definition or use.
    
    Attributes:
        id: Unique identifier for this node
        variable_name: Name of the variable
        state: State of the variable (defined, used, modified, killed)
        cfg_node_id: Corresponding CFG node ID
        line_number: Line number in source
        source_code: Source code snippet
        scope: Lexical scope
        reaching_definitions: Set of definition node IDs that reach this point
        metadata: Additional metadata
    """
    id: int
    variable_name: str
    state: VariableState = VariableState.DEFINED
    cfg_node_id: int = 0
    line_number: int = 0
    source_code: str = ""
    scope: str = "global"
    reaching_definitions: Set[int] = field(default_factory=set, init=False)
    live_out: Set[str] = field(default_factory=set, init=False)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"DFNode({self.id}: {self.variable_name} [{self.state.value}] at line {self.line_number})"


@dataclass
class DFEdge:
    """An edge in the Data Flow Graph representing a data dependency.
    
    Attributes:
        source: Source node ID (definition)
        target: Target node ID (use)
        variable: Variable being tracked
        edge_type: Type of data dependency
        metadata: Additional metadata
    """
    source: int
    target: int
    variable: str
    edge_type: str = "data_dependency"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"DFEdge({self.source} --{self.variable}--> {self.target})"


@dataclass
class DataFlowGraph:
    """A Data Flow Graph representing data dependencies in a program.
    
    Attributes:
        nodes: Dictionary mapping node ID to DFNode
        edges: List of DFEdge objects
        variable_definitions: Dictionary mapping variable name to set of definition node IDs
        variable_uses: Dictionary mapping variable name to set of use node IDs
        cfg_reference: Reference to the associated CFG
        source_code: Original source code
    """
    nodes: Dict[int, DFNode] = field(default_factory=dict)
    edges: List[DFEdge] = field(default_factory=list)
    variable_definitions: Dict[str, Set[int]] = field(default_factory=dict)
    variable_uses: Dict[str, Set[int]] = field(default_factory=dict)
    cfg_reference: Optional[ControlFlowGraph] = None
    source_code: str = ""
    
    @property
    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)
    
    @property
    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self.edges)
    
    @property
    def variables(self) -> Set[str]:
        """Get all variables tracked in the data flow graph."""
        return set(self.variable_definitions.keys()) | set(self.variable_uses.keys())
    
    def add_node(self, node: DFNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        
        # Track definitions and uses
        if node.state in (VariableState.DEFINED, VariableState.MODIFIED):
            if node.variable_name not in self.variable_definitions:
                self.variable_definitions[node.variable_name] = set()
            self.variable_definitions[node.variable_name].add(node.id)
        
        if node.state in (VariableState.USED, VariableState.MODIFIED):
            if node.variable_name not in self.variable_uses:
                self.variable_uses[node.variable_name] = set()
            self.variable_uses[node.variable_name].add(node.id)
    
    def add_edge(self, edge: DFEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)
    
    def get_definition_chains(self, variable: str) -> List[List[int]]:
        """Get all definition-use chains for a variable.
        
        Returns:
            List of chains, where each chain is a list of node IDs from def to use.
        """
        if variable not in self.variable_definitions:
            return []
        
        chains = []
        for def_id in self.variable_definitions[variable]:
            # BFS to find all reachable uses
            visited = set()
            queue = [def_id]
            chain = [def_id]
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                
                for edge in self.edges:
                    if edge.source == current and edge.variable == variable:
                        chain.append(edge.target)
                        queue.append(edge.target)
            
            if len(chain) > 1:
                chains.append(chain)
        
        return chains
    
    def compute_reaching_definitions(self) -> Dict[int, Set[int]]:
        """Compute reaching definitions for each node.
        
        Returns:
            Dictionary mapping node ID to set of reaching definition node IDs.
        """
        cfg = self.cfg_reference
        if cfg is None or cfg.entry_node is None:
            return {}
        
        # Initialize
        all_nodes = set(self.nodes.keys())
        reaching: Dict[int, Set[int]] = {n: set() for n in all_nodes}
        
        # For each definition node, add to its own reaching set
        for var, def_ids in self.variable_definitions.items():
            for def_id in def_ids:
                if def_id in reaching:
                    reaching[def_id].add(def_id)
        
        # Build CFG-based worklist
        worklist = list(cfg.nodes.keys())
        
        # Iterate until fixed point
        changed = True
        max_iterations = 100
        iteration = 0
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            
            for node_id in worklist:
                if node_id not in cfg.nodes:
                    continue
                
                # Get predecessors from CFG
                cfg_node = cfg.nodes[node_id]
                preds = cfg_node.get_predecessor_ids()
                
                for pred_id in preds:
                    # Transfer function: add definitions, kill same-variable definitions
                    new_defs = reaching.get(pred_id, set()).copy()
                    
                    if node_id in self.nodes:
                        df_node = self.nodes[node_id]
                        if df_node.state == VariableState.DEFINED:
                            # Kill previous definitions of same variable
                            same_var_defs = self.variable_definitions.get(df_node.variable_name, set())
                            new_defs = new_defs - same_var_defs
                            new_defs.add(node_id)
                
                new_reaching = set()
                for pred_id in preds:
                    new_reaching.update(reaching.get(pred_id, set()))
                
                if node_id in self.nodes:
                    df_node = self.nodes[node_id]
                    if df_node.state == VariableState.DEFINED:
                        same_var_defs = self.variable_definitions.get(df_node.variable_name, set())
                        new_reaching = new_reaching - same_var_defs
                        new_reaching.add(node_id)
                
                if new_reaching != reaching.get(node_id, set()):
                    reaching[node_id] = new_reaching
                    changed = True
                    if node_id in self.nodes:
                        self.nodes[node_id].reaching_definitions = new_reaching
        
        return reaching
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary representation for serialization."""
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "variables": list(self.variables),
            "nodes": {
                nid: {
                    "id": n.id,
                    "variable": n.variable_name,
                    "state": n.state.value,
                    "cfg_node_id": n.cfg_node_id,
                    "line_number": n.line_number,
                    "source_code": n.source_code[:100] if n.source_code else "",
                    "scope": n.scope,
                    "reaching_definitions": list(n.reaching_definitions),
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
    """Combined Control Flow Graph and Data Flow Graph.
    
    This integrates control flow and data flow information for
    comprehensive program analysis.
    
    Attributes:
        cfg: The control flow graph
        dfg: The data flow graph
        source_code: Original source code
        metadata: Additional metadata about the analyzed code
    """
    cfg: ControlFlowGraph = field(default_factory=ControlFlowGraph)
    dfg: DataFlowGraph = field(default_factory=DataFlowGraph)
    source_code: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return (
            f"CombinedGraph(cfg_nodes={self.cfg.node_count}, "
            f"cfg_edges={self.cfg.edge_count}, "
            f"dfg_nodes={self.dfg.node_count}, "
            f"dfg_edges={self.dfg.edge_count})"
        )
    
    def get_node_mapping(self) -> Dict[int, List[int]]:
        """Get mapping from CFG node IDs to DFG node IDs.
        
        Returns:
            Dictionary mapping CFG node ID to list of DFG node IDs.
        """
        mapping: Dict[int, List[int]] = {}
        for df_node_id, df_node in self.dfg.nodes.items():
            cfg_id = df_node.cfg_node_id
            if cfg_id not in mapping:
                mapping[cfg_id] = []
            mapping[cfg_id].append(df_node_id)
        return mapping
    
    def compute_graph_edit_distance(self, other: 'CombinedGraph') -> float:
        """Compute a simple graph edit distance between this graph and another.
        
        This is a simplified heuristic based on node and edge counts.
        For more accurate comparison, structural similarity algorithms
        like graph kernel methods should be used.
        
        Args:
            other: Another CombinedGraph to compare against
            
        Returns:
            Distance value (0 means identical, higher means more different)
        """
        # Control flow distance
        cfg_dist = abs(self.cfg.node_count - other.cfg.node_count) + \
                   abs(self.cfg.edge_count - other.cfg.edge_count)
        
        # Data flow distance
        dfg_dist = abs(self.dfg.node_count - other.dfg.node_count) + \
                   abs(self.dfg.edge_count - other.dfg.edge_count)
        
        # Variable overlap distance
        self_vars = set(self.dfg.variables)
        other_vars = set(other.dfg.variables)
        var_dist = len(self_vars.symmetric_difference(other_vars))
        
        return cfg_dist + dfg_dist + var_dist
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert combined graph to dictionary representation."""
        return {
            "cfg": self.cfg.to_dict(),
            "dfg": self.dfg.to_dict(),
            "metadata": self.metadata,
        }