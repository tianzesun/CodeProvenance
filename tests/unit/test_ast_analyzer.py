"""Unit tests for AST-based structural analysis."""

import pytest
from src.backend.engines.ai_detection.ast_analyzer import (
    ASTAnalyzer,
    analyze_ast,
    compute_ast_score,
)


class TestASTAnalyzer:
    """Test AST structural feature extraction."""

    def test_basic_feature_extraction(self):
        """Test that basic features are extracted from valid code."""
        code = """
def hello():
    return "world"

def goodbye():
    return "moon"
"""
        features = analyze_ast(code)
        assert features.function_count == 2
        assert features.class_count == 0
        assert features.avg_function_length > 0

    def test_uniform_function_lengths(self):
        """AI code tends to have uniform function lengths."""
        # GPT-4 style: all functions similar length
        uniform_code = """
def func1(x):
    '''Doc'''
    result = x * 2
    return result

def func2(y):
    '''Doc'''
    result = y + 1
    return result

def func3(z):
    '''Doc'''
    result = z - 1
    return result
"""
        features = analyze_ast(uniform_code)
        assert features.function_length_cv < 0.3  # Low CV = uniform

        # Human code: varied function lengths
        varied_code = """
def short():
    return 1

def medium(x, y):
    if x > 0:
        return x + y
    return y

def long_function(a, b, c, d):
    result = 0
    for i in range(10):
        if i % 2 == 0:
            result += a
        else:
            result += b
        if i > 5:
            result += c
        else:
            result += d
    return result
"""
        features2 = analyze_ast(varied_code)
        assert features2.function_length_cv > 0.3  # High CV = varied

    def test_import_clustering(self):
        """Test detection of perfect import organization."""
        # Perfect clustering (AI-typical)
        perfect_code = """
import os
import sys
from pathlib import Path

def main():
    pass
"""
        features = analyze_ast(perfect_code)
        assert features.import_clustering_score > 0.9

        # Scattered imports (human-typical)
        scattered_code = """
import os

def helper():
    pass

import sys

def main():
    pass

from pathlib import Path
"""
        features2 = analyze_ast(scattered_code)
        assert features2.import_clustering_score < 0.9

    def test_defensive_patterns(self):
        """Test detection of excessive defensive programming."""
        # Claude-style: try/except everywhere
        defensive_code = """
def process(data):
    try:
        if data is None:
            return None
        result = []
        try:
            for item in data:
                if item is not None:
                    result.append(item)
        except TypeError:
            pass
        return result
    except Exception:
        return []
"""
        features = analyze_ast(defensive_code)
        assert features.defensive_pattern_count >= 2

    def test_docstring_coverage(self):
        """Test docstring coverage calculation."""
        # All functions documented (AI-typical)
        full_docs = """
def func1():
    '''Doc1'''
    pass

def func2():
    '''Doc2'''
    pass

class MyClass:
    '''ClassDoc'''
    pass
"""
        features = analyze_ast(full_docs)
        assert features.docstring_coverage == 1.0

        # No documentation (common in student code)
        no_docs = """
def func1():
    pass

def func2():
    pass
"""
        features2 = analyze_ast(no_docs)
        assert features2.docstring_coverage == 0.0

    def test_type_hint_coverage(self):
        """Test type hint coverage calculation."""
        # Fully typed (Claude-typical)
        typed_code = """
def add(x: int, y: int) -> int:
    return x + y

def multiply(a: float, b: float) -> float:
    return a * b
"""
        features = analyze_ast(typed_code)
        assert features.type_hint_coverage == 1.0

        # No types (common in Python)
        untyped_code = """
def add(x, y):
    return x + y
"""
        features2 = analyze_ast(untyped_code)
        assert features2.type_hint_coverage == 0.0

    def test_dead_code_detection(self):
        """Test detection of unreachable code."""
        code_with_dead = """
def func():
    return 1
    print("unreachable")
    x = 2  # also unreachable
"""
        features = analyze_ast(code_with_dead)
        assert features.dead_code_count >= 1

    def test_nesting_depth(self):
        """Test nesting depth calculation."""
        deeply_nested = """
def func():
    if True:
        for i in range(10):
            while i > 0:
                if i % 2:
                    pass
"""
        features = analyze_ast(deeply_nested)
        assert features.max_nesting_depth >= 4

    def test_ai_score_computation(self):
        """Test that AI score is computed from features."""
        # GPT-4 style code
        ai_like_code = """
import os
import sys

def process_data(data: list) -> list:
    '''Process the data and return results.'''
    result = []
    try:
        for item in data:
            if item is not None:
                result.append(item)
    except TypeError:
        return []
    return result

def validate_data(data: list) -> bool:
    '''Validate the input data.'''
    if data is None:
        return False
    try:
        return len(data) > 0
    except TypeError:
        return False

def transform_data(data: list) -> list:
    '''Transform the data.'''
    result = []
    try:
        for item in data:
            result.append(item.upper())
    except AttributeError:
        return []
    return result
"""
        result = compute_ast_score(ai_like_code)
        assert result["ai_score"] > 0.5  # Should score as AI-like
        assert "features" in result

    def test_empty_code_handling(self):
        """Test graceful handling of empty code."""
        features = analyze_ast("")
        assert features.function_count == 0
        assert features.class_count == 0

    def test_syntax_error_handling(self):
        """Test graceful handling of syntax errors."""
        invalid_code = "def broken( invalid syntax"
        features = analyze_ast(invalid_code)
        # Should return default features
        assert features.function_count == 0

    def test_complexity_uniformity(self):
        """Test cyclomatic complexity uniformity."""
        # All functions same complexity (AI-typical)
        uniform_complexity = """
def func1(x):
    if x > 0:
        return x
    return 0

def func2(y):
    if y > 0:
        return y
    return 0

def func3(z):
    if z > 0:
        return z
    return 0
"""
        features = analyze_ast(uniform_complexity)
        assert features.complexity_uniformity > 0.7

    def test_singleton_pattern(self):
        """Test that analyzer uses singleton pattern."""
        from src.backend.engines.ai_detection import get_ast_analyzer

        analyzer1 = get_ast_analyzer()
        analyzer2 = get_ast_analyzer()
        assert analyzer1 is analyzer2

    def test_feature_serialization(self):
        """Test that features can be serialized to dict."""
        code = "def test(): pass"
        features = analyze_ast(code)
        feature_dict = features.to_dict()

        assert isinstance(feature_dict, dict)
        assert "function_count" in feature_dict
        assert "class_count" in feature_dict
        assert isinstance(feature_dict["function_count"], int)

    def test_non_python_language(self):
        """Test that non-Python languages return default features."""
        features = analyze_ast("int main() { return 0; }", language="c")
        assert features.function_count == 0
        assert features.class_count == 0
