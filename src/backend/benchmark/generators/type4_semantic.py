"""Type-4 (Semantic Clone) generator.

Generates semantic clones with different implementations
but same functionality. Includes Easy, Medium, and Hard levels.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from src.backend.benchmark.generators.base_loader import CodePool
from src.backend.benchmark.generators.utils.rename_utils import rename_identifiers
from src.backend.benchmark.generators.utils.transform_utils import structural_transform
from src.backend.benchmark.generators.utils.ast_utils import is_valid_python


class Type4Generator:
    """Generator for Type-4 (semantic) clones.
    
    Type-4 clones have the same functionality but different
    implementations. Includes three difficulty levels:
    - Easy: Partial token overlap
    - Medium: Refactored structure
    - Hard: LLM-transformed (simulated)
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def generate(self, code: str, difficulty: str = "medium") -> str:
        """Generate a Type-4 clone from source code.
        
        Args:
            code: Source code to clone.
            difficulty: Difficulty level ("easy", "medium", "hard").
            
        Returns:
            Type-4 clone with semantic changes.
        """
        if difficulty == "easy":
            return self._generate_easy(code)
        elif difficulty == "medium":
            return self._generate_medium(code)
        elif difficulty == "hard":
            return self._generate_hard(code)
        else:
            return self._generate_medium(code)
    
    def _generate_easy(self, code: str) -> str:
        """Generate easy Type-4 clone (partial token overlap).
        
        Args:
            code: Source code.
            
        Returns:
            Easy semantic clone.
        """
        # Combine rename + small structure change
        renamed = rename_identifiers(code, seed=self.seed)
        
        # Add small structural change
        result = structural_transform(renamed, seed=self.seed + 100)
        
        # Verify validity
        if not is_valid_python(result):
            return renamed
        
        return result
    
    def _generate_medium(self, code: str) -> str:
        """Generate medium Type-4 clone (refactored structure).
        
        Args:
            code: Source code.
            
        Returns:
            Medium semantic clone.
        """
        # Apply multiple transformations
        result = code
        
        # Step 1: Rename identifiers
        result = rename_identifiers(result, seed=self.seed)
        
        # Step 2: Apply structural transformations
        result = structural_transform(result, seed=self.seed + 200)
        
        # Step 3: Add dead code
        from src.backend.benchmark.generators.utils.transform_utils import add_dead_code
        result = add_dead_code(result, seed=self.seed + 300)
        
        # Verify validity
        if not is_valid_python(result):
            # Fallback to simpler transformation
            result = rename_identifiers(code, seed=self.seed)
        
        return result
    
    def _generate_hard(self, code: str) -> str:
        """Generate hard Type-4 clone (LLM-transformed simulation).
        
        Simulates LLM transformation by applying aggressive
        structural changes while preserving logic.
        
        Args:
            code: Source code.
            
        Returns:
            Hard semantic clone.
        """
        # Simulate LLM transformation with multiple passes
        result = code
        
        # Pass 1: Aggressive renaming
        result = rename_identifiers(result, seed=self.seed)
        
        # Pass 2: Structural transformation
        result = structural_transform(result, seed=self.seed + 400)
        
        # Pass 3: Add complex dead code
        from src.backend.benchmark.generators.utils.transform_utils import add_dead_code
        for _ in range(3):
            result = add_dead_code(result, seed=self.seed + 500 + _)
        
        # Pass 4: Convert loops
        from src.backend.benchmark.generators.utils.transform_utils import convert_loops
        result = convert_loops(result, seed=self.seed + 600)
        
        # Verify validity
        if not is_valid_python(result):
            # Fallback to medium difficulty
            return self._generate_medium(code)
        
        return result
    
    def generate_all_difficulties(self, code: str) -> Dict[str, str]:
        """Generate Type-4 clones at all difficulty levels.
        
        Args:
            code: Source code to clone.
            
        Returns:
            Dictionary mapping difficulty to clone.
        """
        return {
            "easy": self._generate_easy(code),
            "medium": self._generate_medium(code),
            "hard": self._generate_hard(code),
        }


def generate_type4_clone(code: str, difficulty: str = "medium", seed: int = 42) -> str:
    """Generate a Type-4 clone from source code.
    
    Args:
        code: Source code to clone.
        difficulty: Difficulty level ("easy", "medium", "hard").
        seed: Random seed for reproducibility.
        
    Returns:
        Type-4 clone with semantic changes.
    """
    generator = Type4Generator(seed=seed)
    return generator.generate(code, difficulty)


def generate_type4_all_difficulties(code: str, seed: int = 42) -> Dict[str, str]:
    """Generate Type-4 clones at all difficulty levels.
    
    Args:
        code: Source code to clone.
        seed: Random seed for reproducibility.
        
    Returns:
        Dictionary mapping difficulty to clone.
    """
    generator = Type4Generator(seed=seed)
    return generator.generate_all_difficulties(code)