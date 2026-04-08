"""Legacy code pre-processing helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Dict, List, Optional


@dataclass
class CodeProcessingResult:
    """Result of processing a single source snippet."""

    original_code: str
    processed_code: str
    tokens: List[str]
    lines: List[str]
    language: str
    processing_time: float


class CodeProcessor:
    """Normalize and tokenize source code for lightweight analysis."""

    def process(
        self,
        code: str,
        language: str,
        *,
        remove_comments: bool = True,
        normalize_whitespace: bool = True,
    ) -> CodeProcessingResult:
        start = time.perf_counter()
        processed = code
        if remove_comments:
            processed = self._remove_comments(processed)
        if normalize_whitespace:
            processed = self._normalize_whitespace(processed)

        tokens = re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|[^\s]", processed)
        lines = processed.splitlines()
        return CodeProcessingResult(
            original_code=code,
            processed_code=processed,
            tokens=tokens,
            lines=lines,
            language=language,
            processing_time=time.perf_counter() - start,
        )

    def process_batch(
        self,
        submissions: Dict[str, str],
        *,
        language: str = "python",
    ) -> Dict[str, CodeProcessingResult]:
        return {
            submission_id: self.process(code, language)
            for submission_id, code in submissions.items()
        }

    @staticmethod
    def _remove_comments(code: str) -> str:
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
        code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
        return code

    @staticmethod
    def _normalize_whitespace(code: str) -> str:
        normalized_lines = []
        for line in code.splitlines():
            stripped = re.sub(r"\s+", " ", line).strip()
            if stripped:
                normalized_lines.append(stripped)
        return "\n".join(normalized_lines)


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
