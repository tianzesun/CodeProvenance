"""Deterministic engine — guarantees reproducibility across all evaluation runs.

Enforces:
- Fixed random seed
- Fixed ordering of pairs
- Deterministic tokenization
- No parallel race conditions affecting order
"""
from __future__ import annotations

import os
import random
import re
from typing import Any, Dict, List


def set_determinism(seed: int = 42) -> None:
    """Set all sources of non-determinism to a fixed seed."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass


def sorted_pairs(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort pairs deterministically by file paths."""
    return sorted(pairs, key=lambda p: (p.get("file1", ""), p.get("file2", "")))


def deterministic_tokenize(code: str) -> List[str]:
    """Tokenize code deterministically."""
    tokens = re.findall(r'[a-zA-Z_]\w*|\d+|[^\s\w]', code)
    return tokens
