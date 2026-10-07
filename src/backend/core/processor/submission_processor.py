"""Legacy submission processing helpers."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .code_processor import (
    CodeProcessingResult,
    CodeProcessor,
    detect_language,
    normalize_language,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_FILE_BYTES = 5_000_000


@dataclass
class SubmissionProcessingResult:
    """Processed submission payload.

    ``fingerprint`` identifies formatting-level duplicates (same language, same
    code after comment/whitespace normalization, same block structure).
    ``token_fingerprint`` additionally ignores identifier names and literal
    values, so it also matches copies that only renamed variables.
    """

    submission_id: str
    file_path: str
    language: str
    fingerprint: str
    processing_time: float
    metadata: dict[str, str]
    processing_result: CodeProcessingResult
    token_fingerprint: str = ""


def _digest(language: str, text: str) -> str:
    # The language is part of the hash: `x = 1` in Python and JavaScript are not
    # duplicates. surrogatepass: undecodable input must not crash hashing.
    payload = f"{normalize_language(language)}\x00{text}"
    return sha256(payload.encode("utf-8", errors="surrogatepass")).hexdigest()


def _to_text(value: object) -> str:
    """Payload -> str (``str(None)`` gave "None" and ``str(b"x")`` gave "b'x'")."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8-sig", errors="replace")
    return value if isinstance(value, str) else str(value)


class SubmissionProcessor:
    """Prepare submission records for downstream analysis.

    After ``process_directory``, ``skipped_files`` maps each file that was not
    processed to the reason (binary, too large, not UTF-8, unreadable, ...).
    """

    def __init__(
        self,
        code_processor: CodeProcessor | None = None,
        *,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ):
        self.code_processor = code_processor or CodeProcessor()
        self.max_file_bytes = max_file_bytes
        self.skipped_files: dict[str, str] = {}

    def process_submission(
        self,
        submission_id: str,
        file_path: str,
        code: str,
        language: str,
    ) -> SubmissionProcessingResult:
        start = time.perf_counter()
        processing_result = self.code_processor.process(code, language)
        # structured_code keeps Python block structure; the flat processed_code
        # made `for..: a` + dedented `b` identical to `b` inside the loop.
        structure = (
            processing_result.structured_code or processing_result.processed_code
        )
        return SubmissionProcessingResult(
            submission_id=submission_id,
            file_path=file_path,
            language=language,
            fingerprint=_digest(language, structure),
            processing_time=time.perf_counter() - start,
            metadata={
                "submission_id": submission_id,
                "file_path": file_path,
                "language": language,
            },
            processing_result=processing_result,
            token_fingerprint=_digest(
                language, " ".join(processing_result.normalized_tokens)
            ),
        )

    def process_submissions(
        self,
        submissions: Mapping[str, object],
    ) -> dict[str, SubmissionProcessingResult]:
        """Process ``{id: code | bytes | {"code", "file_path", "language"}}``.

        Raises:
            ValueError: If two keys stringify to the same id (one would silently
                overwrite the other).
        """
        results: dict[str, SubmissionProcessingResult] = {}
        for submission_id, payload in submissions.items():
            sid = str(submission_id)
            if sid in results:
                raise ValueError(f"Duplicate submission id after str(): {sid!r}")

            if isinstance(payload, Mapping):
                file_path = _to_text(payload.get("file_path")) or sid
                code = _to_text(payload.get("code"))
                language = _to_text(payload.get("language")) or detect_language(
                    file_path
                )
            else:
                file_path = sid
                code = _to_text(payload)
                language = detect_language(file_path)

            results[sid] = self.process_submission(sid, file_path, code, language)
        return results

    def process_directory(
        self, directory: str, pattern: str = "*"
    ) -> dict[str, SubmissionProcessingResult]:
        """Process files under ``directory`` matching ``pattern``.

        Keys/``file_path`` are paths relative to ``directory`` (so ``**/*.py``
        no longer lets ``sub/a.py`` silently replace ``a.py``). Binary,
        non-UTF-8, oversized, unreadable and out-of-tree (symlink) files are
        skipped and listed in ``skipped_files`` instead of aborting the run.

        Raises:
            NotADirectoryError: If ``directory`` is not a directory.
            ValueError: If ``pattern`` is absolute.
        """
        root = Path(directory).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        try:
            candidates = sorted(root.glob(pattern))
        except NotImplementedError as e:
            raise ValueError(f"Pattern must be relative: {pattern!r}") from e

        self.skipped_files = {}
        submissions: dict[str, object] = {}
        for file_path in candidates:
            if not file_path.is_file():
                continue
            key = file_path.relative_to(root).as_posix()
            try:
                resolved = file_path.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    self.skipped_files[key] = "resolves outside the directory"
                    continue
                if resolved.stat().st_size > self.max_file_bytes:
                    self.skipped_files[key] = f"larger than {self.max_file_bytes} bytes"
                    continue
                raw = resolved.read_bytes()
                if b"\x00" in raw[:8192]:
                    self.skipped_files[key] = "binary file"
                    continue
                code = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                self.skipped_files[key] = "not valid UTF-8"
                continue
            except OSError as e:
                self.skipped_files[key] = f"unreadable: {e.strerror or e}"
                continue
            submissions[key] = {
                "file_path": key,
                "code": code,
                "language": detect_language(key),
            }

        for key, reason in self.skipped_files.items():
            logger.warning("Skipped %s: %s", key, reason)
        return self.process_submissions(submissions)

    def compare_fingerprints(
        self,
        results: Mapping[str, SubmissionProcessingResult],
        *,
        normalized: bool = False,
    ) -> list[dict[str, object]]:
        """Group submissions with identical fingerprints.

        Args:
            results: Output of ``process_submissions``.
            normalized: Group by ``token_fingerprint`` (ignores identifier names
                and literal values) instead of the exact ``fingerprint``.

        Submissions with no code tokens (empty / comment-only files) are
        ignored: they used to be reported as duplicates of each other.
        """
        groups: dict[str, list[str]] = {}
        for submission_id, result in results.items():
            if not result.processing_result.tokens:
                continue
            key = result.token_fingerprint if normalized else result.fingerprint
            groups.setdefault(key, []).append(submission_id)

        duplicates: list[dict[str, object]] = [
            {
                "fingerprint": fingerprint,
                "submission_ids": sorted(ids),
                "count": len(ids),
            }
            for fingerprint, ids in groups.items()
            if len(ids) > 1
        ]
        # deterministic: largest group first, ties by first id
        return sorted(duplicates, key=lambda g: (-int(g["count"]), g["submission_ids"][0]))  # type: ignore[index]


def process_submission(
    submission_id: str,
    file_path: str,
    code: str,
    language: str,
) -> SubmissionProcessingResult:
    """Process one submission using default settings."""
    return SubmissionProcessor().process_submission(
        submission_id, file_path, code, language
    )


_detect_language = detect_language  # backwards-compatible private alias
