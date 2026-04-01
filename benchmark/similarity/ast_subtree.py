"""AST-based subtree similarity detection.

Compares code using Abstract Syntax Tree structural analysis.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict


def extract_subtrees(ast_root: Any, max_depth: int = 3) -> List[str]:
    """Extract all subtrees up to max_depth from AST.
    
    Args:
        ast_root: Root node of the AST.
        max_depth: Maximum depth to traverse.
        
    Returns:
        List of subtree string representations.
    """
    subtrees = []
    
    def traverse(node: Any, depth: int) -> str:
        if depth > max_depth or node is None:
            return ""
        
        node_str = _node_to_string(node)
        subtrees.append(node_str)
        
        children = _get_children(node)
        for child in children:
            traverse(child, depth + 1)
        
        return node_str
    
    traverse(ast_root, 0)
    return subtrees


def _node_to_string(node: Any) -> str:
    """Convert AST node to string representation.
    
    Args:
        node: AST node.
        
    Returns:
        String representation of the node.
    """
    if hasattr(node, 'node_name'):
        return node.node_name()
    if hasattr(node, 'type'):
        return node.type
    return str(type(node).__name__)


def _get_children(node: Any) -> List[Any]:
    """Get children of an AST node.
    
    Args:
        node: AST node.
        
    Returns:
        List of child nodes.
    """
    if hasattr(node, 'children'):
        return node.children
    if hasattr(node, 'child_count'):
        return [node.getChild(i) for i in range(node.child_count())]
    return []


def compute_subtree_frequencies(subtrees: List[str]) -> Dict[str, int]:
    """Compute frequency of each subtree type.
    
    Args:
        subtrees: List of subtree strings.
        
    Returns:
        Dictionary of subtree -> frequency.
    """
    freq = defaultdict(int)
    for s in subtrees:
        freq[s] += 1
    return dict(freq)


def ast_similarity(subtrees1: List[str], subtrees2: List[str]) -> float:
    """Calculate AST-based structural similarity.
    
    Uses frequency-weighted Jaccard similarity.
    
    Args:
        subtrees1: Subtrees from first code sample.
        subtrees2: Subtrees from second code sample.
        
    Returns:
        Similarity score between 0.0 and 1.0.
    """
    freq1 = compute_subtree_frequencies(subtrees1)
    freq2 = compute_subtree_frequencies(subtrees2)
    
    all_types = set(freq1.keys()) | set(freq2.keys())
    
    if not all_types:
        return 0.0
    
    intersection = sum(min(freq1.get(t, 0), freq2.get(t, 0)) for t in all_types)
    union = sum(max(freq1.get(t, 0), freq2.get(t, 0)) for t in all_types)
    
    return intersection / union if union > 0 else 0.0


def compare_ast(ast1: Any, ast2: Any, max_depth: int = 3) -> float:
    """Compare two AST roots for similarity.
    
    Args:
        ast1: First AST root.
        ast2: Second AST root.
        max_depth: Maximum subtree depth.
        
    Returns:
        Similarity score between 0.0 and 1.0.
    """
    subtrees1 = extract_subtrees(ast1, max_depth)
    subtrees2 = extract_subtrees(ast2, max_depth)
    return ast_similarity(subtrees1, subtrees2)


def compare_ast_safe(code_a: str, code_b: str, max_depth: int = 3) -> float:
    """Compare two code strings using AST-like analysis (safe fallback).
    
    When no real AST parser is available, this extracts structural
    features from raw code to approximate AST similarity.
    
    Args:
        code_a: First code string.
        code_b: Second code string.
        max_depth: Maximum depth (unused, kept for API compatibility).
        
    Returns:
        Similarity score between 0.0 and 1.0.
    """
    features_a = _extract_structural_features(code_a)
    features_b = _extract_structural_features(code_b)
    return _feature_similarity(features_a, features_b)


def _extract_structural_features(code: str) -> Dict[str, int]:
    """Extract structural features from code as a frequency map.
    
    Args:
        code: Source code string.
        
    Returns:
        Dictionary mapping feature names to counts.
    """
    features: Dict[str, int] = defaultdict(int)
    
    # Count control flow structures
    control_patterns = {
        "if": r'\bif\b',
        "elif": r'\belif\b',
        "else": r'\belse\b',
        "for": r'\bfor\b',
        "while": r'\bwhile\b',
        "return": r'\breturn\b',
        "try": r'\btry\b',
        "except": r'\bexcept\b',
        "catch": r'\bcatch\b',
        "switch": r'\bswitch\b',
        "case": r'\bcase\b',
        "class": r'\bclass\b',
        "def": r'\bdef\b',
        "function": r'\bfunction\b',
    }
    
    for name, pattern in control_patterns.items():
        count = len(re.findall(pattern, code))
        if count > 0:
            features[name] = count
    
    # Count brackets (structural nesting)
    features["parens"] = code.count('(') + code.count(')')
    features["braces"] = code.count('{') + code.count('}')
    features["brackets"] = code.count('[') + code.count(']')
    
    # Count operators
    features["assignment"] = len(re.findall(r'=', code)) - len(re.findall(r'==', code))
    features["comparison"] = len(re.findall(r'==|!=|<=|>=|<|>', code))
    
    # Line-based features
    lines = [l.strip() for l in code.split('\n') if l.strip()]
    features["total_lines"] = len(lines)
    features["non_comment_lines"] = len([
        l for l in lines if not l.startswith('//') and not l.startswith('#')
    ])
    
    return dict(features)


def _feature_similarity(
    features_a: Dict[str, int],
    features_b: Dict[str, int]
) -> float:
    """Compute similarity between two feature dictionaries.
    
    Uses frequency-weighted Jaccard similarity.
    
    Args:
        features_a: First feature dictionary.
        features_b: Second feature dictionary.
        
    Returns:
        Similarity score between 0.0 and 1.0.
    """
    all_keys = set(features_a.keys()) | set(features_b.keys())
    if not all_keys:
        return 0.0
    
    intersection = sum(
        min(features_a.get(k, 0), features_b.get(k, 0))
        for k in all_keys
    )
    union = sum(
        max(features_a.get(k, 0), features_b.get(k, 0))
        for k in all_keys
    )
    
    return intersection / union if union > 0 else 0.0
