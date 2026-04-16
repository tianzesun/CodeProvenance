"""
Lexical baseline adapter.

Simple n-gram and token overlap baseline plagiarism detector.
Used as a lower bound reference for benchmark validation.
"""
from __future__ import annotations

from typing import Any, Dict, List
import hashlib
from collections import defaultdict

from .base_adapter import BaseAdapter


class LexicalBaselineAdapter(BaseAdapter):
    """
    Lexical baseline detector using 5-gram winnowing algorithm.
    This is the minimum acceptable performance baseline.
    """

    name = "lexical_baseline"
    version = "1.0.0"

    def __init__(self, ngram_size: int = 5, window_size: int = 20):
        self.ngram_size = ngram_size
        self.window_size = window_size

    def run(self, dataset: Any) -> Dict[str, Any]:
        """Run lexical baseline detection on dataset."""
        predictions = defaultdict(float)

        for pair in dataset.pairs:
            score = self._calculate_similarity(pair.code_a, pair.code_b)
            predictions[f"{pair.id}"] = score

        return predictions

    def _calculate_similarity(self, code_a: str, code_b: str) -> float:
        """Calculate simple token overlap similarity."""
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)

        if not tokens_a or not tokens_b:
            return 0.0

        fingerprints_a = self._winnowing_fingerprint(tokens_a)
        fingerprints_b = self._winnowing_fingerprint(tokens_b)

        intersection = len(fingerprints_a & fingerprints_b)
        union = len(fingerprints_a | fingerprints_b)

        return intersection / union if union > 0 else 0.0

    def _tokenize(self, code: str) -> List[str]:
        """Simple whitespace and punctuation tokenizer."""
        tokens = []
        current = []

        for c in code:
            if c.isalnum():
                current.append(c)
            else:
                if current:
                    tokens.append(''.join(current))
                    current = []
                if not c.isspace():
                    tokens.append(c)

        if current:
            tokens.append(''.join(current))

        return tokens

    def _winnowing_fingerprint(self, tokens: List[str]) -> set[int]:
        """Generate winnowing hash fingerprints."""
        fingerprints = set()

        if len(tokens) < self.ngram_size:
            return fingerprints

        # Generate n-grams
        ngrams = []
        for i in range(len(tokens) - self.ngram_size + 1):
            ngram = '|'.join(tokens[i:i+self.ngram_size])
            h = int(hashlib.sha256(ngram.encode()).hexdigest(), 16)
            ngrams.append(h)

        # Winnowing algorithm
        for i in range(len(ngrams) - self.window_size + 1):
            window = ngrams[i:i+self.window_size]
            min_hash = min(window)
            fingerprints.add(min_hash)

        return fingerprints
