"""Comment- and string-aware lexical scanning shared by the similarity engines.

Several engines stripped comments and strings with chains of ``re.sub`` calls such
as ``re.sub(r'["\\'].*?["\\']', "STR", text, flags=re.DOTALL)`` run BEFORE the
comments were removed. A single apostrophe in a comment (``# don't``) then paired
with the next quote anywhere below it, and everything in between, real code
included, was replaced by ``STR``. Likewise ``//`` was treated as a comment start
in Python, where it is the floor-division operator, and ``#`` and ``//`` inside
string literals (URLs, f-strings) truncated lines.

This module scans in ONE pass, so a comment is only a comment outside a string and
a string only a string outside a comment, and it picks the comment syntax from the
language (or, when unknown, from the source itself).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

#: Languages whose line comments start with ``#``.
HASH_COMMENT_LANGUAGES = frozenset(
    {"python", "py", "python3", "ruby", "rb", "bash", "sh", "shell", "perl", "r",
     "powershell", "yaml", "elixir", "julia", "makefile", "toml"}  # fmt: skip
)
#: Languages that use ``//`` and ``/* */`` comments.
SLASH_COMMENT_LANGUAGES = frozenset(
    {"java", "c", "cpp", "c++", "cc", "h", "hpp", "csharp", "cs", "c#", "javascript",
     "js", "jsx", "typescript", "ts", "tsx", "go", "golang", "rust", "rs", "kotlin",
     "kt", "swift", "scala", "php", "dart", "objc"}  # fmt: skip
)

_PYTHON_HINT = re.compile(
    r"^[ \t]*(?:def[ \t]+\w+[ \t]*\(.*\)[ \t]*(?:->[^:\n]*)?:"
    r"|class[ \t]+\w+[^\n{;]*:[ \t]*$"
    r"|elif\b[^\n]*:"
    r"|if[ \t]+__name__"
    r"|(?:from[ \t]+[\w.]+[ \t]+)?import[ \t]+[\w., ]+[ \t]*$"
    r"|(?:if|while|for|else|try|except|with)\b[^\n{;]*:[ \t]*$)",
    re.MULTILINE,
)
# ``//`` only counts as a hint when it starts a comment (line start, or after ``;``/``{``/``}``):
# in ``b // 2`` it is Python's floor-division operator.
_SLASH_HINT = re.compile(
    r"(?:^|[;{}])[ \t]*//|/\*|;[ \t]*$|\{[ \t]*$|^[ \t]*#include|\bpublic[ \t]+static\b",
    re.MULTILINE,
)

_STRING = (
    r'(?P<string>(?:[rRbBuUfF]{1,2})?(?:'
    r'"""(?:\\.|[^\\])*?"""|\'\'\'(?:\\.|[^\\])*?\'\'\''  # triple-quoted (Python)
    r'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''  # single-line
    r"|`(?:\\.|[^`\\])*`"  # template literals (JS)
    r"))"
)
_NUMBER = r"(?P<number>0[xX][0-9a-fA-F_]+|\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?)"
_IDENT = r"(?P<ident>[A-Za-z_$][\w$]*)"
_OP = (
    r"(?P<op>==|!=|<=|>=|\*\*|//|->|=>|\+\+|--|&&|\|\||<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^="
    r"|::|\S)"
)
_COMMENT = {
    "hash": r"(?P<comment>#[^\n]*)",
    "slash": r"(?P<comment>//[^\n]*|/\*.*?\*/|^[ \t]*#[^\n]*)",
}
_PATTERNS: dict[str, re.Pattern[str]] = {}


def comment_style(source: str, language: str | None = None) -> str:
    """Return ``"hash"`` or ``"slash"``: how comments are written in ``source``.

    A known ``language`` decides. Otherwise the source is inspected: Python-shaped
    statements mean ``#`` comments (so ``//`` stays the division operator), C-like
    punctuation means ``//`` comments, and with no evidence ``#`` is assumed.
    """
    name = (language or "").strip().lower()
    if name in HASH_COMMENT_LANGUAGES:
        return "hash"
    if name in SLASH_COMMENT_LANGUAGES:
        return "slash"
    if _PYTHON_HINT.search(source):
        return "hash"
    if _SLASH_HINT.search(source):
        return "slash"
    # No evidence either way: ``#`` is the safe guess, because treating ``//`` as a
    # comment would destroy Python's floor division.
    return "hash"


def _pattern(style: str) -> re.Pattern[str]:
    pattern = _PATTERNS.get(style)
    if pattern is None:
        flags = re.DOTALL | re.MULTILINE
        pattern = re.compile(
            "|".join((_COMMENT[style], _STRING, _NUMBER, _IDENT, _OP)), flags
        )
        _PATTERNS[style] = pattern
    return pattern


def scan(source: str, language: str | None = None) -> Iterator[tuple[str, str]]:
    """Yield ``(kind, text)`` for every non-comment token.

    ``kind`` is ``"string"``, ``"number"``, ``"ident"`` or ``"op"``. Comments are
    skipped; whitespace never produces a token.
    """
    for match in _pattern(comment_style(source, language)).finditer(source):
        kind = match.lastgroup
        if kind != "comment":
            yield kind, match.group()  # type: ignore[misc]


def tokenize(
    source: str,
    language: str | None = None,
    *,
    normalize_literals: bool = True,
) -> list[str]:
    """Token strings; with ``normalize_literals`` strings become ``STR`` and numbers ``NUM``."""
    tokens: list[str] = []
    append = tokens.append
    for kind, text in scan(source, language):
        if normalize_literals and kind == "string":
            append("STR")
        elif normalize_literals and kind == "number":
            append("NUM")
        else:
            append(text)
    return tokens


def normalized_text(source: str, language: str | None = None) -> str:
    """Canonical one-line text: comments dropped, literals normalised, single spaces."""
    return " ".join(tokenize(source, language))


def strip_comments(source: str, language: str | None = None) -> str:
    """``source`` with comments removed (strings and layout preserved)."""
    pattern = _pattern(comment_style(source, language))
    return pattern.sub(lambda m: "" if m.lastgroup == "comment" else m.group(), source)
