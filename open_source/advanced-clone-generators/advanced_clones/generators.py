"""
Advanced clone type generators for testing plagiarism detection systems.
"""

import random
import re
from enum import Enum


class CloneType(Enum):
    """Enumeration of clone types."""
    EXACT = 1
    RENAMED = 2
    RESTRUCTURED = 3
    SEMANTIC = 4
    ADVERSARIAL = 5
    LLM_REWRITE = 6


def generate_adversarial_clone(code: str, seed: int = 42) -> str:
    """
    Generate Type 5 adversarial clone using professional obfuscation techniques.
    """
    rng = random.Random(seed)
    modified = code

    # Rename identifiers to hex
    identifiers = _extract_identifiers(modified)
    rename_map = {}

    for idx, ident in enumerate(identifiers):
        new_name = f"_{idx:x}"
        rename_map[ident] = new_name

    for old, new in rename_map.items():
        modified = re.sub(rf'\b{re.escape(old)}\b', new, modified)

    # Insert dead code
    lines = modified.split('\n')
    if len(lines) > 3:
        insert_pos = rng.randint(1, len(lines) - 2)
        lines.insert(insert_pos, '    if False:')
        lines.insert(insert_pos + 1, '        unreachable = 42')

    return '\n'.join(lines)


def generate_llm_clone(code: str, seed: int = 42) -> str:
    """
    Generate Type 6 LLM rewrite using AI-style code transformations.
    """
    rng = random.Random(seed)
    modified = code

    # Rename to descriptive names
    identifiers = _extract_identifiers(modified)
    descriptive_names = [
        "input_values", "result", "output", "index", "counter", "current"
    ]

    rename_map = {}
    for idx, ident in enumerate(identifiers):
        new_name = descriptive_names[idx % len(descriptive_names)]
        rename_map[ident] = new_name

    for old, new in rename_map.items():
        modified = re.sub(rf'\b{re.escape(old)}\b', new, modified)

    # Add type hints
    lines = modified.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('def ') and '->' not in line:
            lines[i] = line.rstrip(':') + ' -> Any:'
            break

    return '\n'.join(lines)


def validate_clone_pair(original: str, transformed: str) -> bool:
    """Basic validation of clone pair."""
    # Simple check: both should contain 'def ' (function definitions)
    return 'def ' in original and 'def ' in transformed


def _extract_identifiers(code: str) -> set:
    """Extract Python identifiers from code."""
    potential_ids = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', code))

    keywords = {
        'def', 'return', 'if', 'else', 'for', 'while', 'import', 'from',
        'class', 'try', 'except', 'finally', 'with', 'as', 'in', 'not',
        'and', 'or', 'is', 'None', 'True', 'False', 'print', 'self',
        'int', 'float', 'str', 'list', 'dict', 'set', 'tuple', 'bool',
        'len', 'range', 'sum', 'max', 'min', 'enumerate'
    }

    return {
        ident for ident in potential_ids
        if ident not in keywords and len(ident) > 1
    }