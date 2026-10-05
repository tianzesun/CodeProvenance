"""Small shared helpers for the detection layers (numbers, normalisation, tokens).

``tokens()`` reuses the similarity package's comment- and string-aware scanner when it is
importable and falls back to a minimal local scanner otherwise, so the detection package keeps
working standalone.
"""

from __future__ import annotations

import math
import re
from typing import Any

try:  # shared scanner (comments and strings handled in one pass)
    from src.backend.engines.similarity import code_scan as _code_scan
except Exception:  # noqa: BLE001
    _code_scan = None

MAX_CODE_CHARS = 2_000_000

_FALLBACK = re.compile(
    r"""(?P<comment>\#[^\n]*|//[^\n]*|/\*.*?\*/)
      |(?P<string>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
      |(?P<number>\d+(?:\.\d+)?)
      |(?P<ident>[A-Za-z_]\w*)
      |(?P<op>==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--|->|\S)""",
    re.VERBOSE | re.DOTALL,
)


def score(value: Any, default: float = 0.0) -> float:
    """A finite float clamped to [0, 1]; ``default`` for None / NaN / non-numbers.

    ``max(0.0, min(1.0, nan))`` is 1.0, so a NaN engine score used to turn into a PERFECT match.
    """
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number)) if math.isfinite(number) else default


def first_score(scores: dict[str, Any], *keys: str) -> float | None:
    """The first PRESENT, usable score among ``keys`` (aliases), else None (= unavailable)."""
    for key in keys:
        if key in scores:
            value = scores[key]
            if value is None:
                continue
            number = score(value, default=float("nan"))
            if not math.isnan(number):
                return number
    return None


def normalize_text(code: str | None) -> str:
    """Line endings unified, trailing whitespace dropped, surrounding blank space trimmed."""
    if not code:
        return ""
    text = str(code)[:MAX_CODE_CHARS].replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def tokens(code: str, language: str | None = None) -> list[tuple[str, str]]:
    """``[(kind, text)]`` for non-comment tokens; kind is string/number/ident/op."""
    code = (code or "")[:MAX_CODE_CHARS]
    if _code_scan is not None:
        try:
            return list(_code_scan.scan(code, language))
        except Exception:  # noqa: BLE001
            pass
    return [(m.lastgroup, m.group()) for m in _FALLBACK.finditer(code) if m.lastgroup != "comment"]
