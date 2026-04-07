"""NiCad-like clone detection benchmark adapter.

NiCad uses:
1. Extract functions/blocks by parsing
2. Normalize identifiers (blind rename)
3. Compare normalized units using UPI (Unit of Paired Instances) threshold
4. Report clones above similarity threshold

Reference: J.R. Cordy & C.K. Roy, "NiCad: Accurate Detection of Near-Miss Clones"

FROZEN INTERFACE: evaluate() returns canonical EvaluationResult.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from src.benchmark.adapters.base_adapter import BaseAdapter
from src.benchmark.contracts.evaluation_result import EvaluationResult, EnrichedPair


class NiCadAdapter(BaseAdapter):
    """NiCad adapter with canonical output."""

    # Common keywords/operators preserved during normalization
    _KEYWORDS = frozenset([
        'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while',
        'import', 'from', 'try', 'except', 'finally', 'with', 'as',
        'in', 'not', 'and', 'or', 'is', 'None', 'True', 'False',
        'pass', 'break', 'continue', 'raise', 'yield', 'lambda',
        'public', 'private', 'protected', 'static', 'void', 'int',
        'float', 'double', 'char', 'boolean', 'string',
        'new', 'this', 'super', 'extends', 'implements',
        'const', 'let', 'var', 'function', 'async', 'await',
    ])

    def __init__(self, threshold: float = 0.5, dissimilarity_threshold: float = 0.05):
        """Initialize NiCad adapter.
        
        Args:
            threshold: Decision threshold for clone detection.
            dissimilarity_threshold: UPI dissimilarity threshold (0.0 = exact, 0.1 = up to 10% different)
        """
        self._threshold = threshold
        self._dissimilarity_threshold = dissimilarity_threshold

    @property
    def name(self) -> str:
        return "nicad"

    @property
    def version(self) -> str:
        return "6.2"

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate a code pair using NiCad - FROZEN INTERFACE.

        Args:
            pair: EnrichedPair with code snippets and metadata.

        Returns:
            EvaluationResult with canonical schema.
        """
        score = self._compare(pair.code_a, pair.code_b)
        return self._make_result(
            pair=pair,
            score=score,
            threshold=self._threshold,
            metadata={"dissimilarity_threshold": self._dissimilarity_threshold},
        )

    def _compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using NiCad-like approach."""
        if not code_a or not code_b:
            return 0.0

        # Normalize both snippets (blind rename identifiers)
        norm_a = self._normalize(code_a)
        norm_b = self._normalize(code_b)

        if not norm_a or not norm_b:
            return 0.0

        # Tokenize normalized code
        tokens_a = norm_a.split()
        tokens_b = norm_b.split()

        if not tokens_a or not tokens_b:
            return 0.0

        # Find matching tokens (UPI calculation)
        set_a, set_b = set(tokens_a), set(tokens_b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        if union == 0:
            return 0.0

        # Jaccard-based similarity
        similarity = intersection / union
        return max(0.0, min(1.0, similarity))

    def _normalize(self, code: str) -> str:
        """NiCad-style normalization with blind renaming."""
        # Remove comments
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

        # Remove string literals and numbers
        code = re.sub(r'"[^"]*"', '"STRING"', code)
        code = re.sub(r"'[^']*'", "'STRING'", code)
        code = re.sub(r'\b[0-9]+\.?[0-9]*\b', 'NUM', code)

        # Normalize whitespace
        code = re.sub(r'\s+', ' ', code.strip())

        # Blind rename: replace identifiers with generic tokens
        tokens = []
        id_counter = 0
        id_map = {}
        i = 0
        while i < len(code):
            c = code[i]
            if c.isalpha() or c == '_':
                j = i
                while j < len(code) and (code[j].isalnum() or code[j] == '_'):
                    j += 1
                word = code[i:j]
                if word in self._KEYWORDS:
                    tokens.append(word)
                else:
                    if word not in id_map:
                        id_map[word] = f'__ID{id_counter}__'
                        id_counter += 1
                    tokens.append(id_map[word])
                i = j
            else:
                tokens.append(c)
                i += 1

        return ' '.join(tokens)
