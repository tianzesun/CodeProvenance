"""
Combined CFG + DFG Builder for Python AST.

This module provides a unified builder that constructs both Control Flow Graph
and Data Flow Graph from Python AST in a single pass, ensuring proper
correspondence between the two graphs.
"""

import ast
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    CFGEdge,
    CFGNode,
    CombinedGraph,
    ControlFlowGraph,
    DataFlowGraph,
    DFEdge,
    DFNode,
    EdgeType,
    VariableState,
)
from .cfg_builder import ControlFlowGraphBuilder
from .dfg_builder import DataFlowGraphBuilder, ScopeInfo


class CFGDFGBuilder:
    """Unified builder that constructs both CFG and DFG from Python AST.
    
    This builder creates a CombinedGraph containing:
    - A Control Flow Graph representing execution paths
    - A Data Flow Graph representing variable dependencies
    - Cross-references between CFG nodes and DFG nodes
    
    Usage:
        builder = CFGDFGBuilder()
        combined = builder.build(source_code)
    """
    
    def __init__(self) -> None:
        self._cfg_builder: ControlFlowGraphBuilder = ControlFlowGraphBuilder()
        self._dfg_builder: DataFlowGraphBuilder = DataFlowGraphBuilder()
    
    def build(self, source_code: str) -> CombinedGraph:
        """Build combined CFG + DFG from source code.
        
        Args:
            source_code: Python source code string
            
        Returns:
            CombinedGraph containing both CFG and DFG
            
        Raises:
            SyntaxError: If source code cannot be parsed
        """
        tree = ast.parse(source_code)
        return self.build_from_ast(tree, source_code)
    
    def build_from_ast(self, tree: ast.Module, source_code: str = "") -> CombinedGraph:
        """Build combined CFG + DFG from AST.
        
        Args:
            tree: Python AST module
            source_code: Original source code string
            
        Returns:
            CombinedGraph containing both CFG and DFG
        """
        # Step 1: Build CFG
        cfg = self._cfg_builder.build(tree, source_code)
        
        # Step 2: Build DFG using CFG
        dfg = self._dfg_builder.build(tree, cfg, source_code)
        
        # Step 3: Create combined graph
        combined = CombinedGraph(
            cfg=cfg,
            dfg=dfg,
            source_code=source_code,
            metadata={
                "language": "python",
                "ast_nodes": sum(1 for _ in ast.walk(tree)),
            }
        )
        
        return combined
    
    def build_for_function(
        self,
        source_code: str,
        function_name: str,
    ) -> Optional[CombinedGraph]:
        """Build combined CFG + DFG for a specific function.
        
        Args:
            source_code: Python source code string
            function_name: Name of function to extract
            
        Returns:
            CombinedGraph for the function, or None if not found
        """
        tree = ast.parse(source_code)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    # Build CFG for function
                    cfg = self._cfg_builder.build_from_function(node, source_code)
                    
                    # Build DFG for function
                    dfg = self._dfg_builder.build_for_function(node, cfg, source_code)
                    
                    return CombinedGraph(
                        cfg=cfg,
                        dfg=dfg,
                        source_code=source_code,
                        metadata={
                            "language": "python",
                            "function_name": function_name,
                        }
                    )
        
        return None
    
    def build_for_class(
        self,
        source_code: str,
        class_name: str,
    ) -> Optional[CombinedGraph]:
        """Build combined CFG + DFG for a specific class.
        
        Args:
            source_code: Python source code string
            class_name: Name of class to extract
            
        Returns:
            CombinedGraph for the class, or None if not found
        """
        tree = ast.parse(source_code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == class_name:
                    cfg = self._cfg_builder.build_from_class(node, source_code)
                    
                    dfg = self._dfg_builder.build(tree, cfg, source_code)
                    
                    return CombinedGraph(
                        cfg=cfg,
                        dfg=dfg,
                        source_code=source_code,
                        metadata={
                            "language": "python",
                            "class_name": class_name,
                        }
                    )
        
        return None


def build_combined(source_code: str) -> CombinedGraph:
    """Convenience function to build combined CFG + DFG from source code.
    
    Args:
        source_code: Python source code string
        
    Returns:
        CombinedGraph containing both CFG and DFG
        
    Raises:
        SyntaxError: If source code cannot be parsed
    """
    builder = CFGDFGBuilder()
    return builder.build(source_code)


def build_combined_for_function(
    source_code: str,
    function_name: str,
) -> Optional[CombinedGraph]:
    """Convenience function to build combined CFG + DFG for a function.
    
    Args:
        source_code: Python source code string
        function_name: Name of function to analyze
        
    Returns:
        CombinedGraph for the function, or None if not found
    """
    builder = CFGDFGBuilder()
    return builder.build_for_function(source_code, function_name)


# ─────────────────────────────────────────────
# Graph Analysis Utilities
# ─────────────────────────────────────────────


def compute_cyclomatic_complexity(cfg: ControlFlowGraph) -> int:
    """Compute the cyclomatic complexity of a CFG.
    
    Cyclomatic complexity = E - N + 2P
    where E = edges, N = nodes, P = connected components (usually 1)
    
    Args:
        cfg: Control Flow Graph
        
    Returns:
        Cyclomatic complexity value
    """
    edges = cfg.edge_count
    nodes = cfg.node_count
    components = 1  # Assuming connected graph
    
    return max(1, edges - nodes + 2 * components)


def find_reachable_nodes(cfg: ControlFlowGraph, start: int) -> Set[int]:
    """Find all nodes reachable from a start node in the CFG.
    
    Args:
        cfg: Control Flow Graph
        start: Starting node ID
        
    Returns:
        Set of reachable node IDs
    """
    visited: Set[int] = set()
    queue = [start]
    
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        
        if current in cfg.nodes:
            for successor_id in cfg.nodes[current].get_successor_ids():
                if successor_id not in visited:
                    queue.append(successor_id)
    
    return visited


def find_dominance_frontier(cfg: ControlFlowGraph) -> Dict[int, Set[int]]:
    """Compute dominance frontiers for all nodes.
    
    The dominance frontier of a node n is the set of all nodes m such that
    n dominates a predecessor of m but does not strictly dominate m.
    
    Args:
        cfg: Control Flow Graph
        
    Returns:
        Dictionary mapping node ID to its dominance frontier
    """
    dominators = cfg.compute_dominators()
    frontier: Dict[int, Set[int]] = {n: set() for n in cfg.nodes}
    
    for node_id in cfg.nodes:
        preds = cfg.nodes[node_id].get_predecessor_ids()
        
        if len(preds) >= 2:
            for pred_id in preds:
                runner = pred_id
                while runner != dominators.get(node_id, set()).pop() if dominators.get(node_id) else runner:
                    if runner in frontier:
                        frontier[runner].add(node_id)
                    # Get immediate dominator
                    runner_doms = dominators.get(runner, set())
                    runners = [r for r in runner_doms if r != runner]
                    if runners:
                        runner = runners[0]
                    else:
                        break
    
    return frontier


def extract_variable_dependencies(combined: CombinedGraph) -> Dict[str, List[Tuple[int, int]]]:
    """Extract variable dependency chains from the combined graph.
    
    Args:
        combined: Combined CFG + DFG
        
    Returns:
        Dictionary mapping variable name to list of (def_id, use_id) pairs
    """
    deps: Dict[str, List[Tuple[int, int]]] = {}
    
    for edge in combined.dfg.edges:
        if edge.variable not in deps:
            deps[edge.variable] = []
        deps[edge.variable].append((edge.source, edge.target))
    
    return deps


def compute_code_metrics(combined: CombinedGraph) -> Dict[str, float]:
    """Compute various code metrics from the combined graph.
    
    Args:
        combined: Combined CFG + DFG
        
    Returns:
        Dictionary of metric names to values
    """
    cfg = combined.cfg
    dfg = combined.dfg
    
    def get_all_variables_in_scope(scope: str) -> Set[str]:
        """Get all variables defined or used in a scope."""
        vars = set()
        for node in dfg.nodes.values():
            if node.scope == scope:
                vars.add(node.variable_name)
        return vars
    
    metrics = {
        "cyclomatic_complexity": compute_cyclomatic_complexity(cfg),
        "cfg_nodes": cfg.node_count,
        "cfg_edges": cfg.edge_count,
        "dfg_nodes": dfg.node_count,
        "dfg_edges": dfg.edge_count,
        "num_variables": len(dfg.variables),
        "num_scopes": len(cfg.get_all_scopes()),
        "avg_defs_per_variable": (
            sum(len(defs) for defs in dfg.variable_definitions.values()) /
            max(1, len(dfg.variable_definitions))
        ),
        "max_variable_scope_size": max(
            (len(nodes) for nodes in cfg.scopes.values()),
            default=0
        ),
    }
    
    return metrics


def serialize_graph(combined: CombinedGraph) -> Dict:
    """Serialize combined graph to JSON-serializable dictionary.
    
    Args:
        combined: Combined CFG + DFG
        
    Returns:
        Dictionary representation suitable for JSON serialization
    """
    return combined.to_dict()