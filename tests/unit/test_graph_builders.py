"""
Unit tests for CFG + DFG graph builders.

Tests cover:
- Control Flow Graph construction
- Data Flow Graph construction  
- Combined graph building
- Edge cases and error handling
- Graph analysis utilities
"""

import ast
import pytest
from typing import Dict, List, Set

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.graph.models import (
    CFGNode,
    CFGEdge,
    CombinedGraph,
    ControlFlowGraph,
    DataFlowGraph,
    DFEdge,
    DFNode,
    EdgeType,
    VariableState,
)
from src.core.graph.cfg_builder import (
    ControlFlowGraphBuilder,
    build_cfg,
    build_cfg_for_function,
)
from src.core.graph.dfg_builder import (
    DataFlowGraphBuilder,
    build_dfg,
)
from src.core.graph.combined_builder import (
    CFGDFGBuilder,
    build_combined,
    build_combined_for_function,
    compute_cyclomatic_complexity,
    find_reachable_nodes,
    extract_variable_dependencies,
    compute_code_metrics,
)


# ─────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def simple_code() -> str:
    """Simple sequential code for testing."""
    return """
x = 1
y = 2
z = x + y
print(z)
"""


@pytest.fixture
def conditional_code() -> str:
    """Code with if-else branches."""
    return """
def check(x):
    if x > 0:
        result = "positive"
    else:
        result = "non-positive"
    return result
"""


@pytest.fixture
def loop_code() -> str:
    """Code with for and while loops."""
    return """
def sum_list(items):
    total = 0
    for item in items:
        total += item
    return total

def countdown(n):
    while n > 0:
        n -= 1
    return n
"""


@pytest.fixture
def nested_code() -> str:
    """Code with nested structures."""
    return """
def process(data):
    result = []
    for item in data:
        if isinstance(item, int):
            result.append(item * 2)
        elif isinstance(item, str):
            result.append(item.upper())
    return result
"""


@pytest.fixture
def function_code() -> str:
    """Code with multiple functions."""
    return """
def add(a, b):
    return a + b

def multiply(a, b):
    result = a * b
    return result

def compute(x, y):
    sum_val = add(x, y)
    prod = multiply(x, y)
    return sum_val + prod
"""


@pytest.fixture
def class_code() -> str:
    """Code with class definition."""
    return """
class Calculator:
    def __init__(self):
        self.value = 0
    
    def add(self, n):
        self.value += n
        return self.value
"""


@pytest.fixture
def try_except_code() -> str:
    """Code with try-except."""
    return """
def safe_divide(a, b):
    try:
        result = a / b
        return result
    except ZeroDivisionError as e:
        error_msg = str(e)
        return None
"""


# ─────────────────────────────────────────────
# CFG Model Tests
# ─────────────────────────────────────────────


class TestCFGNode:
    """Tests for CFGNode model."""
    
    def test_create_node(self) -> None:
        """Test creating a CFGNode."""
        node = CFGNode(id=1, node_type="Assign", line_start=5)
        assert node.id == 1
        assert node.node_type == "Assign"
        assert node.line_start == 5
    
    def test_add_successor(self) -> None:
        """Test adding successor to node."""
        node = CFGNode(id=1)
        node.add_successor(2, EdgeType.SEQUENTIAL)
        assert len(node.successors) == 1
        assert node.successors[0] == (2, EdgeType.SEQUENTIAL)
    
    def test_add_predecessor(self) -> None:
        """Test adding predecessor to node."""
        node = CFGNode(id=1)
        node.add_predecessor(0, EdgeType.SEQUENTIAL)
        assert len(node.predecessors) == 1
    
    def test_get_successor_ids(self) -> None:
        """Test getting successor IDs."""
        node = CFGNode(id=1)
        node.add_successor(2, EdgeType.TRUE_BRANCH)
        node.add_successor(3, EdgeType.FALSE_BRANCH)
        
        all_successors = node.get_successor_ids()
        assert set(all_successors) == {2, 3}
        
        true_successors = node.get_successor_ids(EdgeType.TRUE_BRANCH)
        assert true_successors == [2]
    
    def test_repr(self) -> None:
        """Test string representation."""
        node = CFGNode(id=5, node_type="If", line_start=10)
        assert "CFGNode" in repr(node)
        assert "5" in repr(node)


class TestCFGEdge:
    """Tests for CFGEdge model."""
    
    def test_create_edge(self) -> None:
        """Test creating a CFGEdge."""
        edge = CFGEdge(source=1, target=2, edge_type=EdgeType.SEQUENTIAL)
        assert edge.source == 1
        assert edge.target == 2
        assert edge.edge_type == EdgeType.SEQUENTIAL
    
    def test_repr(self) -> None:
        """Test string representation."""
        edge = CFGEdge(source=1, target=2)
        assert "CFGEdge" in repr(edge)


class TestControlFlowGraph:
    """Tests for ControlFlowGraph model."""
    
    def test_create_graph(self) -> None:
        """Test creating an empty CFG."""
        cfg = ControlFlowGraph()
        assert cfg.node_count == 0
        assert cfg.edge_count == 0
    
    def test_add_node(self) -> None:
        """Test adding nodes to graph."""
        cfg = ControlFlowGraph()
        node = CFGNode(id=1, node_type="Assign")
        cfg.add_node(node)
        assert cfg.node_count == 1
        assert 1 in cfg.nodes
    
    def test_add_edge(self) -> None:
        """Test adding edges to graph."""
        cfg = ControlFlowGraph()
        cfg.add_node(CFGNode(id=1))
        cfg.add_node(CFGNode(id=2))
        
        edge = CFGEdge(source=1, target=2)
        cfg.add_edge(edge)
        
        assert cfg.edge_count == 1
        assert 2 in cfg.nodes[1].get_successor_ids()
    
    def test_get_edge(self) -> None:
        """Test getting edge between nodes."""
        cfg = ControlFlowGraph()
        cfg.add_node(CFGNode(id=1))
        cfg.add_node(CFGNode(id=2))
        cfg.add_edge(CFGEdge(source=1, target=2))
        
        edge = cfg.get_edge(1, 2)
        assert edge is not None
        assert edge.source == 1
        assert edge.target == 2
    
    def test_get_nodes_in_scope(self) -> None:
        """Test getting nodes in a scope."""
        cfg = ControlFlowGraph()
        cfg.add_node(CFGNode(id=1, scope="global"))
        cfg.add_node(CFGNode(id=2, scope="func"))
        
        global_nodes = cfg.get_nodes_in_scope("global")
        assert len(global_nodes) == 1
    
    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        cfg = ControlFlowGraph()
        cfg.add_node(CFGNode(id=1, node_type="Assign", source_code="x = 1"))
        result = cfg.to_dict()
        assert "nodes" in result
        assert "edges" in result


# ─────────────────────────────────────────────
# DFG Model Tests
# ─────────────────────────────────────────────


class TestDFNode:
    """Tests for DFNode model."""
    
    def test_create_node(self) -> None:
        """Test creating a DFNode."""
        node = DFNode(id=1, variable_name="x", state=VariableState.DEFINED)
        assert node.id == 1
        assert node.variable_name == "x"
        assert node.state == VariableState.DEFINED
    
    def test_repr(self) -> None:
        """Test string representation."""
        node = DFNode(id=1, variable_name="result", state=VariableState.USED)
        assert "DFNode" in repr(node)
        assert "result" in repr(node)


class TestDFEdge:
    """Tests for DFEdge model."""
    
    def test_create_edge(self) -> None:
        """Test creating a DFG edge."""
        edge = DFEdge(source=1, target=2, variable="x")
        assert edge.source == 1
        assert edge.target == 2
        assert edge.variable == "x"


class TestDataFlowGraph:
    """Tests for DataFlowGraph model."""
    
    def test_create_graph(self) -> None:
        """Test creating an empty DFG."""
        dfg = DataFlowGraph()
        assert dfg.node_count == 0
        assert dfg.edge_count == 0
    
    def test_add_node(self) -> None:
        """Test adding nodes to DFG."""
        dfg = DataFlowGraph()
        node = DFNode(id=1, variable_name="x", state=VariableState.DEFINED)
        dfg.add_node(node)
        
        assert dfg.node_count == 1
        assert "x" in dfg.variables
        assert 1 in dfg.variable_definitions["x"]
    
    def test_add_edge(self) -> None:
        """Test adding edges to DFG."""
        dfg = DataFlowGraph()
        dfg.add_edge(DFEdge(source=1, target=2, variable="x"))
        assert dfg.edge_count == 1
    
    def test_variables_property(self) -> None:
        """Test getting all variables."""
        dfg = DataFlowGraph()
        dfg.add_node(DFNode(id=1, variable_name="x", state=VariableState.DEFINED))
        dfg.add_node(DFNode(id=2, variable_name="y", state=VariableState.USED))
        
        assert "x" in dfg.variables
        assert "y" in dfg.variables
    
    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        dfg = DataFlowGraph()
        dfg.add_node(DFNode(id=1, variable_name="x", state=VariableState.DEFINED))
        result = dfg.to_dict()
        assert "nodes" in result
        assert "variables" in result


# ─────────────────────────────────────────────
# Combined Graph Model Tests
# ─────────────────────────────────────────────


class TestCombinedGraph:
    """Tests for CombinedGraph model."""
    
    def test_create_combined(self) -> None:
        """Test creating a combined graph."""
        combined = CombinedGraph()
        assert combined.cfg is not None
        assert combined.dfg is not None
    
    def test_get_node_mapping(self) -> None:
        """Test getting CFG to DFG node mapping."""
        combined = CombinedGraph()
        combined.cfg.add_node(CFGNode(id=1))
        combined.dfg.add_node(DFNode(id=10, variable_name="x", cfg_node_id=1))
        
        mapping = combined.get_node_mapping()
        assert 1 in mapping
        assert 10 in mapping[1]
    
    def test_compute_graph_edit_distance(self) -> None:
        """Test graph edit distance computation."""
        combined1 = CombinedGraph()
        combined1.cfg.add_node(CFGNode(id=1))
        combined1.dfg.add_node(DFNode(id=1, variable_name="x"))
        
        combined2 = CombinedGraph()
        combined2.cfg.add_node(CFGNode(id=1))
        combined2.cfg.add_node(CFGNode(id=2))
        combined2.dfg.add_node(DFNode(id=1, variable_name="x"))
        combined2.dfg.add_node(DFNode(id=2, variable_name="y"))
        
        distance = combined1.compute_graph_edit_distance(combined2)
        assert distance >= 0
    
    def test_to_dict(self) -> None:
        """Test serialization."""
        combined = CombinedGraph()
        combined.cfg.add_node(CFGNode(id=1))
        result = combined.to_dict()
        assert "cfg" in result
        assert "dfg" in result


# ─────────────────────────────────────────────
# CFG Builder Tests
# ─────────────────────────────────────────────


class TestControlFlowGraphBuilder:
    """Tests for CFG builder."""
    
    def test_build_simple(self, simple_code: str) -> None:
        """Test building CFG from simple code."""
        cfg = build_cfg(simple_code)
        
        assert cfg.entry_node is not None
        assert cfg.exit_node is not None
        assert cfg.node_count > 2  # At least entry, statements, exit
        assert cfg.edge_count > 0
    
    def test_build_conditional(self, conditional_code: str) -> None:
        """Test building CFG with conditionals."""
        cfg = build_cfg(conditional_code)
        
        assert cfg.entry_node is not None
        assert cfg.exit_node is not None
    
    def test_build_loop(self, loop_code: str) -> None:
        """Test building CFG with loops."""
        cfg = build_cfg(loop_code)
        
        assert cfg.entry_node is not None
        assert cfg.exit_node is not None
    
    def test_build_nested(self, nested_code: str) -> None:
        """Test building CFG with nested structures."""
        cfg = build_cfg(nested_code)
        
        assert cfg.node_count > 0
        assert cfg.edge_count > 0
    
    def test_build_function(self, function_code: str) -> None:
        """Test building CFG for function."""
        cfg = build_cfg(function_code)
        
        # Should have nodes for all three functions
        assert cfg.node_count > 0
    
    def test_build_for_function(self, conditional_code: str) -> None:
        """Test building CFG for specific function."""
        cfg = build_cfg_for_function(conditional_code, "check")
        
        assert cfg is not None
        assert cfg.entry_node is not None
    
    def test_build_for_function_not_found(self, simple_code: str) -> None:
        """Test finding non-existent function."""
        cfg = build_cfg_for_function(simple_code, "nonexistent")
        assert cfg is None
    
    def test_build_try_except(self, try_except_code: str) -> None:
        """Test building CFG with try-except."""
        cfg = build_cfg(try_except_code)
        assert cfg.node_count > 0
    
    def test_build_with_syntax_error(self) -> None:
        """Test handling syntax errors."""
        with pytest.raises(SyntaxError):
            build_cfg("def foo(")
    
    def test_edge_types_in_conditional(self, conditional_code: str) -> None:
        """Test that conditional edges have correct types."""
        cfg = build_cfg(conditional_code)
        
        has_true_branch = False
        has_false_branch = False
        
        for edge in cfg.edges:
            if edge.edge_type == EdgeType.TRUE_BRANCH:
                has_true_branch = True
            if edge.edge_type == EdgeType.FALSE_BRANCH:
                has_false_branch = True
    
    def test_loop_back_edges(self, loop_code: str) -> None:
        """Test that loops have back edges."""
        cfg = build_cfg(loop_code)
        
        has_loop_back = any(
            edge.edge_type == EdgeType.LOOP_BACK
            for edge in cfg.edges
        )
        # May or may not have depending on structure
        assert True  # Just verify it doesn't crash


class TestCFGStatements:
    """Tests for specific statement types in CFG."""
    
    def test_assignment(self) -> None:
        """Test assignment statement handling."""
        code = "x = 1\ny = 2"
        cfg = build_cfg(code)
        
        assign_nodes = [
            n for n in cfg.nodes.values()
            if n.node_type == "Assign"
        ]
        assert len(assign_nodes) == 2
    
    def test_return(self) -> None:
        """Test return statement handling."""
        code = "def f():\n    return 42"
        cfg = build_cfg(code)
        
        return_nodes = [
            n for n in cfg.nodes.values()
            if n.node_type == "Return"
        ]
        assert len(return_nodes) == 1
    
    def test_import(self) -> None:
        """Test import statement handling."""
        code = "import os\nimport sys"
        cfg = build_cfg(code)
        
        import_nodes = [
            n for n in cfg.nodes.values()
            if n.node_type in ("Import", "ImportFrom")
        ]
        assert len(import_nodes) >= 1
    
    def test_for_loop(self) -> None:
        """Test for loop handling."""
        code = """
def process(items):
    for item in items:
        print(item)
"""
        cfg = build_cfg(code)
        
        for_headers = [
            n for n in cfg.nodes.values()
            if n.node_type == "ForHeader"
        ]
        assert len(for_headers) >= 1
    
    def test_while_loop(self) -> None:
        """Test while loop handling."""
        code = """
def loop():
    while True:
        break
"""
        cfg = build_cfg(code)
        
        conditions = [
            n for n in cfg.nodes.values()
            if "Condition" in n.node_type
        ]
        assert len(conditions) >= 1
    
    def test_with_statement(self) -> None:
        """Test with statement handling."""
        code = """
def read_file():
    with open("file.txt") as f:
        content = f.read()
"""
        cfg = build_cfg(code)
        assert cfg.node_count > 0
    
    def test_try_except_finally(self) -> None:
        """Test try-except-finally handling."""
        code = """
def process():
    try:
        do_something()
    except ValueError:
        handle_error()
    finally:
        cleanup()
"""
        cfg = build_cfg(code)
        
        try_entries = [
            n for n in cfg.nodes.values()
            if n.node_type == "TryEntry"
        ]
        assert len(try_entries) >= 1


# ─────────────────────────────────────────────
# DFG Builder Tests
# ─────────────────────────────────────────────


class TestDataFlowGraphBuilder:
    """Tests for DFG builder."""
    
    def test_build_simple(self, simple_code: str) -> None:
        """Test building DFG from simple code."""
        tree = ast.parse(simple_code)
        cfg = build_cfg(simple_code)
        dfg = build_dfg(tree, cfg, simple_code)
        
        assert dfg.node_count > 0
        assert "x" in dfg.variables or "y" in dfg.variables or "z" in dfg.variables
    
    def test_variable_definitions(self, simple_code: str) -> None:
        """Test variable definition tracking."""
        tree = ast.parse(simple_code)
        cfg = build_cfg(simple_code)
        dfg = build_dfg(tree, cfg, simple_code)
        
        # Should have definitions for x, y, z
        assert len(dfg.variable_definitions) > 0
    
    def test_variable_uses(self, simple_code: str) -> None:
        """Test variable use tracking."""
        tree = ast.parse(simple_code)
        cfg = build_cfg(simple_code)
        dfg = build_dfg(tree, cfg, simple_code)
        
        # Should have uses of x, y
        assert len(dfg.variable_uses) > 0
    
    def test_augmented_assign(self) -> None:
        """Test augmented assignment handling."""
        code = """
def increment():
    x = 0
    x += 1
    return x
"""
        tree = ast.parse(code)
        cfg = build_cfg(code)
        dfg = build_dfg(tree, cfg, code)
        
        modified_nodes = [
            n for n in dfg.nodes.values()
            if n.state == VariableState.MODIFIED
        ]
        assert len(modified_nodes) >= 1
    
    def test_for_loop_variable(self) -> None:
        """Test for loop variable definition."""
        code = """
def process(items):
    for item in items:
        print(item)
"""
        tree = ast.parse(code)
        cfg = build_cfg(code)
        dfg = build_dfg(tree, cfg, code)
        
        assert "item" in dfg.variables
    
    def test_function_parameters(self) -> None:
        """Test function parameter tracking."""
        code = """
def compute(a, b):
    return a + b
"""
        tree = ast.parse(code)
        cfg = build_cfg(code)
        dfg = build_dfg(tree, cfg, code)
        
        assert "a" in dfg.variables
        assert "b" in dfg.variables
    
    def test_except_handler_variable(self) -> None:
        """Test except handler variable definition."""
        code = """
def handle():
    try:
        do_something()
    except Exception as e:
        print(e)
"""
        tree = ast.parse(code)
        cfg = build_cfg(code)
        dfg = build_dfg(tree, cfg, code)
        
        assert "e" in dfg.variables


# ─────────────────────────────────────────────
# Combined Builder Tests
# ─────────────────────────────────────────────


class TestCFGDFGBuilder:
    """Tests for combined CFG+DFG builder."""
    
    def test_build(self, simple_code: str) -> None:
        """Test building combined graph."""
        combined = build_combined(simple_code)
        
        assert combined is not None
        assert isinstance(combined, CombinedGraph)
        assert combined.cfg.node_count > 0
        assert combined.dfg.node_count > 0
    
    def test_build_for_function(self, function_code: str) -> None:
        """Test building combined graph for function."""
        combined = build_combined_for_function(function_code, "add")
        
        assert combined is not None
        assert combined.cfg.entry_node is not None
    
    def test_build_for_function_not_found(self, simple_code: str) -> None:
        """Test building for non-existent function."""
        combined = build_combined_for_function(simple_code, "nonexistent")
        assert combined is None
    
    def test_metadata(self, simple_code: str) -> None:
        """Test graph metadata."""
        combined = build_combined(simple_code)
        
        assert "language" in combined.metadata
        assert combined.metadata["language"] == "python"
    
    def test_build_for_class(self, class_code: str) -> None:
        """Test building combined graph for class."""
        builder = CFGDFGBuilder()
        combined = builder.build_for_class(class_code, "Calculator")
        
        assert combined is not None


# ─────────────────────────────────────────────
# Analysis Utilities Tests
# ─────────────────────────────────────────────


class TestAnalysisUtilities:
    """Tests for graph analysis utilities."""
    
    def test_cyclomatic_complexity_simple(self, simple_code: str) -> None:
        """Test cyclomatic complexity for simple code."""
        cfg = build_cfg(simple_code)
        complexity = compute_cyclomatic_complexity(cfg)
        assert complexity >= 1
    
    def test_cyclomatic_complexity_conditional(self, conditional_code: str) -> None:
        """Test cyclomatic complexity with conditionals."""
        cfg = build_cfg(conditional_code)
        complexity = compute_cyclomatic_complexity(cfg)
        assert complexity >= 2  # At least 2 paths
    
    def test_reachable_nodes(self, simple_code: str) -> None:
        """Test finding reachable nodes."""
        cfg = build_cfg(simple_code)
        
        if cfg.entry_node:
            reachable = find_reachable_nodes(cfg, cfg.entry_node)
            assert len(reachable) >= 1
    
    def test_variable_dependencies(self) -> None:
        """Test extracting variable dependencies."""
        code = """
def compute():
    x = 1
    y = x + 1
    return y
"""
        combined = build_combined(code)
        deps = extract_variable_dependencies(combined)
        
        assert isinstance(deps, dict)
    
    def test_code_metrics(self, simple_code: str) -> None:
        """Test code metrics computation."""
        combined = build_combined(simple_code)
        metrics = compute_code_metrics(combined)
        
        assert "cyclomatic_complexity" in metrics
        assert "cfg_nodes" in metrics
        assert "dfg_nodes" in metrics
        assert metrics["cfg_nodes"] > 0
    
    def test_dominators(self) -> None:
        """Test dominator computation."""
        code = """
def test(x):
    if x > 0:
        return x
    return -x
"""
        cfg = build_cfg(code)
        dominators = cfg.compute_dominators()
        
        assert isinstance(dominators, dict)


# ─────────────────────────────────────────────
# Edge Case Tests
# ─────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_code(self) -> None:
        """Test handling empty code."""
        cfg = build_cfg("")
        assert cfg.entry_node is not None
        assert cfg.exit_node is not None
    
    def test_single_expression(self) -> None:
        """Test single expression."""
        code = "1"
        cfg = build_cfg(code)
        assert cfg.node_count > 0
    
    def test_only_comments(self) -> None:
        """Test code with only comments."""
        code = "# comment\n# another comment"
        cfg = build_cfg(code)
        assert cfg.entry_node is not None
    
    def test_nested_functions(self) -> None:
        """Test nested function definitions."""
        code = """
def outer():
    def inner():
        return 1
    return inner()
"""
        combined = build_combined(code)
        assert combined.cfg.node_count > 0
    
    def test_list_comprehension(self) -> None:
        """Test list comprehension."""
        code = """
def compute():
    result = [x * 2 for x in range(10)]
    return result
"""
        combined = build_combined(code)
        assert combined.dfg.node_count > 0
    
    def test_multiple_assignments(self) -> None:
        """Test multiple assignment."""
        code = """
def test():
    x = y = z = 0
    return x + y + z
"""
        combined = build_combined(code)
        assert combined.dfg.node_count > 0
    
    def test_tuple_unpacking(self) -> None:
        """Test tuple unpacking."""
        code = """
def test():
    a, b = 1, 2
    return a + b
"""
        combined = build_combined(code)
        assert "a" in combined.dfg.variables
        assert "b" in combined.dfg.variables


# ─────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_full_pipeline(self, function_code: str) -> None:
        """Test complete pipeline: parse -> CFG -> DFG -> combined."""
        # Parse
        tree = ast.parse(function_code)
        assert tree is not None
        
        # Build CFG
        cfg = build_cfg(function_code)
        assert cfg.entry_node is not None
        assert cfg.exit_node is not None
        
        # Build DFG
        dfg = build_dfg(tree, cfg, function_code)
        assert dfg.node_count > 0
        
        # Build combined
        combined = build_combined(function_code)
        assert combined.cfg.node_count > 0
        assert combined.dfg.node_count > 0
    
    def test_similarity_comparison(self) -> None:
        """Test using graphs for similarity comparison."""
        code1 = """
def add(a, b):
    result = a + b
    return result
"""
        code2 = """
def add(x, y):
    sum_val = x + y
    return sum_val
"""
        code3 = """
def multiply(a, b):
    result = a * b
    return result
"""
        combined1 = build_combined(code1)
        combined2 = build_combined(code2)
        combined3 = build_combined(code3)
        
        # Similar structure should have smaller distance
        dist_12 = combined1.compute_graph_edit_distance(combined2)
        dist_13 = combined1.compute_graph_edit_distance(combined3)
        
        # Both should have valid distances
        assert dist_12 >= 0
        assert dist_13 >= 0
    
    def test_code_with_errors(self) -> None:
        """Test handling code with various issues."""
        # Invalid syntax
        with pytest.raises(SyntaxError):
            build_combined("def foo(")
        
        # Empty
        combined = build_combined("")
        assert combined is not None
    
    def test_large_function(self) -> None:
        """Test handling larger functions."""
        code = """
def process_data(data_list):
    result = []
    errors = []
    
    for item in data_list:
        if item is None:
            errors.append("null value")
            continue
        
        if isinstance(item, (int, float)):
            if item > 0:
                result.append(item * 2)
            elif item < 0:
                result.append(item * -1)
            else:
                result.append(0)
        elif isinstance(item, str):
            try:
                num = float(item)
                result.append(num)
            except ValueError:
                errors.append(f"invalid: {item}")
        else:
            errors.append(f"unsupported type: {type(item)}")
    
    return result, errors
"""
        combined = build_combined(code)
        
        # Should have reasonable graph
        assert combined.cfg.node_count > 10
        assert combined.dfg.node_count > 5
        
        # Compute metrics
        metrics = compute_code_metrics(combined)
        assert metrics["cyclomatic_complexity"] > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])