"""Legacy code pre-processing helpers."""

from __future__ import annotations

import keyword
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── language handling ───────────────────────────────────────────────────────

_LANGUAGE_ALIASES = {
    "py": "python", "python3": "python",
    "js": "javascript", "jsx": "javascript", "ts": "javascript", "tsx": "javascript",
    "typescript": "javascript", "node": "javascript",
}  # fmt: skip
_CLIKE = {
    "java",
    "javascript",
    "c",
    "cpp",
    "c++",
    "csharp",
    "cs",
    "go",
    "rust",
    "kotlin",
    "swift",
}


def normalize_language(language: str) -> str:
    """Canonical language name ("Python" -> "python", "js" -> "javascript")."""
    lang = (language or "").strip().lower()
    return _LANGUAGE_ALIASES.get(lang, lang)


def detect_language(file_path: str) -> str:
    """Language from a file extension (default "python").

    Shared by every entry point; ``process_batch`` used to force one language
    on every file regardless of its extension.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix == ".java":
        return "java"
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        return "javascript"
    return "python"


_PY_KEYWORDS = frozenset(keyword.kwlist)
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
        "true",
        "false",
        "null",
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
        "true",
        "false",
        "null",
        "undefined",
    ]
)
_KEYWORDS = {"python": _PY_KEYWORDS, "java": _JAVA_KEYWORDS, "javascript": _JS_KEYWORDS}
_ALL_KEYWORDS = _PY_KEYWORDS | _JAVA_KEYWORDS | _JS_KEYWORDS

# ── scanner: comments / strings / code ──────────────────────────────────────
# One left-to-right regex pass so that comment markers inside strings are not
# comments and operators are not comment markers. The old code ran three
# language-blind regexes: in Python `a // b` (floor division) deleted the rest of
# the line, `"http://x"` was cut at the colon, and in Java/JS `#` removed text.

_PFX = r"(?i:[rbuf]{1,2})?"
_PY_STRING = (
    rf'{_PFX}(?:"""[\s\S]*?(?:"""|\Z)|\'\'\'[\s\S]*?(?:\'\'\'|\Z)'
    rf"|\"(?:\\.|[^\"\\\n])*\"?|'(?:\\.|[^'\\\n])*'?)"
)
_C_STRING = r'"(?:\\.|[^"\\\n])*"?|\'(?:\\.|[^\'\\\n])*\'?|`(?:\\.|[^`\\])*`?'
_BLOCK = r"/\*[\s\S]*?(?:\*/|\Z)"
_SCANNERS = {
    "python": re.compile(rf"(?P<comment>#[^\n]*)|(?P<string>{_PY_STRING})"),
    "clike": re.compile(rf"(?P<comment>//[^\n]*|{_BLOCK})|(?P<string>{_C_STRING})"),
    # unknown language: every comment style and both string syntaxes
    "any": re.compile(
        rf"(?P<comment>#[^\n]*|//[^\n]*|{_BLOCK})|(?P<string>{_PY_STRING}|`(?:\\.|[^`\\])*`?)"
    ),
}


def _family(language: str) -> str:
    lang = normalize_language(language)
    if lang == "python":
        return "python"
    return "clike" if lang in _CLIKE else "any"


def _plain_string_end(code: str, i: int) -> int:
    """End index of the plain string literal whose opening quote is at ``i``."""
    quote = code[i]
    triple = code.startswith(quote * 3, i)
    qlen = 3 if triple else 1
    i += qlen
    n = len(code)
    while i < n:
        c = code[i]
        if c == "\\":
            i += 2
        elif code.startswith(quote * qlen, i):
            return i + qlen
        elif c == "\n" and not triple:
            return i
        else:
            i += 1
    return n


def _fstring_end(code: str, start: int) -> int:
    """End index of the f-string literal starting at ``start`` (at its prefix).

    Tracks ``{...}`` replacement fields and nested strings, so the PEP 701
    (Python 3.12) form ``f"{d["k"]}"`` - the same quote inside the field - ends
    in the right place. A regex cannot do this.
    """
    n = len(code)
    i = start
    while i < n and code[i] in "rRbBuUfF":
        i += 1
    quote = code[i]
    triple = code.startswith(quote * 3, i)
    qlen = 3 if triple else 1
    closing = quote * qlen
    i += qlen
    depth = 0
    while i < n:
        c = code[i]
        if depth == 0:
            if c == "\\":
                i += 2
            elif code.startswith(closing, i):
                return i + qlen
            elif c == "\n" and not triple:
                return i
            elif c == "{":
                if code.startswith("{{", i):  # escaped brace
                    i += 2
                else:
                    depth = 1
                    i += 1
            else:
                i += 1
        else:
            if c in "([{":
                depth += 1
                i += 1
            elif c in ")]}":
                depth -= 1
                i += 1
            elif c in "\"'":
                j = i
                while j > start and code[j - 1] in "rRbBuUfF":
                    j -= 1
                prefix = code[j:i]
                i = (
                    _fstring_end(code, j)
                    if "f" in prefix.lower()
                    else _plain_string_end(code, i)
                )
            elif c == "\n" and not triple:
                return i
            else:
                i += 1
    return n


def _segments(code: str, language: str) -> list[tuple[str, str]]:
    """Split ``code`` into ("code" | "string" | "comment", text) segments."""
    family = _family(language)
    scanner = _SCANNERS[family]
    out: list[tuple[str, str]] = []
    pos = 0  # start of text not yet emitted
    cursor = 0  # where the next search starts
    while True:
        m = scanner.search(code, cursor)
        if m is None:
            break
        end = m.end()
        kind = m.lastgroup or "code"
        if family == "python" and kind == "string":
            prefix = re.match(r"[rbuf]*", m.group(), re.IGNORECASE).group()  # type: ignore[union-attr]
            if "f" in prefix.lower():
                end = _fstring_end(code, m.start())
        if m.start() > pos:
            out.append(("code", code[pos : m.start()]))
        out.append((kind, code[m.start() : end]))
        pos = cursor = end
    if pos < len(code):
        out.append(("code", code[pos:]))
    return out


_NUMBER = r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.[\d_]*)?(?:[eE][+-]?[\d_]+)?[jJ]?|\.\d[\d_]*"
_COMMON_TOKEN = rf"(?P<number>{_NUMBER})" r"|(?P<ident>(?:[^\W\d]|\$)[\w$]*)"
# Operators differ by language: Python has no `++`/`--`/`&&` (so `a - -n` must be two
# minus tokens) but has `@=`, `//`, `:=`.
_OPERATORS = {
    "python": r"\*\*=?|//=?|<<=?|>>=?|\.\.\.|->|:=|[-+*/%&|^<>=!@]=|\S",
    "other": (
        r">>>=|<<=|>>=|>>>|===|!==|\*\*=?|//=?|<<|>>|\.\.\.|->|=>|:=|\+\+|--|&&|\|\|"
        r"|\?\?|[-+*/%&|^<>=!]=|\S"
    ),
}
_TOKEN_RES = {
    family: re.compile(f"{_COMMON_TOKEN}|(?P<op>{ops})")
    for family, ops in _OPERATORS.items()
}

_LINE_CONTINUATION = re.compile(r"\\\r?\n")


def _merge_code(segments: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Join adjacent "code" segments (e.g. around a removed comment)."""
    merged: list[tuple[str, str]] = []
    for kind, text in segments:
        if kind == "code" and merged and merged[-1][0] == "code":
            merged[-1] = ("code", merged[-1][1] + text)
        else:
            merged.append((kind, text))
    return merged


def _tokenize(segments: list[tuple[str, str]], language: str) -> list[tuple[str, str]]:
    """(kind, text) tokens; strings are single tokens, comments are skipped."""
    tokens: list[tuple[str, str]] = []
    token_re = _TOKEN_RES[
        "python" if normalize_language(language) == "python" else "other"
    ]
    for kind, text in segments:
        if kind == "comment":
            continue
        if kind == "string":
            tokens.append(("string", text))
            continue
        text = _LINE_CONTINUATION.sub(
            " ", text
        )  # `\` + newline is whitespace, not a token
        tokens.extend((m.lastgroup or "op", m.group()) for m in token_re.finditer(text))
    return tokens


def _normalized_tokens(tokens: list[tuple[str, str]], language: str) -> list[str]:
    """Rename/literal-insensitive token stream: identifiers -> ID, numbers -> NUM,
    strings -> STR; keywords and operators kept."""
    keywords = _KEYWORDS.get(normalize_language(language), _ALL_KEYWORDS)
    out = []
    for kind, text in tokens:
        if kind == "string":
            out.append("STR")
        elif kind == "number":
            out.append("NUM")
        elif kind == "ident":
            out.append(text if text in keywords else "ID")
        else:
            out.append(text)
    return out


@dataclass
class CodeProcessingResult:
    """Result of processing a single source snippet.

    ``processed_code``/``lines`` keep their historical flat form (indentation
    removed). The two extra fields keep information the flat form loses:

    * ``structured_code`` - like ``processed_code`` but with Python block
      structure (indentation depth) preserved; used for fingerprints.
    * ``normalized_tokens`` - identifiers/numbers/strings replaced by ID/NUM/STR.
    """

    original_code: str
    processed_code: str
    tokens: list[str]
    lines: list[str]
    language: str
    processing_time: float
    structured_code: str = ""
    normalized_tokens: list[str] = field(default_factory=list)


class CodeProcessor:
    """Normalize and tokenize source code for lightweight analysis.

    Known limitation: JavaScript regex literals containing quotes
    (``/"/g``) are mistaken for string starts.
    """

    def process(
        self,
        code: str,
        language: str,
        *,
        remove_comments: bool = True,
        normalize_whitespace: bool = True,
    ) -> CodeProcessingResult:
        start = time.perf_counter()
        segments = _segments(code.lstrip("\ufeff"), language)

        if remove_comments:
            segments = self._remove_comment_segments(segments)

        if normalize_whitespace:
            entries = self._normalize_segments(
                segments, normalize_language(language) == "python"
            )
            lines_flat = [text for text, _ in entries]
            processed = "\n".join(lines_flat)
            structured = "\n".join("\t" * depth + text for text, depth in entries)
        else:
            processed = "".join(text for _, text in segments)
            structured = processed

        tokens = _tokenize(segments, language)
        return CodeProcessingResult(
            original_code=code,
            processed_code=processed,
            tokens=[text for _, text in tokens],
            lines=processed.splitlines(),
            language=language,
            processing_time=time.perf_counter() - start,
            structured_code=structured,
            normalized_tokens=_normalized_tokens(tokens, language),
        )

    def process_batch(
        self,
        submissions: dict[str, str],
        *,
        language: str | None = None,
    ) -> dict[str, CodeProcessingResult]:
        """Process many snippets. ``language=None`` (default) detects it from
        each key's file extension (falling back to Python); pass a language to
        force one for all."""
        return {
            submission_id: self.process(
                code, language or detect_language(str(submission_id))
            )
            for submission_id, code in submissions.items()
        }

    @staticmethod
    def _remove_comment_segments(
        segments: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for kind, text in segments:
            if kind != "comment":
                out.append((kind, text))
            elif "\n" in text:  # block comment: keep line count stable
                out.append(("code", "\n" * text.count("\n")))
            elif text.startswith("/*"):  # `a/*x*/b` must not become `ab`
                out.append(("code", " "))
        return out

    @staticmethod
    def _normalize_segments(
        segments: list[tuple[str, str]], python: bool
    ) -> list[tuple[str, int]]:
        """Collapse whitespace *outside strings*; drop blank lines; for Python
        also return each line's block depth.

        The old line-based version also collapsed whitespace inside string
        literals (``"a    b"`` -> ``"a b"``), broke multi-line strings, and
        discarded Python indentation, so ``for..: a`` followed by dedented ``b``
        looked identical to ``b`` inside the loop.

        Lines that continue an open bracket or a backslash do not take part in
        indentation tracking (their indentation is cosmetic).
        """
        segments = _merge_code(segments)
        entries: list[tuple[str, int]] = []
        parts: list[str] = []
        indent_stack = [0]
        lead = 0
        continuation = False
        bracket_depth = 0
        backslash = False
        at_line_start = True

        def flush() -> None:
            text = "".join(parts).strip()
            parts.clear()
            if not text:
                return
            depth = 0
            if python and not continuation:
                if lead > indent_stack[-1]:
                    indent_stack.append(lead)
                else:
                    while lead < indent_stack[-1]:
                        indent_stack.pop()
                depth = len(indent_stack) - 1
            entries.append((text, depth))

        for kind, text in segments:
            if kind == "string":
                if at_line_start:  # file/line begins with a literal
                    lead, continuation, at_line_start = (
                        0,
                        bracket_depth > 0 or backslash,
                        False,
                    )
                parts.append(text)
                backslash = False
                continue
            pieces = text.split("\n")
            for i, piece in enumerate(pieces):
                if i > 0:
                    flush()
                    at_line_start = True
                if at_line_start:
                    indent = piece[: len(piece) - len(piece.lstrip())]
                    lead = len(indent.expandtabs(8))
                    continuation = bracket_depth > 0 or backslash
                    at_line_start = False
                if kind == "code":
                    for ch in piece:
                        if ch in "([{":
                            bracket_depth += 1
                        elif ch in ")]}":
                            bracket_depth = max(0, bracket_depth - 1)
                    if piece.strip():
                        backslash = piece.rstrip().endswith("\\")
                parts.append(re.sub(r"\s+", " ", piece))
        flush()
        return entries

    # kept for callers/tests that used the old helpers directly
    @staticmethod
    def _remove_comments(code: str, language: str = "python") -> str:
        segments = CodeProcessor._remove_comment_segments(_segments(code, language))
        return "".join(text for _, text in segments)

    @staticmethod
    def _normalize_whitespace(code: str, language: str = "python") -> str:
        entries = CodeProcessor._normalize_segments(
            _segments(code, language), normalize_language(language) == "python"
        )
        return "\n".join(text for text, _ in entries)


def process_code(
    code: str,
    language: str,
    *,
    remove_comments: bool = True,
    normalize_whitespace: bool = True,
) -> CodeProcessingResult:
    """Process a single snippet with default settings."""
    return CodeProcessor().process(
        code,
        language,
        remove_comments=remove_comments,
        normalize_whitespace=normalize_whitespace,
    )
