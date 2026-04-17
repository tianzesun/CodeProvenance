"""
Tests for Enhanced Winnowing Similarity Algorithm

Tests the super-powered winnowing algorithm with:
- Adaptive k-gram sizing
- Weighted token hashing
- Multi-pass fingerprinting
- Variable renaming resistance
- Control flow analysis
- AI detection scoring
"""

import pytest
from src.backend.core.similarity.winnowing_similarity import EnhancedWinnowingSimilarity


class TestEnhancedWinnowingSimilarity:
    """Test suite for Enhanced Winnowing Similarity algorithm"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.algorithm = EnhancedWinnowingSimilarity(
            multi_pass=True,
            adaptive=True,
            weighted=True,
            ai_detection=True
        )
    
    def test_initialization(self):
        """Test algorithm initialization"""
        assert self.algorithm.name == "enhanced_winnowing"
        assert self.algorithm.multi_pass is True
        assert self.algorithm.adaptive is True
        assert self.algorithm.weighted is True
        assert self.algorithm.ai_detection is True
        assert len(self.algorithm.k_sizes) == 4  # [3, 5, 9, 15]
    
    def test_compare_identical_code(self):
        """Test that identical code returns similarity close to 1.0"""
        parsed_a = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'def'},
                {'type': 'FUNCTION', 'value': 'hello'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'LITERAL', 'value': '"hello"'},
            ],
            'raw': 'def hello(): return "hello"'
        }
        
        score = self.algorithm.compare(parsed_a, parsed_a)
        # Should be close to 1.0 for identical code
        assert score > 0.85
    
    def test_compare_empty_code(self):
        """Test comparison of empty code"""
        parsed_empty = {'tokens': [], 'raw': ''}
        
        # Both empty should return 1.0
        score = self.algorithm.compare(parsed_empty, parsed_empty)
        assert score == 1.0
        
        # One empty should return 0.0
        parsed_non_empty = {
            'tokens': [{'type': 'KEYWORD', 'value': 'pass'}],
            'raw': 'pass'
        }
        score = self.algorithm.compare(parsed_empty, parsed_non_empty)
        assert score == 0.0
    
    def test_variable_renaming_resistance(self):
        """Test that variable renaming doesn't significantly affect similarity"""
        # Original code
        parsed_a = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'def'},
                {'type': 'FUNCTION', 'value': 'sum'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'x'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'y'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'VARIABLE', 'value': 'x'},
                {'type': 'OPERATOR', 'value': '+'},
                {'type': 'VARIABLE', 'value': 'y'},
            ],
            'raw': 'def sum(x, y): return x + y'
        }
        
        # Renamed variables
        parsed_b = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'def'},
                {'type': 'FUNCTION', 'value': 'sum'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'a'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'b'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'VARIABLE', 'value': 'a'},
                {'type': 'OPERATOR', 'value': '+'},
                {'type': 'VARIABLE', 'value': 'b'},
            ],
            'raw': 'def sum(a, b): return a + b'
        }
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        # Should show good similarity despite variable renaming
        # (Not expecting 1.0 due to k-gram variations from different variable names)
        assert score > 0.65
    
    def test_control_flow_analysis(self):
        """Test control flow pattern detection"""
        parsed_a = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'if'},
                {'type': 'VARIABLE', 'value': 'x'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'LITERAL', 'value': '1'},
            ],
            'raw': 'if x: return 1'
        }
        
        parsed_b = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'if'},
                {'type': 'VARIABLE', 'value': 'y'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'LITERAL', 'value': '2'},
            ],
            'raw': 'if y: return 2'
        }
        
        # Should detect similar control flow patterns
        cf_a = self.algorithm._extract_control_flow(parsed_a)
        cf_b = self.algorithm._extract_control_flow(parsed_b)
        
        assert 'CONDITIONAL' in cf_a
        assert 'RETURN' in cf_a
        assert 'CONDITIONAL' in cf_b
        assert 'RETURN' in cf_b
    
    def test_ai_detection(self):
        """Test AI-generated code detection"""
        # Human-like code
        human_code = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'def'},
                {'type': 'FUNCTION', 'value': 'fib'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'n'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'if'},
                {'type': 'VARIABLE', 'value': 'n'},
                {'type': 'OPERATOR', 'value': '<'},
                {'type': 'LITERAL', 'value': '2'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'VARIABLE', 'value': 'n'},
            ],
            'raw': 'def fib(n): if n < 2: return n'
        }
        
        ai_score = self.algorithm._detect_ai_generated(human_code)
        # Human code should have low AI score
        assert ai_score < 0.5
    
    def test_adaptive_k_gram(self):
        """Test adaptive k-gram sizing"""
        # Small code should use k=3
        small_tokens = [{'type': 'VARIABLE', 'value': f'v{i}'} for i in range(20)]
        k_small = self.algorithm._get_adaptive_k(small_tokens)
        assert k_small == 3
        
        # Medium code should use k=5
        medium_tokens = [{'type': 'VARIABLE', 'value': f'v{i}'} for i in range(100)]
        k_medium = self.algorithm._get_adaptive_k(medium_tokens)
        assert k_medium == 5
        
        # Large code should use k=9
        large_tokens = [{'type': 'VARIABLE', 'value': f'v{i}'} for i in range(300)]
        k_large = self.algorithm._get_adaptive_k(large_tokens)
        assert k_large == 9
        
        # Very large code should use k=15
        very_large_tokens = [{'type': 'VARIABLE', 'value': f'v{i}'} for i in range(600)]
        k_very_large = self.algorithm._get_adaptive_k(very_large_tokens)
        assert k_very_large == 15
    
    def test_token_normalization(self):
        """Test token normalization"""
        tokens = [
            {'type': 'KEYWORD', 'value': 'def'},
            {'type': 'FUNCTION', 'value': 'test'},
            {'type': 'VARIABLE', 'value': 'myVar'},
            {'type': 'LITERAL', 'value': '42'},
            {'type': 'COMMENT', 'value': '# comment'},
            {'type': 'WHITESPACE', 'value': ' '},
        ]
        
        normalized = self.algorithm._normalize_tokens(tokens)
        
        # Comments and whitespace should be filtered out
        assert len(normalized) == 4
        
        # Check normalization
        assert normalized[0]['value'] == 'def'
        assert normalized[1]['value'] == 'test'
        assert normalized[2]['value'] == 'VAR'  # Variable normalized
        assert normalized[3]['value'] == 'NUM'  # Literal normalized
    
    def test_variable_normalization(self):
        """Test variable name normalization"""
        # Loop variables
        assert self.algorithm._normalize_variable('i') == 'LOOP_VAR'
        assert self.algorithm._normalize_variable('j') == 'LOOP_VAR'
        assert self.algorithm._normalize_variable('k') == 'LOOP_VAR'
        
        # Self/this
        assert self.algorithm._normalize_variable('self') == 'SELF'
        assert self.algorithm._normalize_variable('this') == 'SELF'
        
        # Magic methods
        assert self.algorithm._normalize_variable('__init__') == 'MAGIC_VAR'
        assert self.algorithm._normalize_variable('__str__') == 'MAGIC_VAR'
        
        # Constants
        assert self.algorithm._normalize_variable('MAX_VALUE') == 'CONST'
        assert self.algorithm._normalize_variable('PI') == 'CONST'
        
        # Private variables
        assert self.algorithm._normalize_variable('_private') == 'PRIVATE_VAR'
        assert self.algorithm._normalize_variable('__private') == 'PRIVATE_VAR'
        
        # Generic variables
        assert self.algorithm._normalize_variable('myVar') == 'VAR'
        assert self.algorithm._normalize_variable('count') == 'VAR'
    
    def test_literal_normalization(self):
        """Test literal normalization"""
        # Numbers
        assert self.algorithm._normalize_literal('42') == 'NUM'
        assert self.algorithm._normalize_literal('-10') == 'NUM'
        
        # Booleans
        assert self.algorithm._normalize_literal('true') == 'BOOL'
        assert self.algorithm._normalize_literal('false') == 'BOOL'
        assert self.algorithm._normalize_literal('True') == 'BOOL'
        
        # None/null
        assert self.algorithm._normalize_literal('None') == 'NULL'
        assert self.algorithm._normalize_literal('null') == 'NULL'
        assert self.algorithm._normalize_literal('nil') == 'NULL'
        
        # Strings
        assert self.algorithm._normalize_literal('"hello"') == 'STR'
        assert self.algorithm._normalize_literal("'world'") == 'STR'
    
    def test_weighted_hashing(self):
        """Test weighted token hashing"""
        tokens = [
            {'type': 'KEYWORD', 'value': 'if', 'weight': 2.0},
            {'type': 'VARIABLE', 'value': 'x', 'weight': 1.0},
            {'type': 'KEYWORD', 'value': 'return', 'weight': 2.0},
        ]
        
        hash_val = self.algorithm._weighted_hash_tokens(tokens)
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256 hex digest
    
    def test_jaccard_similarity(self):
        """Test Jaccard similarity calculation"""
        # Identical sets
        assert self.algorithm._jaccard_similarity(['a', 'b', 'c'], ['a', 'b', 'c']) == 1.0
        
        # Disjoint sets
        assert self.algorithm._jaccard_similarity(['a', 'b'], ['c', 'd']) == 0.0
        
        # Partial overlap
        score = self.algorithm._jaccard_similarity(['a', 'b', 'c'], ['b', 'c', 'd'])
        assert 0.0 < score < 1.0
        
        # Empty sets
        assert self.algorithm._jaccard_similarity([], []) == 1.0
        assert self.algorithm._jaccard_similarity(['a'], []) == 0.0
    
    def test_winnowing_algorithm(self):
        """Test winnowing algorithm"""
        hashes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        
        # Window size 3
        fingerprints = self.algorithm._winnow(hashes, 3)
        
        # Should select minimum hash in each window
        assert isinstance(fingerprints, list)
        assert len(fingerprints) > 0
        assert len(fingerprints) <= len(hashes)
    
    def test_multi_pass_comparison(self):
        """Test multi-pass comparison with multiple k-gram sizes"""
        tokens_a = [
            {'type': 'KEYWORD', 'value': 'def'},
            {'type': 'FUNCTION', 'value': 'test'},
            {'type': 'VARIABLE', 'value': 'x'},
        ]
        tokens_b = [
            {'type': 'KEYWORD', 'value': 'def'},
            {'type': 'FUNCTION', 'value': 'test'},
            {'type': 'VARIABLE', 'value': 'y'},
        ]
        
        score = self.algorithm._multi_pass_compare(tokens_a, tokens_b)
        assert 0.0 <= score <= 1.0
    
    def test_single_pass_comparison(self):
        """Test single-pass comparison"""
        tokens_a = [
            {'type': 'KEYWORD', 'value': 'def'},
            {'type': 'FUNCTION', 'value': 'test'},
        ]
        tokens_b = [
            {'type': 'KEYWORD', 'value': 'def'},
            {'type': 'FUNCTION', 'value': 'test'},
        ]
        
        score = self.algorithm._single_pass_compare(tokens_a, tokens_b)
        assert score == 1.0  # Identical tokens
    
    def test_entropy_calculation(self):
        """Test Shannon entropy calculation"""
        # Uniform distribution should have high entropy
        uniform = [10, 10, 10, 10]
        entropy_uniform = self.algorithm._calculate_entropy(uniform)
        assert entropy_uniform > 0
        
        # Non-uniform distribution should have lower entropy
        non_uniform = [100, 1, 1, 1]
        entropy_non_uniform = self.algorithm._calculate_entropy(non_uniform)
        assert entropy_non_uniform < entropy_uniform
    
    def test_different_code_structures(self):
        """Test comparison of different code structures"""
        # Loop vs conditional
        parsed_loop = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'for'},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'KEYWORD', 'value': 'in'},
                {'type': 'VARIABLE', 'value': 'range'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'LITERAL', 'value': '10'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'pass'},
            ],
            'raw': 'for i in range(10): pass'
        }
        
        parsed_conditional = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'if'},
                {'type': 'VARIABLE', 'value': 'x'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'pass'},
            ],
            'raw': 'if x: pass'
        }
        
        score = self.algorithm.compare(parsed_loop, parsed_conditional)
        # Different structures should have lower similarity
        assert score < 0.7
    
    def test_similar_algorithms(self):
        """Test comparison of similar algorithms"""
        # Bubble sort
        parsed_bubble = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'for'},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'KEYWORD', 'value': 'in'},
                {'type': 'VARIABLE', 'value': 'range'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'n'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'for'},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'KEYWORD', 'value': 'in'},
                {'type': 'VARIABLE', 'value': 'range'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'n'},
                {'type': 'OPERATOR', 'value': '-'},
                {'type': 'LITERAL', 'value': '1'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'if'},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': '>'},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': '+'},
                {'type': 'LITERAL', 'value': '1'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': '+'},
                {'type': 'LITERAL', 'value': '1'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': '='},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': '+'},
                {'type': 'LITERAL', 'value': '1'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': ']'},
            ],
            'raw': 'for i in range(n): for j in range(n-1): if arr[j] > arr[j+1]: arr[j], arr[j+1] = arr[j+1], arr[j]'
        }
        
        # Selection sort (similar structure)
        parsed_selection = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'for'},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'KEYWORD', 'value': 'in'},
                {'type': 'VARIABLE', 'value': 'range'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'n'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'VARIABLE', 'value': 'min_idx'},
                {'type': 'OPERATOR', 'value': '='},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'KEYWORD', 'value': 'for'},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'KEYWORD', 'value': 'in'},
                {'type': 'VARIABLE', 'value': 'range'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'OPERATOR', 'value': '+'},
                {'type': 'LITERAL', 'value': '1'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'n'},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'KEYWORD', 'value': 'if'},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': '<'},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'min_idx'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': ':'},
                {'type': 'VARIABLE', 'value': 'min_idx'},
                {'type': 'OPERATOR', 'value': '='},
                {'type': 'VARIABLE', 'value': 'j'},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'min_idx'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': '='},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'min_idx'},
                {'type': 'OPERATOR', 'value': ']'},
                {'type': 'OPERATOR', 'value': ','},
                {'type': 'VARIABLE', 'value': 'arr'},
                {'type': 'OPERATOR', 'value': '['},
                {'type': 'VARIABLE', 'value': 'i'},
                {'type': 'OPERATOR', 'value': ']'},
            ],
            'raw': 'for i in range(n): min_idx = i for j in range(i+1, n): if arr[j] < arr[min_idx]: min_idx = j arr[i], arr[min_idx] = arr[min_idx], arr[i]'
        }
        
        score = self.algorithm.compare(parsed_bubble, parsed_selection)
        # Similar sorting algorithms should have moderate similarity
        assert 0.3 < score < 0.8


class TestWinnowingEdgeCases:
    """Test edge cases for Winnowing algorithm"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.algorithm = EnhancedWinnowingSimilarity()
    
    def test_very_short_code(self):
        """Test comparison of very short code"""
        parsed_a = {
            'tokens': [{'type': 'KEYWORD', 'value': 'pass'}],
            'raw': 'pass'
        }
        parsed_b = {
            'tokens': [{'type': 'KEYWORD', 'value': 'pass'}],
            'raw': 'pass'
        }
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        assert score == 1.0
    
    def test_single_token_difference(self):
        """Test detection of single token difference"""
        parsed_a = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'LITERAL', 'value': '1'},
            ],
            'raw': 'return 1'
        }
        parsed_b = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'return'},
                {'type': 'LITERAL', 'value': '2'},
            ],
            'raw': 'return 2'
        }
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        # Should detect difference
        assert score < 1.0
    
    def test_whitespace_insensitivity(self):
        """Test that whitespace doesn't affect similarity"""
        parsed_a = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'def'},
                {'type': 'FUNCTION', 'value': 'test'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'WHITESPACE', 'value': ' '},
                {'type': 'OPERATOR', 'value': ':'},
            ],
            'raw': 'def test():'
        }
        parsed_b = {
            'tokens': [
                {'type': 'KEYWORD', 'value': 'def'},
                {'type': 'FUNCTION', 'value': 'test'},
                {'type': 'OPERATOR', 'value': '('},
                {'type': 'OPERATOR', 'value': ')'},
                {'type': 'WHITESPACE', 'value': '\n'},
                {'type': 'OPERATOR', 'value': ':'},
            ],
            'raw': 'def test():'
        }
        
        score = self.algorithm.compare(parsed_a, parsed_b)
        # Whitespace differences should not affect score
        assert score == 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])