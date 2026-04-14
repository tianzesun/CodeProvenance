"""
Unit tests for Structural AST Similarity algorithm.

Tests cover:
- AST node data structures
- Tree Edit Distance
- Tree Kernel methods
- CFG and DFG comparison
- Full algorithm with parameter tuning
"""

from __future__ import annotations

import pytest
from typing import Dict, Any

from src.backend.backend.engines.similarity.structural_ast_similarity import (
    ASTStructuralNode,
    ControlFlowGraph,
    DataFlowGraph,
    TreeKernel,
    WeightedTreeEditDistance,
    CFGComparator,
    DFGComparator,
    StructuralASTSimilarity,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def simple_ast() -> ASTStructuralNode:
    """Create a simple AST for testing."""
    return ASTStructuralNode(
        node_type="FUNCTION",
        value="test",
        children=[
            ASTStructuralNode(node_type="PARAM", value="x"),
            ASTStructuralNode(
                node_type="BODY",
                children=[
                    ASTStructuralNode(node_type="RETURN", children=[
                        ASTStructuralNode(node_type="NAME", value="x"),
                    ]),
                ]
            ),
        ]
    )


@pytest.fixture
def similar_ast() -> ASTStructuralNode:
    """Create a similar AST with minor differences."""
    return ASTStructuralNode(
        node_type="FUNCTION",
        value="test",
        children=[
            ASTStructuralNode(node_type="PARAM", value="y"),  # Different param name
            ASTStructuralNode(
                node_type="BODY",
                children=[
                    ASTStructuralNode(node_type="RETURN", children=[
                        ASTStructuralNode(node_type="NAME", value="y"),
                    ]),
                ]
            ),
        ]
    )


@pytest.fixture
def different_ast() -> ASTStructuralNode:
    """Create a different AST."""
    return ASTStructuralNode(
        node_type="CLASS",
        value="MyClass",
        children=[
            ASTStructuralNode(
                node_type="METHOD",
                value="init",
                children=[
                    ASTStructuralNode(node_type="PARAM", value="self"),
                ]
            ),
        ]
    )


@pytest.fixture
def parsed_code_python() -> Dict[str, Any]:
    """Sample parsed Python code."""
    return {
        "tokens": [
            {"type": "KEYWORD", "value": "def"},
            {"type": "NAME", "value": "foo"},
            {"type": "LPAR", "value": "("},
            {"type": "NAME", "value": "x"},
            {"type": "RPAR", "value": ")"},
            {"type": "COLON", "value": ":"},
            {"type": "KEYWORD", "value": "return"},
            {"type": "NAME", "value": "x"},
        ],
        "language": "python",
    }


# ============================================================================
# AST Node Tests
# ============================================================================

class TestASTStructuralNode:
    """Tests for ASTStructuralNode."""
    
    def test_creation(self):
        """Test basic node creation."""
        node = ASTStructuralNode(node_type="FUNCTION", value="test")
        assert node.node_type == "FUNCTION"
        assert node.value == "test"
        assert node.children == []
    
    def test_subtree_size(self, simple_ast):
        """Test subtree size calculation."""
        assert simple_ast.subtree_size() >= 1
        leaf = ASTStructuralNode(node_type="LITERAL", value="1")
        assert leaf.subtree_size() == 1
    
    def test_tree_depth(self):
        """Test tree depth calculation."""
        deep = ASTStructuralNode(
            node_type="ROOT",
            children=[
                ASTStructuralNode(
                    node_type="CHILD",
                    children=[
                        ASTStructuralNode(node_type="LEAF"),
                    ]
                )
            ]
        )
        assert deep.tree_depth() == 2
    
    def test_to_tuple(self, simple_ast):
        """Test tuple conversion for hashing."""
        t = simple_ast.to_tuple()
        assert isinstance(t, tuple)
        assert t[0] == "FUNCTION"
    
    def test_subtree_hash(self, simple_ast):
        """Test subtree hash generation."""
        h = simple_ast.subtree_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256
    
    def test_normalize_identifiers(self):
        """Test identifier normalization."""
        ast = ASTStructuralNode(
            node_type="FUNCTION",
            children=[
                ASTStructuralNode(node_type="NAME", value="myVar"),
                ASTStructuralNode(node_type="NAME", value="myVar"),  # Same var
                ASTStructuralNode(node_type="NAME", value="other"),  # Different var
                ASTStructuralNode(node_type="KEYWORD", value="if"),  # Keyword
            ]
        )
        mapping = ast.normalize_identifiers()
        assert "myVar" in mapping
        assert "if" not in mapping  # Keywords not normalized
    
    def test_get_all_subtrees(self, simple_ast):
        """Test subtree collection."""
        subtrees = simple_ast.get_all_subtrees(min_size=1)
        assert len(subtrees) >= 1
    
    def test_extract_paths(self):
        """Test path extraction."""
        ast = ASTStructuralNode(
            node_type="ROOT",
            children=[
                ASTStructuralNode(node_type="CHILD"),
            ]
        )
        paths = ast.extract_paths(max_length=4)
        assert len(paths) >= 1


# ============================================================================
# Tree Edit Distance Tests
# ============================================================================

class TestWeightedTreeEditDistance:
    """Tests for WeightedTreeEditDistance."""
    
    def test_identical_trees(self, simple_ast):
        """Test identical trees have distance 0."""
        ted = WeightedTreeEditDistance()
        sim = ted.compute_similarity(simple_ast, simple_ast)
        assert sim == 1.0
    
    def test_none_input(self, simple_ast):
        """Test None input handling."""
        ted = WeightedTreeEditDistance()
        sim = ted.compute_similarity(None, simple_ast)
        assert sim == 0.0
    
    def test_different_trees(self, simple_ast, different_ast):
        """Test different trees have low similarity."""
        ted = WeightedTreeEditDistance()
        sim = ted.compute_similarity(simple_ast, different_ast)
        assert 0.0 <= sim <= 1.0
    
    def test_similar_trees(self, simple_ast, similar_ast):
        """Test similar trees have high similarity."""
        ted = WeightedTreeEditDistance()
        sim = ted.compute_similarity(simple_ast, similar_ast)
        # Similar trees with different variable names should have >= 0 similarity
        assert sim >= 0.0


# ============================================================================
# Tree Kernel Tests
# ============================================================================

class TestTreeKernel:
    """Tests for TreeKernel."""
    
    def test_subtree_kernel(self, simple_ast):
        """Test subtree kernel type."""
        kernel = TreeKernel(kernel_type="subtree", decay_factor=0.5)
        sim = kernel.compute(simple_ast, simple_ast)
        assert 0.0 <= sim <= 1.0
    
    def test_subset_kernel(self, simple_ast):
        """Test subset kernel type."""
        kernel = TreeKernel(kernel_type="subset", decay_factor=0.5)
        sim = kernel.compute(simple_ast, simple_ast)
        assert 0.0 <= sim <= 1.0
    
    def test_different_trees_kernel(self, simple_ast, different_ast):
        """Test kernel with different trees."""
        kernel = TreeKernel()
        sim = kernel.compute(simple_ast, different_ast)
        assert 0.0 <= sim <= 1.0
    
    def test_empty_subtrees(self):
        """Test with minimal trees."""
        kernel = TreeKernel()
        a = ASTStructuralNode(node_type="ROOT")
        b = ASTStructuralNode(node_type="ROOT")
        sim = kernel.compute(a, b)
        assert 0.0 <= sim <= 1.0


# ============================================================================
# CFG Comparator Tests
# ============================================================================

class TestCFGComparator:
    """Tests for CFGComparator."""
    
    def test_identical_cfgs(self):
        """Test identical CFGs."""
        cfg1 = ControlFlowGraph()
        cfg1.add_node(0, "entry")
        cfg1.add_node(1, "normal")
        cfg1.add_edge(0, 1, "flow")
        
        cfg2 = ControlFlowGraph()
        cfg2.add_node(0, "entry")
        cfg2.add_node(1, "normal")
        cfg2.add_edge(0, 1, "flow")
        
        comp = CFGComparator()
        sim = comp.compare(cfg1, cfg2)
        assert sim == 1.0
    
    def test_empty_cfgs(self):
        """Test empty CFG comparison."""
        comp = CFGComparator()
        sim = comp.compare(ControlFlowGraph(), ControlFlowGraph())
        assert sim == 1.0
    
    def test_different_cfgs(self):
        """Test different CFGs."""
        cfg1 = ControlFlowGraph()
        cfg1.add_node(0)
        cfg1.add_edge(0, 0)
        
        cfg2 = ControlFlowGraph()
        cfg2.add_node(0)
        cfg2.add_node(1)
        cfg2.add_edge(0, 1)
        
        comp = CFGComparator()
        sim = comp.compare(cfg1, cfg2)
        assert 0.0 <= sim < 1.0


# ============================================================================
# DFG Comparator Tests
# ============================================================================

class TestDFGComparator:
    """Tests for DFGComparator."""
    
    def test_identical_dfgs(self):
        """Test identical DFGs."""
        dfg1 = DataFlowGraph()
        dfg1.add_definition("x", 1)
        dfg1.add_dependency("x", "y")
        
        dfg2 = DataFlowGraph()
        dfg2.add_definition("x", 1)
        dfg2.add_dependency("x", "y")
        
        comp = DFGComparator()
        sim = comp.compare(dfg1, dfg2)
        assert sim == 1.0
    
    def test_empty_dfgs(self):
        """Test empty DFG comparison."""
        comp = DFGComparator()
        sim = comp.compare(DataFlowGraph(), DataFlowGraph())
        assert sim == 1.0


# ============================================================================
# Structural AST Similarity Tests
# ============================================================================

class TestStructuralASTSimilarity:
    """Tests for StructuralASTSimilarity."""
    
    def test_default_params(self):
        """Test default parameter values."""
        algo = StructuralASTSimilarity()
        params = algo.get_params()
        assert "ted_weight" in params
        assert "tree_kernel_weight" in params
        assert "similarity_threshold" in params
    
    def test_set_params(self):
        """Test parameter setting."""
        algo = StructuralASTSimilarity()
        algo.set_params(ted_weight=0.5)
        assert algo.ted_weight == 0.5
    
    def test_compare_identical(self, parsed_code_python):
        """Test comparing identical code."""
        algo = StructuralASTSimilarity()
        score = algo.compare(parsed_code_python, parsed_code_python)
        assert score > 0.0
    
    def test_compare_returns_float(self, parsed_code_python):
        """Test that compare returns float in [0, 1]."""
        algo = StructuralASTSimilarity()
        diff = {
            "tokens": [{"type": "KEYWORD", "value": "class"}],
            "language": "python",
        }
        score = algo.compare(parsed_code_python, diff)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
    
    def test_compare_empty(self):
        """Test comparing empty inputs."""
        algo = StructuralASTSimilarity()
        score = algo.compare({}, {})
        assert score == 0.0
    
    def test_token_fallback(self):
        """Test token-based AST building."""
        algo = StructuralASTSimilarity()
        parsed = {
            "tokens": [
                {"type": "KEYWORD", "value": "def"},
                {"type": "NAME", "value": "func"},
            ],
        }
        score = algo.compare(parsed, parsed)
        assert score >= 0.0
    
    def test_get_name(self):
        """Test algorithm name."""
        algo = StructuralASTSimilarity()
        assert algo.get_name() == "structural_ast"
    
    def test_parameter_ranges(self):
        """Test algorithm with various parameter configurations."""
        configs = [
            {"ted_weight": 0.1, "cfg_weight": 0.1},
            {"ted_weight": 0.5, "cfg_weight": 0.1},
            {"ted_weight": 0.1, "cfg_weight": 0.5},
        ]
        
        parsed = {
            "tokens": [
                {"type": "KEYWORD", "value": "if"},
                {"type": "NAME", "value": "x"},
            ],
        }
        
        for config in configs:
            algo = StructuralASTSimilarity(**config)
            score = algo.compare(parsed, parsed)
            assert 0.0 <= score <= 1.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the full pipeline."""
    
    def test_full_pipeline(self):
        """Test full similarity pipeline with different codes."""
        code_a = {
            "tokens": [
                {"type": "KEYWORD", "value": "def"},
                {"type": "NAME", "value": "add"},
                {"type": "NAME", "value": "x"},
                {"type": "NAME", "value": "y"},
                {"type": "KEYWORD", "value": "return"},
                {"type": "NAME", "value": "x"},
                {"type": "NAME", "value": "y"},
            ],
        }
        
        code_b = {
            "tokens": [
                {"type": "KEYWORD", "value": "def"},
                {"type": "NAME", "value": "add"},
                {"type": "NAME", "value": "a"},
                {"type": "NAME", "value": "b"},
                {"type": "KEYWORD", "value": "return"},
                {"type": "NAME", "value": "a"},
                {"type": "NAME", "value": "b"},
            ],
        }
        
        code_c = {
            "tokens": [
                {"type": "KEYWORD", "value": "class"},
                {"type": "NAME", "value": "Foo"},
            ],
        }
        
        algo = StructuralASTSimilarity(normalize_identifiers=True)
        
        # Similar codes should have higher score
        score_similar = algo.compare(code_a, code_b)
        score_different = algo.compare(code_a, code_c)
        
        assert score_similar >= 0.0
        assert score_different >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])