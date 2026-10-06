"""Small regex lexers shared by TokenIR, the C-like structural parser and fallbacks.

They are deliberately forgiving (unterminated strings/comments run to the end
of the line/file instead of raising) and understand comments, strings, template
literals, numbers and multi-character operators, which the old per-line regex
tokenizers did not.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class RawToken:
    kind: str  # comment | string | number | ident | op | punct
    text: str
    line: int  # 1-based
    col: int  # 0-based, in characters
    end_line: int
    end_col: int


_IDENT = r"(?:[^\W\d]|\$)[\w$]*"
_C_NUMBER = (
    r"0[xX][0-9a-fA-F_]+[lLn]?|0[bB][01_]+[lLn]?"
    r"|(?:\d[\d_]*(?:\.\d[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?[fFdDlLn]?"
)
_PY_NUMBER = (
    r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+"
    r"|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?[jJ]?"
)
_C_OPS = (
    r">>>=|<<=|>>=|>>>|===|!==|\*\*=|\.\.\.|&&=|\|\|=|\?\?=|<=|>=|==|!=|&&|\|\|"
    r"|\+\+|--|\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<|>>|->|=>|\?\?|\?\.|::|\*\*"
    r"|[-+*/%=<>!&|^~?]"
)
_PY_OPS = r"\*\*=|//=|>>=|<<=|\.\.\.|->|:=|==|!=|<=|>=|\*\*|//|<<|>>|[-+*/%&|^@<>=]=?|~"

_STRINGS = {
    "java": r'"""[\s\S]*?(?:"""|\Z)|"(?:\\.|[^"\\\n])*"?|\'(?:\\.|[^\'\\\n])*\'?',
    "javascript": r'"(?:\\.|[^"\\\n])*"?|\'(?:\\.|[^\'\\\n])*\'?|`(?:\\.|[^`\\])*`?',
    "python": (
        r"(?i:[rbuf]{1,2})?(?:\"\"\"[\s\S]*?(?:\"\"\"|\Z)|'''[\s\S]*?(?:'''|\Z)"
        r"|\"(?:\\.|[^\"\\\n])*\"?|'(?:\\.|[^'\\\n])*'?)"
    ),
}
_COMMENTS = {
    "java": r"//[^\n]*|/\*[\s\S]*?(?:\*/|\Z)",
    "javascript": r"//[^\n]*|/\*[\s\S]*?(?:\*/|\Z)",
    "python": r"#[^\n]*",
}


def _compile(language: str) -> re.Pattern[str]:
    py = language == "python"
    return re.compile(
        f"(?P<comment>{_COMMENTS[language]})"
        f"|(?P<string>{_STRINGS[language]})"
        f"|(?P<number>{_PY_NUMBER if py else _C_NUMBER})"
        f"|(?P<ident>{_IDENT})"
        f"|(?P<op>{_PY_OPS if py else _C_OPS})"
        r"|(?P<punct>[(){}\[\];,.:@#\\]|\S)"
    )


_PATTERNS = {lang: _compile(lang) for lang in _STRINGS}


def lex(source: str, language: str) -> list[RawToken]:
    """Tokenize ``source`` (comments included) for 'python'/'java'/'javascript'."""
    pattern = _PATTERNS[language]
    line_starts = [0]
    for m in re.finditer("\n", source):
        line_starts.append(m.end())

    def position(offset: int) -> tuple[int, int]:
        idx = bisect_right(line_starts, offset) - 1
        return idx + 1, offset - line_starts[idx]

    tokens: list[RawToken] = []
    for m in pattern.finditer(source):
        kind = m.lastgroup or "punct"
        line, col = position(m.start())
        end_line, end_col = position(m.end())
        tokens.append(RawToken(kind, m.group(), line, col, end_line, end_col))
    return tokens
