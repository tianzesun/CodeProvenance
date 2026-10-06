"""
Token-based Intermediate Representation.

Provides sequence-based representation of code using tokens.
"""

import io
import keyword
import tokenize
from dataclasses import dataclass, replace
from typing import Any

from ._lexer import lex
from .base_ir import BaseIR, IRMetadata, normalize_language

_PY_PUNCTUATION = frozenset("()[]{},.:;@")
_NULLS = {
    "python": frozenset({"None"}),
    "java": frozenset({"null"}),
    "javascript": frozenset({"null", "undefined"}),
}
_JAVA_KEYWORDS = frozenset(
    [
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
        "var",
    ]
)
_JS_KEYWORDS = frozenset(
    [
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "finally",
        "for",
        "function",
        "if",
        "implements",
        "import",
        "in",
        "instanceof",
        "interface",
        "let",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
    ]
)
_KEYWORDS = {
    "python": frozenset(keyword.kwlist) - {"True", "False", "None"},
    "java": _JAVA_KEYWORDS,
    "javascript": _JS_KEYWORDS,
}


@dataclass
class Token:
    """Represents a single token in the code.

    Attributes:
        token_type: KEYWORD, IDENTIFIER, OPERATOR, PUNCTUATION, NUMBER, STRING,
            BOOLEAN, NULL (or other types from converters, e.g. SYMBOL)
        value: String value of the token
        line: Line number where token appears (1-indexed)
        column: Column number where token starts (0-indexed)
        normalized: Normalized form (e.g., all identifiers become 'ID')
    """

    token_type: str
    value: str
    line: int = 0
    column: int = 0
    normalized: str = ""

    def __post_init__(self):
        if not self.normalized:
            self.normalized = self._normalize()

    def _normalize(self) -> str:
        """Identifiers become 'ID', literals become their type."""
        if self.token_type == "IDENTIFIER":
            return "ID"
        if self.token_type == "STRING":
            return "STRING_LITERAL"
        if self.token_type == "NUMBER":
            return "NUMBER_LITERAL"
        if self.token_type == "BOOLEAN":
            return "BOOLEAN_LITERAL"
        if self.token_type == "NULL":
            return "NULL_LITERAL"
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_type": self.token_type,
            "value": self.value,
            "line": self.line,
            "column": self.column,
            "normalized": self.normalized,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Token":
        return cls(
            token_type=data["token_type"],
            value=data["value"],
            line=data.get("line", 0),
            column=data.get("column", 0),
            normalized=data.get("normalized", ""),
        )

    def __repr__(self) -> str:
        if self.value != self.normalized:
            return f"Token({self.token_type}, '{self.value}' → '{self.normalized}')"
        return f"Token({self.token_type}, '{self.value}')"


def _classify_word(word: str, language: str) -> str:
    if word in (("True", "False") if language == "python" else ("true", "false")):
        return "BOOLEAN"
    if word in _NULLS[language]:
        return "NULL"
    if word in _KEYWORDS[language]:
        return "KEYWORD"
    return "IDENTIFIER"


class TokenIR(BaseIR):
    """Token-based intermediate representation.

    Represents code as a sequence of tokens, useful for
    fingerprinting and winnowing algorithms.
    """

    REPRESENTATION_TYPE = "token"

    def __init__(self, tokens: list[Token], metadata: IRMetadata):
        super().__init__(metadata)
        self.tokens = tokens

    def to_dict(self) -> dict[str, Any]:
        """Serialize Token IR to dictionary."""
        return {
            "tokens": [token.to_dict() for token in self.tokens],
            "token_count": len(self.tokens),
            "unique_token_types": sorted(self.get_unique_types()),
            "unique_values": sorted(self.get_unique_values()),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], metadata: IRMetadata | None = None
    ) -> "TokenIR":
        """Deserialize Token IR from ``to_dict()`` output.

        A payload without ``"tokens"`` yields an empty placeholder IR (the old
        implementation returned that for *every* input and lost the tokens).
        """
        meta = cls._resolve_metadata(data, metadata)
        tokens = (
            [Token.from_dict(t) for t in data["tokens"]]
            if isinstance(data, dict) and "tokens" in data
            else []
        )
        return cls(tokens=tokens, metadata=meta)

    def _load_from_dict(self, data: dict[str, Any]) -> None:
        self.tokens = [Token.from_dict(t) for t in data["tokens"]]

    def validate(self) -> bool:
        """Validate Token IR integrity."""
        if not self.metadata.validate():
            return False
        if not isinstance(self.tokens, list):
            return False
        return all(isinstance(token, Token) for token in self.tokens)

    @classmethod
    def from_source(
        cls, source_code: str, language: str, file_path: str | None = None
    ) -> "TokenIR":
        """Create Token IR from source code.

        Raises:
            ValueError: If language is not supported
        """
        language = normalize_language(language)
        tokens = cls._tokenize(source_code, language)  # fail before hashing
        metadata = cls.create_metadata(source_code, language, "token", file_path)
        return cls(tokens=tokens, metadata=metadata)

    @staticmethod
    def _tokenize(source_code: str, language: str) -> list[Token]:
        language = normalize_language(language)
        if language == "python":
            return TokenIR._tokenize_python(source_code)
        if language == "java":
            return TokenIR._tokenize_java(source_code)
        if language == "javascript":
            return TokenIR._tokenize_javascript(source_code)
        raise ValueError(f"Unsupported language: {language}")

    # ── Python ──────────────────────────────────────────────────────

    @staticmethod
    def _tokenize_python(source_code: str) -> list[Token]:
        """Tokenize Python with the stdlib ``tokenize`` module.

        Token types are mapped to the shared vocabulary. Before, Python tokens
        kept their ``tokenize`` names (NAME/OP), so identifiers were *never*
        normalized to ``ID`` and keywords were indistinguishable from names; an
        empty ENDMARKER token also ended every stream.

        f-strings are collapsed into one STRING token so the stream is the same
        on Python < 3.12 (one STRING) and >= 3.12 (FSTRING_START/MIDDLE/END).
        """
        lines = source_code.splitlines(keepends=True)
        tokens: list[Token] = []
        fstring_start: tuple[int, int] | None = None
        fstring_depth = 0
        try:
            for tok in tokenize.generate_tokens(io.StringIO(source_code).readline):
                name = tokenize.tok_name[tok.type]
                if name in (
                    "COMMENT",
                    "NL",
                    "NEWLINE",
                    "INDENT",
                    "DEDENT",
                    "ENDMARKER",
                ):
                    continue
                if name == "FSTRING_START":
                    if fstring_depth == 0:
                        fstring_start = tok.start
                    fstring_depth += 1
                    continue
                if name == "FSTRING_END":
                    fstring_depth -= 1
                    if fstring_depth == 0 and fstring_start is not None:
                        (sl, sc), (el, ec) = fstring_start, tok.end
                        if sl == el:
                            text = lines[sl - 1][sc:ec]
                        else:
                            text = (
                                lines[sl - 1][sc:]
                                + "".join(lines[sl : el - 1])
                                + lines[el - 1][:ec]
                            )
                        tokens.append(Token("STRING", text, sl, sc))
                        fstring_start = None
                    continue
                if fstring_depth > 0:
                    continue
                tokens.append(TokenIR._python_token(name, tok))
        except (tokenize.TokenError, SyntaxError):  # IndentationError is a SyntaxError
            return TokenIR._simple_tokenize(source_code)
        return tokens

    @staticmethod
    def _python_token(name: str, tok: "tokenize.TokenInfo") -> Token:
        value, (line, col) = tok.string, tok.start
        if name == "NAME":
            ttype = _classify_word(value, "python")
        elif name == "OP":
            ttype = "PUNCTUATION" if value in _PY_PUNCTUATION else "OPERATOR"
        elif name in ("NUMBER", "STRING"):
            ttype = name
        else:  # ERRORTOKEN etc.
            ttype = "OPERATOR" if not value.isidentifier() else "IDENTIFIER"
        return Token(token_type=ttype, value=value, line=line, column=col)

    @staticmethod
    def _simple_tokenize(source_code: str) -> list[Token]:
        """Lenient fallback for Python code that ``tokenize`` rejects.

        Uses the shared regex lexer (comment/string aware) instead of the old
        per-line split that treated comments and string contents as code.
        """
        return TokenIR._from_lexer(source_code, "python")

    # ── Java / JavaScript / fallback ────────────────────────────────

    @staticmethod
    def _from_lexer(source_code: str, language: str) -> list[Token]:
        tokens: list[Token] = []
        for raw in lex(source_code, language):
            if raw.kind == "comment":
                continue
            if raw.kind == "ident":
                ttype = _classify_word(raw.text, language)
            elif raw.kind == "string":
                ttype = "STRING"
            elif raw.kind == "number":
                ttype = "NUMBER"
            elif raw.kind == "op":
                ttype = "OPERATOR"
            else:
                ttype = "PUNCTUATION"
            tokens.append(Token(ttype, raw.text, raw.line, raw.col))
        return tokens

    @staticmethod
    def _tokenize_java(source_code: str) -> list[Token]:
        """Tokenize Java: comments skipped; strings, text blocks, floats and
        multi-character operators (``==``, ``&&``, ``->`` ...) are single
        tokens. The old tokenizer labelled ``==``/``&&``/``+=`` IDENTIFIER,
        split ``3.14`` into three tokens and tokenized comment/string text as
        code."""
        return TokenIR._from_lexer(source_code, "java")

    @staticmethod
    def _tokenize_javascript(source_code: str) -> list[Token]:
        """Tokenize JavaScript (template literals are single STRING tokens;
        regex literals are not recognised)."""
        return TokenIR._from_lexer(source_code, "javascript")

    # ── queries ─────────────────────────────────────────────────────

    def get_unique_types(self) -> set[str]:
        return {token.token_type for token in self.tokens}

    def get_unique_values(self) -> set[str]:
        return {token.value for token in self.tokens}

    def get_normalized_sequence(self) -> list[str]:
        """Sequence of normalized token values (for fingerprinting/comparison)."""
        return [token.normalized for token in self.tokens]

    def get_token_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for token in self.tokens:
            counts[token.token_type] = counts.get(token.token_type, 0) + 1
        return counts

    def filter_by_type(self, token_types: set[str]) -> "TokenIR":
        """New TokenIR with only the given token types (metadata is copied)."""
        filtered = [t for t in self.tokens if t.token_type in token_types]
        return TokenIR(tokens=filtered, metadata=replace(self.metadata))

    def get_ngrams(self, n: int = 3) -> list[list[str]]:
        """N-grams of normalized tokens.

        Raises:
            ValueError: If ``n < 1`` (``n=0`` used to return len+1 empty lists).
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        normalized = self.get_normalized_sequence()
        return [normalized[i : i + n] for i in range(len(normalized) - n + 1)]

    def get_statistics(self) -> dict[str, Any]:
        return {
            "total_tokens": len(self.tokens),
            "unique_types": len(self.get_unique_types()),
            "unique_values": len(self.get_unique_values()),
            "type_counts": self.get_token_type_counts(),
            "lines_spanned": max((t.line for t in self.tokens), default=0),
        }

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (
            f"TokenIR(tokens={stats['total_tokens']}, types={stats['unique_types']}, "
            f"language={self.metadata.language})"
        )

    def __len__(self) -> int:
        return len(self.tokens)

    def __iter__(self):
        return iter(self.tokens)

    def __getitem__(self, index):
        return self.tokens[index]
