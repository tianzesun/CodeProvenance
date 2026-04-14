"""Negative sample generator.

Generates non-clone pairs for benchmarking, including
easy negatives (unrelated code) and hard negatives (near-miss).
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

from src.backend.benchmark.generators.base_loader import CodePool
from src.backend.benchmark.generators.utils.ast_utils import count_lines, count_tokens


class NegativeGenerator:
    """Generator for negative (non-clone) samples.
    
    Generates two types of negatives:
    - Easy: Completely unrelated code
    - Hard: Near-miss with partial similarity
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def generate_easy(self, pool: CodePool) -> Tuple[str, str]:
        """Generate easy negative pair (unrelated code).
        
        Args:
            pool: Code pool to sample from.
            
        Returns:
            Tuple of (code_a, code_b) - unrelated code.
        """
        return pool.sample_pair()
    
    def generate_hard(self, code: str, pool: CodePool) -> Tuple[str, str]:
        """Generate hard negative pair (near-miss).
        
        Creates pairs that look similar but are not clones
        by injecting small snippets of code.
        
        Args:
            code: Base code to create near-miss from.
            pool: Code pool to sample from.
            
        Returns:
            Tuple of (code_a, code_b) - near-miss pair.
        """
        other = pool.sample()
        
        # Inject small similarity (first few lines of code_a into code_b)
        lines_a = code.strip().split('\n')
        snippet = '\n'.join(lines_a[:min(3, len(lines_a))])
        
        # Combine with other code
        combined = other + '\n\n# Injected snippet\n' + snippet
        
        return code, combined
    
    def generate_hard_by_sharing(self, pool: CodePool) -> Tuple[str, str]:
        """Generate hard negative by sharing common patterns.
        
        Args:
            pool: Code pool to sample from.
            
        Returns:
            Tuple of (code_a, code_b) - hard negative pair.
        """
        code_a, code_b = pool.sample_pair()
        
        # Make them look similar by using same variable names
        # but different logic
        common_vars = ['data', 'result', 'value', 'item', 'temp']
        
        # Add common variable usage to both
        var_a = self.rng.choice(common_vars)
        var_b = self.rng.choice(common_vars)
        
        code_a_modified = code_a + f'\n{var_a} = None'
        code_b_modified = code_b + f'\n{var_b} = None'
        
        return code_a_modified, code_b_modified
    
    def generate_with_constraints(
        self,
        pool: CodePool,
        min_tokens: int = 20,
        max_tokens: int = 300,
        min_lines: int = 5,
        max_lines: int = 50,
        difficulty: str = "easy",
    ) -> Tuple[str, str]:
        """Generate negative pair with constraints.
        
        Args:
            pool: Code pool to sample from.
            min_tokens: Minimum token count.
            max_tokens: Maximum token count.
            min_lines: Minimum line count.
            max_lines: Maximum line count.
            difficulty: Difficulty level ("easy" or "hard").
            
        Returns:
            Tuple of (code_a, code_b) meeting constraints.
        """
        max_attempts = 100
        
        for _ in range(max_attempts):
            if difficulty == "easy":
                code_a, code_b = self.generate_easy(pool)
            else:
                # Get a base code and generate hard negative
                base = pool.sample()
                code_a, code_b = self.generate_hard(base, pool)
            
            # Check constraints
            tokens_a = count_tokens(code_a)
            tokens_b = count_tokens(code_b)
            lines_a = count_lines(code_a)
            lines_b = count_lines(code_b)
            
            if (min_tokens <= tokens_a <= max_tokens and
                min_tokens <= tokens_b <= max_tokens and
                min_lines <= lines_a <= max_lines and
                min_lines <= lines_b <= max_lines):
                return code_a, code_b
        
        # Fallback: return any pair
        return pool.sample_pair()


def generate_easy_negative(pool: CodePool, seed: int = 42) -> Tuple[str, str]:
    """Generate easy negative pair (unrelated code).
    
    Args:
        pool: Code pool to sample from.
        seed: Random seed for reproducibility.
        
    Returns:
        Tuple of (code_a, code_b) - unrelated code.
    """
    generator = NegativeGenerator(seed=seed)
    return generator.generate_easy(pool)


def generate_hard_negative(code: str, pool: CodePool, seed: int = 42) -> Tuple[str, str]:
    """Generate hard negative pair (near-miss).
    
    Args:
        code: Base code to create near-miss from.
        pool: Code pool to sample from.
        seed: Random seed for reproducibility.
        
    Returns:
        Tuple of (code_a, code_b) - near-miss pair.
    """
    generator = NegativeGenerator(seed=seed)
    return generator.generate_hard(code, pool)


def generate_negative_pair(
    pool: CodePool,
    difficulty: str = "easy",
    seed: int = 42,
) -> Tuple[str, str]:
    """Generate a negative pair.
    
    Args:
        pool: Code pool to sample from.
        difficulty: Difficulty level ("easy" or "hard").
        seed: Random seed for reproducibility.
        
    Returns:
        Tuple of (code_a, code_b) - non-clone pair.
    """
    generator = NegativeGenerator(seed=seed)
    
    if difficulty == "easy":
        return generator.generate_easy(pool)
    else:
        base = pool.sample()
        return generator.generate_hard(base, pool)