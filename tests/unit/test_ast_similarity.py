"""
Unit tests for AST Similarity Algorithm

Tests the AST-based similarity algorithm with:
- Tree edit distance
- Control flow graph comparison
- Data flow graph comparison
- Pattern matching
- Complexity metrics
"""

import pytest
from src.backend.backend.core.similarity.ast_similarity import (
    ASTSimilarity, ASTNode, TreeEditDistance,
    ControlFlowGraph, DataFlowGraph
)


class TestASTNode:
    """Test AST node functionality."""
    
    def test_node_creation(self):
        """Test basic node creation."""
        node = ASTNode('IDENTIFIER', 'x')
        assert node.node_type == 'IDENTIFIER'
        assert node.value == 'x'
        assert node.children == []
    
    def test_node_with_children(self):
        """Test node with children."""
        child = ASTNode('VARIABLE', 'x')
        parent = ASTNode('EXPR', 'assign', children=[child])
        
        assert len(parent.children) == 1
        assert child.parent == parent
    
    def test_to_tuple(self):
        """Test tuple conversion for hashing."""
        node = ASTNode('ROOT', '', children=[
            ASTNode('LEAF', 'a'),
            ASTNode('LEAF', 'b')
        ])
        
        tup = node.to_tuple()
        assert len(tup) == 3
        assert tup[0] == 'ROOT'
        assert len(tup[2]) == 2
    
    def test_subtree_size(self):
        """Test subtree size calculation."""
        node = ASTNode('ROOT', '', children=[
            ASTNode('A', '', children=[ASTNode('B', '')]),
            ASTNode('C', '')
        ])
        
        assert node.subtree_size() == 4  # ROOT + A + B + C
    
    def test_normalize_variable_names(self):
        """Test variable name normalization."""
        root = ASTNode('ROOT', '', children=[
            ASTNode('IDENTIFIER', 'myVar'),
            ASTNode('FUNCTION', '', children=[
                ASTNode('IDENTIFIER', 'myVar'),
                ASTNode('IDENTIFIER', 'otherVar')
            ])
        ])
        
        root.normalize_variable_names()
        
        # Both myVar instances should be normalized to same name
        assert root.children[0].value == 'var_0'
        assert root.children[1].children[0].value == 'var_0'
        assert root.children[1].children[1].value == 'var_1'
    
    def test_get_subtrees(self):
        """Test subtree extraction."""
        root = ASTNode('ROOT', '', children=[
            ASTNode('A', '', children=[ASTNode('B', ''), ASTNode('C', '')]),
            ASTNode('D', '')
        ])
        
        subtrees = root.get_subtrees(min_size=1)
        assert len(subtrees) > 0
    
    def test_hash_subtree(self):
        """Test subtree hashing."""
        node1 = ASTNode('A', 'x', children=[ASTNode('B', 'y')])
        node2 = ASTNode('A', 'x', children=[ASTNode('B', 'y')])
        
        assert node1.hash_subtree() == node2.hash_subtree()


class TestTreeEditDistance:
    """Test tree edit distance calculation."""
    
    def test_identical_trees(self):
        """Test identical trees have zero distance."""
        ted = TreeEditDistance()
        
        tree = ASTNode('ROOT', '', children=[
            ASTNode('IDENTIFIER', 'x'),
            ASTNode('OPERATOR', '+'),
            ASTNode('IDENTIFIER', 'y')
        ])
        
        distance = ted.calculate_distance(tree, tree)
        assert distance == 0.0
    
    def test_different_trees(self):
        """Test different trees have positive distance."""
        ted = TreeEditDistance()
        
        tree_a = ASTNode('ROOT', '', children=[
            ASTNode('IDENTIFIER', 'a')
        ])
        tree_b = ASTNode('ROOT', '', children=[
            ASTNode('IDENTIFIER', 'b')
        ])
        
        distance = ted.calculate_distance(tree_a, tree_b)
        assert distance > 0
    
    def test_empty_trees(self):
        """Test empty trees have zero distance."""
        ted = TreeEditDistance()
        tree = ASTNode('ROOT', '')
        
        distance = ted.calculate_distance(tree, tree)
        assert distance == 0.0


class TestControlFlowGraph:
    """Test control flow graph functionality."""
    
    def test_cfg_creation(self):
        """Test CFG creation."""
        cfg = ControlFlowGraph()
        
        block_0 = cfg.add_block(['int x = 0'])
        block_1 = cfg.add_block(['x++'])
        
        cfg.add_edge(block_0, block_1, 'flow')
        
        assert len(cfg.basic_blocks) == 2
        assert len(cfg.edges) == 1


class TestASTSimilarity:
    """Test AST similarity algorithm."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.algorithm = ASTSimilarity()
    
    def test_identical_code(self):
        """Test identical code returns high similarity."""
        tokens = [
            {'type': 'KEYWORD', 'value': 'def'},
            {'type': 'FUNCTION', 'value': 'test'},
            {'type': 'OPERATOR', 'value': '('},
            {'type': 'OPERATOR', 'value': ')'},
            {'type': 'OPERATOR', 'value': ':'},
            {'type': 'KEYWORD', 'value': 'pass'},
        ]
        
        parsed_a = {'tokens': tokens, 'raw': 'def test(): pass'}
        parsed_b = {'tokens': tokens, 'raw': 'def test(): pass'}
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        assert score > 0.8
    
    def test_variable_renaming(self):
        """Test renamed variables still match well."""
        tokens_a = [
            {'type': 'KEYWORD', 'value': 'if'},
            {'type': 'VARIABLE', 'value': 'x'},
            {'type': 'OPERATOR', 'value': ':'},
            {'type': 'KEYWORD', 'value': 'print'},
            {'type': 'VARIABLE', 'value': 'x'},
        ]
        tokens_b = [
            {'type': 'KEYWORD', 'value': 'if'},
            {'type': 'VARIABLE', 'value': 'y'},
            {'type': 'OPERATOR', 'value': ':'},
            {'type': 'KEYWORD', 'value': 'print'},
            {'type': 'VARIABLE', 'value': 'y'},
        ]
        
        parsed_a = {'tokens': tokens_a, 'raw': 'if x: print(x)'}
        parsed_b = {'tokens': tokens_b, 'raw': 'if y: print(y)'}
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        assert score > 0.8
    
    def test_different_code(self):
        """Test different code returns low similarity."""
        tokens_a = [
            {'type': 'KEYWORD', 'value': 'if'},
            {'type': 'VARIABLE', 'value': 'x'},
        ]
        tokens_b = [
            {'type': 'KEYWORD', 'value': 'for'},
            {'type': 'VARIABLE', 'value': 'i'},
        ]
        
        parsed_a = {'tokens': tokens_a, 'raw': 'if x'}
        parsed_b = {'tokens': tokens_b, 'raw': 'for i'}
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        assert score < 0.7
    
    def test_empty_code(self):
        """Test empty code comparison."""
        parsed_empty = {'tokens': [], 'raw': ''}
        score = self.algorithm.compare(parsed_empty, parsed_empty)
        assert score == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])