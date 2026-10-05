"""Code normalization for token and winnowing detection.

Removes comments (and Python docstrings), normalizes identifiers and literals, and returns stable
tokens suitable for k-gram and winnowing fingerprinting.

What changed (all of it affects the comparison scores):
- ONE comment- and string-aware scanner for every language. The Python path used ``tokenize``
  with a regex fallback, so a file that failed to tokenize (an indentation error, an unclosed
  bracket: common in student code) was normalised with a DIFFERENT alphabet (single-character
  operators, ``#`` stripped in Java, ``//`` stripped as a comment in Python) and then compared
  against files normalised the normal way. On Python 3.12 ``tokenize`` also splits f-strings into
  FSTRING_* tokens, whose text leaked into the stream un-normalised.
- The fallback removed comments BEFORE strings, so a ``#`` or ``//`` inside a string literal
  (URLs) cut the line short.
- Built-ins (``len``, ``max``) and attribute names (``x.append`` vs ``x.remove``) are kept as they
  are. Everything used to become ``ID_n`` in order of first appearance, so ``max(a)`` and ``min(a)``
  were the same token sequence. ``normalize_attributes=True`` restores renaming of attributes.
- Docstrings are dropped like comments (a docstring used to be a ``LIT_STR`` token, so adding
  or removing one changed the fingerprint).
- ``original_tokens`` / ``line_numbers`` run parallel to ``tokens`` (needed to find real renames and
  to remove starter code by line); ``distinct_identifier_count`` is new (``identifier_count``
  counts occurrences, as before).
- ``fingerprints()`` implements real winnowing; nothing computed it before.
- ``shape_tokens`` (every identifier is just ``ID``) is the stream to FINGERPRINT. ``ID_n`` numbers
  identifiers by first appearance in the file, so one extra or missing identifier near the top
  (an edited signature, an added import alias) renumbers every later one and no k-gram containing
  an identifier matches any more: a renamed copy scored 0.04. Position-independent ``ID`` is what
  JPlag and MOSS use. ``tokens`` keeps the numbered form for callers that want it.
"""

from __future__ import annotations

import builtins
import keyword
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from hashlib import blake2b

MAX_SOURCE_CHARS = 2_000_000

_PYTHON = frozenset({"python", "py", "python3"})
_HASH_LANGS = frozenset({"python", "py", "python3", "ruby", "rb", "bash", "sh", "shell", "perl", "r", "yaml", "makefile"})
_SLASH_LANGS = frozenset(
    {"java", "c", "cpp", "c++", "cc", "h", "hpp", "cs", "csharp", "c#", "javascript", "js", "jsx",
     "typescript", "ts", "tsx", "go", "golang", "rust", "rs", "kotlin", "kt", "swift", "scala", "php", "dart"}
)  # fmt: skip

_COMMON_KEYWORDS = frozenset(
    {"if", "else", "for", "while", "do", "switch", "case", "default", "break", "continue", "return",
     "try", "catch", "finally", "throw", "throws", "class", "struct", "interface", "enum", "public",
     "private", "protected", "static", "final", "void", "new", "this", "super", "null", "true",
     "false", "import", "package", "extends", "implements", "const", "let", "var", "function",
     "func", "fn", "int", "long", "double", "float", "char", "bool", "boolean", "string", "byte",
     "short", "unsigned", "signed", "sizeof", "typeof", "instanceof", "namespace", "using",
     "include", "define", "async", "await", "yield", "in", "of", "is", "as", "and", "or", "not"}
)  # fmt: skip
_PY_KEYWORDS = frozenset(keyword.kwlist) | frozenset(getattr(keyword, "softkwlist", ()))
_BUILTINS = frozenset(n for n in dir(builtins) if not n.startswith("_"))
_TRIVIAL_WORDS = frozenset({"else", "try", "finally", "pass", "break", "continue", "return", "do", "end", "begin"})

_STRING = (
    r"""(?:[rRbBuUfF]{1,2})?(?:\"\"\"(?:\\.|[^\\])*?\"\"\"|'''(?:\\.|[^\\])*?'''"""
    r"""|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')"""
)
_NUMBER = (
    r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+"
    r"|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?[jJlLfFuU]*"
)
_IDENT = r"[^\W\d]\w*"
_OP = (
    r"\*\*=|//=|>>=|<<=|\.\.\.|->|:=|==|!=|<=|>=|\*\*|//|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=|&&|\|\||\+\+|--|::|=>"
    r"|\S"
)
_COMMENTS = {"hash": r"\#[^\n]*", "slash": r"//[^\n]*|/\*.*?\*/"}
_PATTERNS: dict[str, re.Pattern[str]] = {}
_PYTHON_HINT = re.compile(r"^[ \t]*(?:def[ \t]+\w+|class[ \t]+\w+[^\n{;]*:|elif\b|import[ \t]+\w|from[ \t]+[\w.]+[ \t]+import)", re.M)
_OPEN, _CLOSE = "([{", ")]}"


def _pattern(style: str) -> re.Pattern[str]:
    pattern = _PATTERNS.get(style)
    if pattern is None:
        pattern = _PATTERNS[style] = re.compile(
            f"(?P<comment>{_COMMENTS[style]})|(?P<string>{_STRING})|(?P<number>{_NUMBER})|(?P<ident>{_IDENT})|(?P<op>{_OP})",
            re.DOTALL,
        )
    return pattern


def _comment_style(source: str, language: str) -> str:
    if language in _HASH_LANGS:
        return "hash"
    if language in _SLASH_LANGS:
        return "slash"
    return "hash" if _PYTHON_HINT.search(source) else "slash"  # unknown language: guess from the source


def hash64(text: str) -> int:
    """Stable 64-bit hash (``hash()`` is randomised per process)."""
    return int.from_bytes(blake2b(text.encode("utf-8", "surrogatepass"), digest_size=8).digest(), "big")


@dataclass(frozen=True)
class NormalizedCode:
    """Normalized source text and token stream."""

    tokens: list[str]
    normalized_code: str
    identifier_count: int  # ID_ token OCCURRENCES
    literal_count: int
    #: original text of each token (same length as ``tokens``); used to find real renames
    original_tokens: list[str] = field(default_factory=list)
    #: 1-based line each token STARTS on (same length as ``tokens``)
    line_numbers: list[int] = field(default_factory=list)
    distinct_identifier_count: int = 0
    #: ``tokens`` with every ``ID_n`` replaced by ``ID``: stable under added/removed identifiers
    shape_tokens: list[str] = field(default_factory=list)


class CodeNormalizer:
    """Normalize code for copy/rename-resistant token comparison."""

    def __init__(self, normalize_attributes: bool = False) -> None:
        #: When True, names after a dot are renamed too (more rename-resistant, but
        #: ``x.append`` and ``x.remove`` then look alike).
        self.normalize_attributes = normalize_attributes

    def normalize(self, source: str, language: str = "python") -> NormalizedCode:
        """Normalize source code into stable tokens and compact text."""
        language = str(language or "python").strip().lower()
        source = (source or "")[:MAX_SOURCE_CHARS]
        python = language in _PYTHON
        keywords = _PY_KEYWORDS if python else (_PY_KEYWORDS | _COMMON_KEYWORDS)
        protected = keywords | (_BUILTINS if python else frozenset())

        tokens: list[str] = []
        originals: list[str] = []
        lines: list[int] = []
        ids: dict[str, str] = {}
        depth = 0
        previous = ""

        for match in _pattern(_comment_style(source, language)).finditer(source):
            kind, text = match.lastgroup, match.group()
            if kind == "comment":
                continue
            if kind == "string":
                if python and depth == 0 and self._alone_on_its_line(source, match):
                    continue  # docstring / bare string statement
                token = "LIT_STR"
            elif kind == "number":
                token = "LIT_NUM"
            elif kind == "ident":
                if text in protected or (text.startswith("__") and text.endswith("__")):
                    token = text
                elif previous == "." and not self.normalize_attributes:
                    token = text  # attribute names stay as written
                else:
                    token = ids.setdefault(text, f"ID_{len(ids)}")
            else:
                token = text
                if text in _OPEN:
                    depth += 1
                elif text in _CLOSE:
                    depth = max(0, depth - 1)
            tokens.append(token)
            originals.append(text)
            lines.append(match.start())  # converted to line numbers below
            previous = text if kind == "op" else ""

        lines = self._to_line_numbers(source, lines)
        return NormalizedCode(
            tokens=tokens,
            normalized_code=" ".join(tokens),
            identifier_count=sum(1 for t in tokens if t.startswith("ID_")),
            literal_count=sum(1 for t in tokens if t.startswith("LIT_")),
            original_tokens=originals,
            line_numbers=lines,
            distinct_identifier_count=len(ids),
            shape_tokens=["ID" if t.startswith("ID_") else t for t in tokens],
        )

    @staticmethod
    def _alone_on_its_line(source: str, match: re.Match[str]) -> bool:
        """True when only whitespace (and maybe a comment) surrounds the string on its lines."""
        line_start = source.rfind("\n", 0, match.start()) + 1
        if source[line_start : match.start()].strip():
            return False
        line_end = source.find("\n", match.end())
        rest = source[match.end() : len(source) if line_end < 0 else line_end].strip()
        return rest == "" or rest.startswith("#")

    @staticmethod
    def _to_line_numbers(source: str, offsets: list[int]) -> list[int]:
        """Line number for each ascending character offset (one pass over the source)."""
        numbers, line, position = [], 1, 0
        for offset in offsets:
            line += source.count("\n", position, offset)
            position = offset
            numbers.append(line)
        return numbers

    def kgrams(self, tokens: Iterable[str], k: int = 5) -> list[tuple[str, ...]]:
        """Build ordered k-grams from a normalized token stream."""
        if k <= 0:
            raise ValueError("k must be positive")
        token_list = list(tokens)
        if len(token_list) < k:
            return [tuple(token_list)] if token_list else []
        return [tuple(token_list[index : index + k]) for index in range(len(token_list) - k + 1)]

    def fingerprints(self, tokens: Iterable[str], k: int = 5, window: int = 4) -> set[int]:
        """Winnowed fingerprint set (Schleimer et al.): the minimum k-gram hash of every window.

        A stream shorter than ``k`` tokens has no fingerprints (it used to be one short "k-gram"
        that could never match a longer one).
        """
        if k <= 0 or window <= 0:
            raise ValueError("k and window must be positive")
        token_list = list(tokens)
        if len(token_list) < k:
            return set()
        hashes = [hash64(" ".join(token_list[i : i + k])) for i in range(len(token_list) - k + 1)]
        if len(hashes) <= window:
            return {min(hashes)}
        return {min(hashes[i : i + window]) for i in range(len(hashes) - window + 1)}

    @staticmethod
    def is_trivial_line(tokens: list[str]) -> bool:
        """A line with nothing but punctuation or a lone ``else`` / ``pass`` / ``return`` ..."""
        return not tokens or all(not re.match(r"\w", t) or t in _TRIVIAL_WORDS for t in tokens) or (
            len(tokens) == 1
        )
