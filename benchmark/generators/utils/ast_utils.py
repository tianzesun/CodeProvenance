"""AST utilities for code transformation.

Provides helper functions for parsing, manipulating, and
unparsing Python AST nodes.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def parse_code(code: str) -> ast.AST:
    """Parse Python code into AST.
    
    Args:
        code: Python source code string.
        
    Returns:
        AST tree.
        
    Raises:
        SyntaxError: If code is invalid Python.
    """
    return ast.parse(code)


def unparse_code(tree: ast.AST) -> str:
    """Convert AST back to Python code.
    
    Args:
        tree: AST tree to unparse.
        
    Returns:
        Python source code string.
    """
    return ast.unparse(tree)


def get_functions(tree: ast.AST) -> List[ast.FunctionDef]:
    """Extract all function definitions from AST.
    
    Args:
        tree: AST tree to analyze.
        
    Returns:
        List of function definition nodes.
    """
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node)
    return functions


def get_variables(tree: ast.AST) -> Set[str]:
    """Extract all variable names from AST.
    
    Args:
        tree: AST tree to analyze.
        
    Returns:
        Set of variable names.
    """
    variables = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            variables.add(node.id)
    return variables


def get_identifiers(tree: ast.AST) -> Set[str]:
    """Extract all identifiers (variables, functions, classes) from AST.
    
    Args:
        tree: AST tree to analyze.
        
    Returns:
        Set of identifier names.
    """
    identifiers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.FunctionDef):
            identifiers.add(node.name)
        elif isinstance(node, ast.ClassDef):
            identifiers.add(node.name)
    return identifiers


def count_lines(code: str) -> int:
    """Count number of lines in code.
    
    Args:
        code: Python source code.
        
    Returns:
        Number of lines.
    """
    return len(code.strip().split('\n'))


def count_tokens(code: str) -> int:
    """Count approximate number of tokens in code.
    
    Args:
        code: Python source code.
        
    Returns:
        Approximate token count.
    """
    # Simple tokenization by splitting on whitespace and operators
    tokens = re.findall(r'\b\w+\b|[^\w\s]', code)
    return len(tokens)


def is_valid_python(code: str) -> bool:
    """Check if code is valid Python.
    
    Args:
        code: Python source code.
        
    Returns:
        True if valid, False otherwise.
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def normalize_whitespace(code: str) -> str:
    """Normalize whitespace in code while preserving structure.
    
    Args:
        code: Python source code.
        
    Returns:
        Code with normalized whitespace.
    """
    # Parse and unparse to normalize
    try:
        tree = ast.parse(code)
        return ast.unparse(tree)
    except SyntaxError:
        return code