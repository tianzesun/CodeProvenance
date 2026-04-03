"""Code transformation utilities for generating clones.

Provides functions for structural transformations like
reordering statements, adding dead code, and converting loops.
"""
from __future__ import annotations

import ast
import random
from typing import List, Optional

from benchmark.generators.utils.ast_utils import parse_code, unparse_code


class StatementReorderer(ast.NodeTransformer):
    """AST transformer that reorders independent statements.
    
    Only reorders statements that are independent (no dependencies
    between them).
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the reorderer.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Reorder statements in module body.
        
        Args:
            node: Module node to process.
            
        Returns:
            Module with potentially reordered statements.
        """
        # Group statements into independent blocks
        blocks = self._find_independent_blocks(node.body)
        
        # Shuffle each block independently
        shuffled_blocks = []
        for block in blocks:
            if len(block) > 1:
                # Only shuffle if block has multiple statements
                shuffled = block.copy()
                self.rng.shuffle(shuffled)
                shuffled_blocks.extend(shuffled)
            else:
                shuffled_blocks.extend(block)
        
        node.body = shuffled_blocks
        return node
    
    def _find_independent_blocks(self, statements: List[ast.stmt]) -> List[List[ast.stmt]]:
        """Find blocks of independent statements.
        
        Args:
            statements: List of statements to analyze.
            
        Returns:
            List of statement blocks (each block is independent).
        """
        blocks = []
        current_block = []
        
        for stmt in statements:
            # Check if statement is independent
            if self._is_independent(stmt, current_block):
                current_block.append(stmt)
            else:
                # Start new block
                if current_block:
                    blocks.append(current_block)
                current_block = [stmt]
        
        # Add final block
        if current_block:
            blocks.append(current_block)
        
        return blocks
    
    def _is_independent(self, stmt: ast.stmt, block: List[ast.stmt]) -> bool:
        """Check if statement is independent from block.
        
        Args:
            stmt: Statement to check.
            block: Current block of statements.
            
        Returns:
            True if independent, False otherwise.
        """
        # Simple heuristic: assignments and expressions are independent
        # unless they reference variables defined in the block
        if isinstance(stmt, (ast.Assign, ast.Expr)):
            return True
        
        # Function/class definitions are independent
        if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
            return True
        
        # Control flow statements are not independent
        if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
            return False
        
        return True


class DeadCodeInserter(ast.NodeTransformer):
    """AST transformer that inserts dead code.
    
    Adds unreachable or useless statements to make code
    look different while preserving functionality.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the inserter.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
        self.dead_code_snippets = [
            "pass",
            "_ = None",
            "x = 0",
            "y = ''",
            "z = []",
            "a = {}",
            "b = ()",
            "c = set()",
        ]
    
    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Insert dead code into module.
        
        Args:
            node: Module node to process.
            
        Returns:
            Module with dead code inserted.
        """
        # Insert dead code at random positions
        new_body = []
        for stmt in node.body:
            new_body.append(stmt)
            
            # Randomly insert dead code after some statements
            if self.rng.random() < 0.3:  # 30% chance
                dead_code = self._create_dead_code()
                new_body.append(dead_code)
        
        node.body = new_body
        return node
    
    def _create_dead_code(self) -> ast.stmt:
        """Create a dead code statement.
        
        Returns:
            AST statement representing dead code.
        """
        snippet = self.rng.choice(self.dead_code_snippets)
        try:
            tree = ast.parse(snippet)
            return tree.body[0]
        except SyntaxError:
            # Fallback to pass
            return ast.Pass()


class LoopConverter(ast.NodeTransformer):
    """AST transformer that converts between loop types.
    
    Converts for loops to while loops and vice versa.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the converter.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def visit_For(self, node: ast.For) -> ast.stmt:
        """Convert for loop to while loop.
        
        Args:
            node: For loop node.
            
        Returns:
            While loop or original for loop.
        """
        # Only convert simple for loops (for i in range(n))
        if (isinstance(node.iter, ast.Call) and
            isinstance(node.iter.func, ast.Name) and
            node.iter.func.id == 'range' and
            len(node.iter.args) == 1):
            
            # Convert to while loop
            return self._for_to_while(node)
        
        return node
    
    def _for_to_while(self, for_node: ast.For) -> List[ast.stmt]:
        """Convert for loop to while loop.
        
        Args:
            for_node: For loop to convert.
            
        Returns:
            List of statements (init + while loop).
        """
        # Get loop variable and range
        loop_var = for_node.target
        range_arg = for_node.iter.args[0]
        
        # Get line number from original node
        lineno = getattr(for_node, 'lineno', 1)
        col_offset = getattr(for_node, 'col_offset', 0)
        
        # Create: i = 0; while i < n: ...; i += 1
        init = ast.Assign(
            targets=[loop_var],
            value=ast.Constant(value=0),
            lineno=lineno,
            col_offset=col_offset
        )
        
        condition = ast.Compare(
            left=loop_var,
            ops=[ast.Lt()],
            comparators=[range_arg],
            lineno=lineno,
            col_offset=col_offset
        )
        
        increment = ast.AugAssign(
            target=loop_var,
            op=ast.Add(),
            value=ast.Constant(value=1),
            lineno=lineno,
            col_offset=col_offset
        )
        
        # Create while loop
        while_node = ast.While(
            test=condition,
            body=for_node.body + [increment],
            orelse=for_node.orelse,
            lineno=lineno,
            col_offset=col_offset
        )
        
        return [init, while_node]


def reorder_statements(code: str, seed: int = 42) -> str:
    """Reorder independent statements in code.
    
    Args:
        code: Python source code.
        seed: Random seed for reproducibility.
        
    Returns:
        Code with reordered statements.
    """
    try:
        tree = parse_code(code)
        reorderer = StatementReorderer(seed=seed)
        new_tree = reorderer.visit(tree)
        return unparse_code(new_tree)
    except SyntaxError:
        return code


def add_dead_code(code: str, seed: int = 42) -> str:
    """Add dead code to code.
    
    Args:
        code: Python source code.
        seed: Random seed for reproducibility.
        
    Returns:
        Code with dead code added.
    """
    try:
        tree = parse_code(code)
        inserter = DeadCodeInserter(seed=seed)
        new_tree = inserter.visit(tree)
        return unparse_code(new_tree)
    except SyntaxError:
        return code


def convert_loops(code: str, seed: int = 42) -> str:
    """Convert between loop types.
    
    Args:
        code: Python source code.
        seed: Random seed for reproducibility.
        
    Returns:
        Code with converted loops.
    """
    try:
        tree = parse_code(code)
        converter = LoopConverter(seed=seed)
        new_tree = converter.visit(tree)
        return unparse_code(new_tree)
    except SyntaxError:
        return code


def structural_transform(code: str, seed: int = 42) -> str:
    """Apply multiple structural transformations.
    
    Args:
        code: Python source code.
        seed: Random seed for reproducibility.
        
    Returns:
        Code with structural transformations applied.
    """
    try:
        tree = parse_code(code)
        
        # Apply transformations in random order
        rng = random.Random(seed)
        transformers = [
            StatementReorderer(seed=seed),
            DeadCodeInserter(seed=seed),
            LoopConverter(seed=seed),
        ]
        rng.shuffle(transformers)
        
        for transformer in transformers:
            tree = transformer.visit(tree)
        
        return unparse_code(tree)
    except SyntaxError:
        return code