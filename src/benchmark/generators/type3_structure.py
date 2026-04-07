"""Type-3 (Structural Clone) generator.

Generates clones with structural changes like reordering
statements, adding dead code, or converting loop types.
"""
from __future__ import annotations

import random
from typing import List, Optional

from src.benchmark.generators.base_loader import CodePool
from src.benchmark.generators.utils.transform_utils import (
    reorder_statements,
    add_dead_code,
    convert_loops,
    structural_transform,
)
from src.benchmark.generators.utils.ast_utils import is_valid_python


class Type3Generator:
    """Generator for Type-3 (structural) clones.
    
    Type-3 clones have the same logic but with structural
    changes like reordering, dead code, or loop conversion.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def generate(self, code: str) -> str:
        """Generate a Type-3 clone from source code.
        
        Args:
            code: Source code to clone.
            
        Returns:
            Type-3 clone with structural changes.
        """
        # Apply structural transformations
        transformations = [
            self._reorder_only,
            self._add_dead_code_only,
            self._convert_loops_only,
            self._combined_transform,
        ]
        
        # Select transformation type
        transform_type = self.rng.choice(transformations)
        result = transform_type(code)
        
        # Verify the transformed code is valid Python
        if not is_valid_python(result):
            # If invalid, try with different seed
            for offset in range(1, 10):
                try:
                    result = transform_type(code, seed=self.seed + offset)
                    if is_valid_python(result):
                        break
                except Exception:
                    continue
        
        return result
    
    def _reorder_only(self, code: str, seed: Optional[int] = None) -> str:
        """Apply only statement reordering.
        
        Args:
            code: Source code.
            seed: Optional seed override.
            
        Returns:
            Code with reordered statements.
        """
        use_seed = seed if seed is not None else self.seed
        return reorder_statements(code, seed=use_seed)
    
    def _add_dead_code_only(self, code: str, seed: Optional[int] = None) -> str:
        """Apply only dead code insertion.
        
        Args:
            code: Source code.
            seed: Optional seed override.
            
        Returns:
            Code with dead code added.
        """
        use_seed = seed if seed is not None else self.seed
        return add_dead_code(code, seed=use_seed)
    
    def _convert_loops_only(self, code: str, seed: Optional[int] = None) -> str:
        """Apply only loop conversion.
        
        Args:
            code: Source code.
            seed: Optional seed override.
            
        Returns:
            Code with converted loops.
        """
        use_seed = seed if seed is not None else self.seed
        return convert_loops(code, seed=use_seed)
    
    def _combined_transform(self, code: str, seed: Optional[int] = None) -> str:
        """Apply combined structural transformations.
        
        Args:
            code: Source code.
            seed: Optional seed override.
            
        Returns:
            Code with multiple structural changes.
        """
        use_seed = seed if seed is not None else self.seed
        return structural_transform(code, seed=use_seed)
    
    def generate_variations(self, code: str, n_variations: int = 3) -> List[str]:
        """Generate multiple Type-3 variations.
        
        Args:
            code: Source code to clone.
            n_variations: Number of variations to generate.
            
        Returns:
            List of Type-3 clones.
        """
        variations = []
        
        for i in range(n_variations):
            # Use different seed for each variation
            variation_seed = self.seed + i * 1000
            
            # Apply different transformation types
            if i % 3 == 0:
                variation = self._reorder_only(code, seed=variation_seed)
            elif i % 3 == 1:
                variation = self._add_dead_code_only(code, seed=variation_seed)
            else:
                variation = self._combined_transform(code, seed=variation_seed)
            
            if is_valid_python(variation):
                variations.append(variation)
        
        return variations


def generate_type3_clone(code: str, seed: int = 42) -> str:
    """Generate a Type-3 clone from source code.
    
    Args:
        code: Source code to clone.
        seed: Random seed for reproducibility.
        
    Returns:
        Type-3 clone with structural changes.
    """
    generator = Type3Generator(seed=seed)
    return generator.generate(code)


def generate_type3_variations(code: str, n_variations: int = 3, seed: int = 42) -> List[str]:
    """Generate multiple Type-3 variations.
    
    Args:
        code: Source code to clone.
        n_variations: Number of variations to generate.
        seed: Random seed for reproducibility.
        
    Returns:
        List of Type-3 clones.
    """
    generator = Type3Generator(seed=seed)
    return generator.generate_variations(code, n_variations)