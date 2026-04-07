"""Type-1 (Exact Clone) generator.

Generates exact clones with only whitespace and comment changes.
These are the easiest clones to detect.
"""
from __future__ import annotations

import random
import re
from typing import Optional

from src.benchmark.generators.base_loader import CodePool


class Type1Generator:
    """Generator for Type-1 (exact) clones.
    
    Type-1 clones are identical code with only whitespace,
    formatting, or comment changes.
    """
    
    def __init__(self, seed: int = 42):
        """Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)
    
    def generate(self, code: str) -> str:
        """Generate a Type-1 clone from source code.
        
        Args:
            code: Source code to clone.
            
        Returns:
            Type-1 clone with whitespace/comment changes.
        """
        # Apply one or more transformations
        transformations = [
            self._add_whitespace,
            self._add_comments,
            self._change_indentation,
            self._add_blank_lines,
        ]
        
        # Apply 1-3 random transformations
        n_transforms = self.rng.randint(1, 3)
        selected = self.rng.sample(transformations, min(n_transforms, len(transformations)))
        
        result = code
        for transform in selected:
            result = transform(result)
        
        return result
    
    def _add_whitespace(self, code: str) -> str:
        """Add extra whitespace around operators.
        
        Args:
            code: Source code.
            
        Returns:
            Code with extra whitespace.
        """
        # Add spaces around operators
        replacements = [
            (r'(\w)\+(\w)', r'\1 + \2'),
            (r'(\w)-(\w)', r'\1 - \2'),
            (r'(\w)\*(\w)', r'\1 * \2'),
            (r'(\w)/(\w)', r'\1 / \2'),
            (r'(\w)=(\w)', r'\1 = \2'),
            (r'(\w)==(\w)', r'\1 == \2'),
            (r'(\w)<(\w)', r'\1 < \2'),
            (r'(\w)>(\w)', r'\1 > \2'),
        ]
        
        result = code
        for pattern, replacement in replacements:
            if self.rng.random() < 0.5:  # 50% chance to apply each
                result = re.sub(pattern, replacement, result)
        
        return result
    
    def _add_comments(self, code: str) -> str:
        """Add comments to code.
        
        Args:
            code: Source code.
            
        Returns:
            Code with added comments.
        """
        lines = code.split('\n')
        result_lines = []
        
        comments = [
            "# TODO: implement this",
            "# FIXME: handle edge case",
            "# NOTE: important logic",
            "# HACK: temporary solution",
            "# REVIEW: check this",
            "# OPTIMIZE: performance",
        ]
        
        for line in lines:
            result_lines.append(line)
            
            # Add comment after some lines (20% chance)
            if self.rng.random() < 0.2:
                indent = len(line) - len(line.lstrip())
                comment = ' ' * indent + self.rng.choice(comments)
                result_lines.append(comment)
        
        return '\n'.join(result_lines)
    
    def _change_indentation(self, code: str) -> str:
        """Change indentation style.
        
        Args:
            code: Source code.
            
        Returns:
            Code with changed indentation.
        """
        # Convert 4-space to 2-space or vice versa
        lines = code.split('\n')
        result_lines = []
        
        for line in lines:
            if line.strip():  # Non-empty line
                # Count leading spaces
                leading_spaces = len(line) - len(line.lstrip())
                
                # Randomly change indentation
                if self.rng.random() < 0.3:
                    if leading_spaces >= 4:
                        # Reduce indentation
                        new_indent = leading_spaces - 2
                        line = ' ' * new_indent + line.lstrip()
                    else:
                        # Increase indentation
                        new_indent = leading_spaces + 2
                        line = ' ' * new_indent + line.lstrip()
            
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _add_blank_lines(self, code: str) -> str:
        """Add blank lines between statements.
        
        Args:
            code: Source code.
            
        Returns:
            Code with added blank lines.
        """
        lines = code.split('\n')
        result_lines = []
        
        for i, line in enumerate(lines):
            result_lines.append(line)
            
            # Add blank line after function/class definitions
            if line.strip().startswith(('def ', 'class ')):
                if i + 1 < len(lines) and lines[i + 1].strip():
                    result_lines.append('')
            
            # Randomly add blank lines (10% chance)
            elif self.rng.random() < 0.1:
                result_lines.append('')
        
        return '\n'.join(result_lines)


def generate_type1_clone(code: str, seed: int = 42) -> str:
    """Generate a Type-1 clone from source code.
    
    Args:
        code: Source code to clone.
        seed: Random seed for reproducibility.
        
    Returns:
        Type-1 clone with whitespace/comment changes.
    """
    generator = Type1Generator(seed=seed)
    return generator.generate(code)