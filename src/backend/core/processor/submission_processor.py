"""Legacy submission processing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import time
from typing import Dict, Iterable, Mapping

from src.backend.core.processor.code_processor import CodeProcessingResult, CodeProcessor


@dataclass
class SubmissionProcessingResult:
    """Processed submission payload."""

    submission_id: str
    file_path: str
    language: str
    fingerprint: str
    processing_time: float
    metadata: Dict[str, str]
    processing_result: CodeProcessingResult


class SubmissionProcessor:
    """Prepare submission records for downstream analysis."""

    def __init__(self, code_processor: CodeProcessor | None = None):
        self.code_processor = code_processor or CodeProcessor()

    def process_submission(
        self,
        submission_id: str,
        file_path: str,
        code: str,
        language: str,
    ) -> SubmissionProcessingResult:
        start = time.perf_counter()
        processing_result = self.code_processor.process(code, language)
        fingerprint = sha256(processing_result.processed_code.encode("utf-8")).hexdigest()
        return SubmissionProcessingResult(
            submission_id=submission_id,
            file_path=file_path,
            language=language,
            fingerprint=fingerprint,
            processing_time=time.perf_counter() - start,
            metadata={
                "submission_id": submission_id,
                "file_path": file_path,
                "language": language,
            },
            processing_result=processing_result,
        )

    def process_submissions(
        self,
        submissions: Mapping[str, object],
    ) -> Dict[str, SubmissionProcessingResult]:
        results: Dict[str, SubmissionProcessingResult] = {}
        for submission_id, payload in submissions.items():
            if isinstance(payload, dict):
                file_path = str(payload.get("file_path", submission_id))
                code = str(payload.get("code", ""))
                language = str(payload.get("language", _detect_language(file_path)))
            else:
                file_path = str(submission_id)
                code = str(payload)
                language = _detect_language(file_path)

            results[str(submission_id)] = self.process_submission(
                str(submission_id),
                file_path,
                code,
                language,
            )
        return results

    def process_directory(self, directory: str, pattern: str = "*") -> Dict[str, SubmissionProcessingResult]:
        path = Path(directory)
        submissions = {
            file_path.name: {
                "file_path": file_path.name,
                "code": file_path.read_text(encoding="utf-8"),
                "language": _detect_language(file_path.name),
            }
            for file_path in sorted(path.glob(pattern))
            if file_path.is_file()
        }
        return self.process_submissions(submissions)

    def compare_fingerprints(
        self,
        results: Mapping[str, SubmissionProcessingResult],
    ) -> list[Dict[str, object]]:
        groups: Dict[str, list[str]] = {}
        for submission_id, result in results.items():
            groups.setdefault(result.fingerprint, []).append(submission_id)

        duplicates = []
        for fingerprint, submission_ids in groups.items():
            if len(submission_ids) > 1:
                duplicates.append(
                    {
                        "fingerprint": fingerprint,
                        "submission_ids": sorted(submission_ids),
                        "count": len(submission_ids),
                    }
                )
        return sorted(duplicates, key=lambda group: group["count"], reverse=True)


def process_submission(
    submission_id: str,
    file_path: str,
    code: str,
    language: str,
) -> SubmissionProcessingResult:
    """Process one submission using default settings."""
    return SubmissionProcessor().process_submission(submission_id, file_path, code, language)


def _detect_language(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".java":
        return "java"
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return "javascript"
    return "python"
