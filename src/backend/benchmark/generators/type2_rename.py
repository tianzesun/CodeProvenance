"""Type-2 (Renamed Clone) generator.

Generates clones with renamed identifiers (variables, functions, classes).
Same structure but different names.
"""
from __future__ import annotations

import random
from typing import Optional

from src.backend.benchmark.generators.base_loader import CodePool
from src.backend.benchmark.generators.utils.rename_utils import rename_identifiers
from src.backend.benchmark.generators.utils.ast_utils import is_valid_python


class Type2Generator:
    """Generator for Type-2 (renamed) clones.
    
    Type-2 clones have the same structure but with renamed
    identifiers (variables, functions, classes).
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def generate(self, code: str) -> str:
        """Generate a Type-2 clone from source code.
        
        Args:
            code: Source code to clone.
            
        Returns:
            Type-2 clone with renamed identifiers.
        """
        # Rename identifiers
        renamed = rename_identifiers(code, seed=self.seed)
        
        # Verify the renamed code is valid Python
        if not is_valid_python(renamed):
            # If invalid, try with different seed
            for offset in range(1, 10):
                try:
                    renamed = rename_identifiers(code, seed=self.seed + offset)
                    if is_valid_python(renamed):
                        break
                except Exception:
                    continue
        
        return renamed
    
    def generate_with_variations(self, code: str, n_variations: int = 3) -> list:
        """Generate multiple Type-2 variations.
        
        Args:
            code: Source code to clone.
            n_variations: Number of variations to generate.
            
        Returns:
            List of Type-2 clones.
        """
        variations = []
        
        for i in range(n_variations):
            # Use different seed for each variation
            variation_seed = self.seed + i * 1000
            variation = rename_identifiers(code, seed=variation_seed)
            
            if is_valid_python(variation):
                variations.append(variation)
        
        return variations


def generate_type2_clone(code: str, seed: int = 42) -> str:
    """Generate a Type-2 clone from source code.
    
    Args:
        code: Source code to clone.
        seed: Random seed for reproducibility.
        
    Returns:
        Type-2 clone with renamed identifiers.
    """
    generator = Type2Generator(seed=seed)
    return generator.generate(code)


def generate_type2_variations(code: str, n_variations: int = 3, seed: int = 42) -> list:
    """Generate multiple Type-2 variations.
    
    Args:
        code: Source code to clone.
        n_variations: Number of variations to generate.
        seed: Random seed for reproducibility.
        
    Returns:
        List of Type-2 clones.
    """
    generator = Type2Generator(seed=seed)
    return generator.generate_with_variations(code, n_variations)