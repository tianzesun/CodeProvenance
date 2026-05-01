"""Code normalization for token and winnowing detection.

This layer removes comments and whitespace, normalizes identifiers, normalizes
literals, and returns stable tokens that are appropriate for k-gram and
winnowing fingerprinting.
"""

from __future__ import annotations

import io
import keyword
import re
import tokenize
from dataclasses import dataclass
from typing import Dict, Iterable, List


PYTHON_LITERAL_TYPES = {tokenize.NUMBER, tokenize.STRING}
PYTHON_SKIP_TYPES = {
    tokenize.COMMENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.NL,
    tokenize.NEWLINE,
}


@dataclass(frozen=True)
class NormalizedCode:
    """Normalized source text and token stream."""

    tokens: List[str]
    normalized_code: str
    identifier_count: int
    literal_count: int


class CodeNormalizer:
    """Normalize code for copy/rename-resistant token comparison."""

    def normalize(self, source: str, language: str = "python") -> NormalizedCode:
        """Normalize source code into stable tokens and compact text."""
        if language.lower() in {"python", "py", "python3"}:
            tokens = self._normalize_python(source)
        else:
            tokens = self._normalize_generic(source)

        identifier_count = sum(1 for token in tokens if token.startswith("ID_"))
        literal_count = sum(1 for token in tokens if token.startswith("LIT_"))
        return NormalizedCode(
            tokens=tokens,
            normalized_code=" ".join(tokens),
            identifier_count=identifier_count,
            literal_count=literal_count,
        )

    def kgrams(self, tokens: Iterable[str], k: int = 5) -> List[tuple[str, ...]]:
        """Build ordered k-grams from a normalized token stream."""
        token_list = list(tokens)
        if k <= 0:
            raise ValueError("k must be positive")
        if len(token_list) < k:
            return [tuple(token_list)] if token_list else []
        return [
            tuple(token_list[index : index + k])
            for index in range(len(token_list) - k + 1)
        ]

    def _normalize_python(self, source: str) -> List[str]:
        """Normalize Python source with the standard tokenizer."""
        identifier_map: Dict[str, str] = {}
        tokens: List[str] = []

        try:
            token_stream = tokenize.generate_tokens(io.StringIO(source or "").readline)
            for token in token_stream:
                token_type = token.type
                token_text = token.string
                if token_type in PYTHON_SKIP_TYPES:
                    continue
                if token_type == tokenize.NAME:
                    tokens.append(self._normalize_name(token_text, identifier_map))
                elif token_type == tokenize.NUMBER:
                    tokens.append("LIT_NUM")
                elif token_type == tokenize.STRING:
                    tokens.append("LIT_STR")
                elif token_type == tokenize.OP:
                    tokens.append(token_text)
                else:
                    compact = token_text.strip()
                    if compact:
                        tokens.append(compact)
        except (IndentationError, SyntaxError, tokenize.TokenError):
            return self._normalize_generic(source)

        return tokens

    def _normalize_generic(self, source: str) -> List[str]:
        """Normalize non-Python or syntactically invalid source with regex fallback."""
        cleaned = re.sub(r"//.*?$|#.*?$", "", source or "", flags=re.MULTILINE)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(
            r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " LIT_STR ", cleaned
        )
        cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", " LIT_NUM ", cleaned)
        raw_tokens = re.findall(r"[A-Za-z_]\w*|LIT_STR|LIT_NUM|[^\s\w]", cleaned)
        identifier_map: Dict[str, str] = {}
        return [self._normalize_name(token, identifier_map) for token in raw_tokens]

    def _normalize_name(self, token: str, identifier_map: Dict[str, str]) -> str:
        """Normalize identifiers while preserving language keywords."""
        if token in {"LIT_STR", "LIT_NUM"}:
            return token
        if keyword.iskeyword(token) or token in {"True", "False", "None"}:
            return token
        if re.fullmatch(r"[A-Za-z_]\w*", token):
            if token not in identifier_map:
                identifier_map[token] = f"ID_{len(identifier_map)}"
            return identifier_map[token]
        return token
