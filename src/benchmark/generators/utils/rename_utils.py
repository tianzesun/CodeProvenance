"""Identifier renaming utilities for code transformation.

Provides functions for renaming variables, functions, and
other identifiers in Python code while preserving semantics.
"""
from __future__ import annotations

import ast
import random
import string
from typing import Dict, List, Optional, Set, Tuple

from src.benchmark.generators.utils.ast_utils import get_identifiers, parse_code, unparse_code


class IdentifierRenamer(ast.NodeTransformer):
    """AST transformer that renames identifiers consistently.
    
    Maintains a mapping of original names to new names to ensure
    consistent renaming throughout the code.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the renamer.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
        self.name_map: Dict[str, str] = {}
        self.counter = 0
        
        # Python keywords that should not be renamed
        self.keywords = {
            'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
            'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
            'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
            'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'try', 'while', 'with', 'yield'
        }
        
        # Built-in functions that should not be renamed
        self.builtins = {
            'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
            'set', 'tuple', 'bool', 'type', 'isinstance', 'issubclass',
            'hasattr', 'getattr', 'setattr', 'delattr', 'property',
            'classmethod', 'staticmethod', 'super', 'object', 'enumerate',
            'zip', 'map', 'filter', 'sorted', 'reversed', 'min', 'max',
            'sum', 'abs', 'round', 'pow', 'divmod', 'input', 'open',
            'file', 'read', 'write', 'close', 'append', 'extend', 'pop',
            'remove', 'sort', 'reverse', 'copy', 'clear', 'keys', 'values',
            'items', 'get', 'update', 'add', 'discard', 'union', 'intersection',
            'difference', 'symmetric_difference', 'issubset', 'issuperset',
        }
    
    def _generate_name(self, original: str) -> str:
        """Generate a new identifier name.
        
        Args:
            original: Original identifier name.
            
        Returns:
            New identifier name.
        """
        # Use different prefixes based on identifier type
        if original[0].isupper():
            # Likely a class name
            prefix = 'Class'
        elif original.startswith('_'):
            # Private/protected
            prefix = '_var'
        else:
            # Regular variable/function
            prefix = 'var'
        
        # Generate random suffix
        suffix = ''.join(self.rng.choices(string.ascii_lowercase, k=4))
        return f"{prefix}_{self.counter}_{suffix}"
    
    def _should_rename(self, name: str) -> bool:
        """Check if an identifier should be renamed.
        
        Args:
            name: Identifier name.
            
        Returns:
            True if should be renamed, False otherwise.
        """
        # Don't rename keywords
        if name in self.keywords:
            return False
        
        # Don't rename built-ins
        if name in self.builtins:
            return False
        
        # Don't rename special methods
        if name.startswith('__') and name.endswith('__'):
            return False
        
        return True
    
    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Rename Name nodes.
        
        Args:
            node: Name node to process.
            
        Returns:
            Potentially renamed Name node.
        """
        if self._should_rename(node.id):
            if node.id not in self.name_map:
                self.name_map[node.id] = self._generate_name(node.id)
                self.counter += 1
            node.id = self.name_map[node.id]
        return node
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Rename function definitions.
        
        Args:
            node: FunctionDef node to process.
            
        Returns:
            Potentially renamed FunctionDef node.
        """
        if self._should_rename(node.name):
            if node.name not in self.name_map:
                self.name_map[node.name] = self._generate_name(node.name)
                self.counter += 1
            node.name = self.name_map[node.name]
        
        # Continue visiting child nodes
        self.generic_visit(node)
        return node
    
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Rename class definitions.
        
        Args:
            node: ClassDef node to process.
            
        Returns:
            Potentially renamed ClassDef node.
        """
        if self._should_rename(node.name):
            if node.name not in self.name_map:
                self.name_map[node.name] = self._generate_name(node.name)
                self.counter += 1
            node.name = self.name_map[node.name]
        
        # Continue visiting child nodes
        self.generic_visit(node)
        return node


def rename_identifiers(code: str, seed: int = 42) -> str:
    """Rename all identifiers in code.
    
    Args:
        code: Python source code.
        seed: Random seed for reproducibility.
        
    Returns:
        Code with renamed identifiers.
    """
    try:
        tree = parse_code(code)
        renamer = IdentifierRenamer(seed=seed)
        new_tree = renamer.visit(tree)
        return unparse_code(new_tree)
    except SyntaxError:
        # If parsing fails, return original code
        return code


def get_rename_map(code: str, seed: int = 42) -> Dict[str, str]:
    """Get the mapping of original names to renamed names.
    
    Args:
        code: Python source code.
        seed: Random seed for reproducibility.
        
    Returns:
        Dictionary mapping original names to new names.
    """
    try:
        tree = parse_code(code)
        renamer = IdentifierRenamer(seed=seed)
        renamer.visit(tree)
        return renamer.name_map
    except SyntaxError:
        return {}