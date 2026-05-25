"""Canonical JPlag benchmark adapter backed by the bundled JPlag jar."""

from __future__ import annotations

import csv
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.backend.benchmark.adapters.base_adapter import BaseAdapter
from src.backend.benchmark.contracts.evaluation_result import (
    EnrichedPair,
    EvaluationResult,
)


class JPlagAdapter(BaseAdapter):
    """Run JPlag once per language group and map CSV scores back to pairs."""

    TOOL_DIR = Path(__file__).resolve().parents[4] / "tools" / "external" / "JPlag"
    LANGUAGE_MAP = {
        "python": "python3",
        "javascript": "javascript",
        "typescript": "typescript",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "csharp": "csharp",
        "go": "go",
        "rust": "rust",
        "kotlin": "kotlin",
        "swift": "swift",
    }

    def __init__(self, min_tokens: int = 3, threshold: float = 0.5) -> None:
        self._min_tokens = min_tokens
        self._threshold = threshold

    @property
    def name(self) -> str:
        """Return the adapter name."""
        return "jplag"

    @property
    def version(self) -> str:
        """Return the adapter version."""
        return "real-jplag-cli"

    def is_available(self) -> bool:
        """Return whether the bundled JPlag jar is available."""
        return self._find_jar() is not None

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate one pair through the same batch runner used by dashboards."""
        language = getattr(pair, "language", None) or "python"
        extension = self._extension_for_language(str(language))
        file_a = f"a{extension}"
        file_b = f"b{extension}"
        metadata: Dict[str, Any] = {
            "language": language,
            "min_tokens": self._min_tokens,
            "real_jplag": True,
        }
        payload = self.run_batch(
            {file_a: pair.code_a, file_b: pair.code_b}, [(file_a, file_b)]
        )
        score = payload["pairs"][0]["score"] if payload.get("pairs") else 0.0
        return self._make_result(pair, score, self._threshold, metadata=metadata)

    def run_batch(
        self,
        submissions: Dict[str, str],
        pairs: Iterable[tuple[str, str]],
        progress_cb=None,
    ) -> Dict[str, Any]:
        """Run JPlag for all submissions and return requested pair scores."""
        jar_path = self._find_jar()
        if not jar_path:
            return {"pairs": []}

        groups: Dict[str, Dict[str, str]] = {}
        score_by_pair: Dict[str, float] = {}
        for filename, content in submissions.items():
            groups.setdefault(self._infer_language_from_filename(filename), {})[
                filename
            ] = content

        for language, language_submissions in groups.items():
            if len(language_submissions) < 2:
                continue
            jplag_language = self.LANGUAGE_MAP.get(language)
            if not jplag_language:
                continue
            group_scores = self._run_group(
                jar_path, jplag_language, language_submissions, progress_cb
            )
            score_by_pair.update(group_scores)

        return {
            "pairs": [
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "score": score_by_pair.get(self._pair_key(file_a, file_b), 0.0),
                }
                for file_a, file_b in pairs
            ]
        }

    def _run_group(
        self,
        jar_path: Path,
        jplag_language: str,
        submissions: Dict[str, str],
        progress_cb=None,
        allow_text_fallback: bool = True,
    ) -> Dict[str, float]:
        """Run one JPlag language group."""
        with tempfile.TemporaryDirectory(prefix="jplag-adapter-") as temp_dir:
            source_root = Path(temp_dir) / "subs"
            result_root = Path(temp_dir) / "results"
            source_root.mkdir(parents=True, exist_ok=True)
            submission_map = self._write_submission_dirs(source_root, submissions)
            suffixes = self._suffixes_for_submissions(submissions)
            suffix_args = ["-p", suffixes] if suffixes else []

            # Use Popen to stream output line-by-line
            proc = subprocess.Popen(
                [
                    "java",
                    "-jar",
                    str(jar_path),
                    "-l",
                    jplag_language,
                    "-t",
                    str(self._min_tokens),
                    "--csv-export",
                    "--overwrite",
                    "--cluster-skip",
                    *suffix_args,
                    "-M",
                    "RUN",
                    "-r",
                    str(result_root),
                    str(source_root),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            output_lines: list[str] = []

            # Stream output lines to progress callback
            if proc.stdout:
                for line in proc.stdout:
                    cleaned_line = self._clean_output_line(line)
                    if cleaned_line:
                        output_lines.append(cleaned_line)
                        if progress_cb:
                            progress_cb(cleaned_line)
            else:
                # Fallback: wait without streaming
                proc.wait()

            proc.wait()
            csv_path = result_root / "results.csv"
            if proc.returncode != 0:
                if csv_path.exists():
                    return self._parse_results_csv(csv_path, submission_map)
                if self._is_recoverable_submission_failure(output_lines):
                    if allow_text_fallback and jplag_language != "text":
                        return self._run_group(
                            jar_path,
                            "text",
                            submissions,
                            progress_cb,
                            allow_text_fallback=False,
                        )
                    return {}
                detail = self._format_failure_output(output_lines)
                raise RuntimeError(
                    f"JPlag exited with code {proc.returncode}: {detail}"
                )

            return self._parse_results_csv(csv_path, submission_map)

    def _clean_output_line(self, line: str) -> str:
        """Strip terminal control characters from JPlag progress output."""
        cleaned = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
        cleaned = cleaned.replace("\r", "\n")
        parts = [part.strip() for part in cleaned.splitlines() if part.strip()]
        return " | ".join(parts)

    def _format_failure_output(self, output_lines: list[str]) -> str:
        """Build a concise JPlag failure detail from captured output lines."""
        unique_lines = list(dict.fromkeys(output_lines))
        if not unique_lines:
            return "no output captured"
        return " | ".join(unique_lines[-8:])

    def _is_recoverable_submission_failure(self, output_lines: list[str]) -> bool:
        """Return whether JPlag failed only because it removed bad submissions."""
        output = "\n".join(output_lines).lower()
        return (
            "submissionset" in output and "submission" in output and "removed" in output
        )

    def _suffixes_for_submissions(self, submissions: Dict[str, str]) -> str:
        """Return JPlag suffix filters for the submitted filenames."""
        suffixes = sorted(
            {
                Path(filename).suffix.lower().lstrip(".")
                for filename in submissions
                if Path(filename).suffix
            }
        )
        return ",".join(suffixes)

    def _parse_results_csv(
        self, csv_path: Path, submission_map: Dict[str, Dict[str, str]]
    ) -> Dict[str, float]:
        """Parse JPlag results.csv into pair scores."""
        scores: Dict[str, float] = {}
        if not csv_path.exists():
            return scores
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                left_submission = row.get("submissionName1")
                right_submission = row.get("submissionName2")
                if (
                    left_submission not in submission_map
                    or right_submission not in submission_map
                ):
                    continue
                try:
                    similarity = float(row.get("averageSimilarity", 0.0))
                except (TypeError, ValueError):
                    continue
                left_name = submission_map[left_submission]["filename"]
                right_name = submission_map[right_submission]["filename"]
                scores[self._pair_key(left_name, right_name)] = max(
                    0.0, min(1.0, similarity)
                )
        return scores

    def _find_jar(self) -> Optional[Path]:
        """Find the bundled JPlag jar."""
        candidates = [self.TOOL_DIR / "jplag.jar"]
        candidates.extend(sorted(self.TOOL_DIR.glob("*jar-with-dependencies.jar")))
        candidates.extend(sorted(self.TOOL_DIR.glob("*.jar")))
        return next((candidate for candidate in candidates if candidate.exists()), None)

    def _write_submission_dirs(
        self, target_dir: Path, submissions: Dict[str, str]
    ) -> Dict[str, Dict[str, str]]:
        """Write files using JPlag's submission-directory layout."""
        written: Dict[str, Dict[str, str]] = {}
        for index, (filename, content) in enumerate(sorted(submissions.items())):
            submission_id = f"sub{index:03d}"
            submission_dir = target_dir / submission_id
            submission_dir.mkdir(parents=True, exist_ok=True)
            file_path = submission_dir / Path(filename).name
            file_path.write_text(content, encoding="utf-8")
            written[submission_id] = {"filename": filename, "path": str(file_path)}
        return written

    def _infer_language_from_filename(self, filename: str) -> str:
        """Infer JPlag language from file suffix."""
        suffix = Path(filename).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rs": "rust",
            ".kt": "kotlin",
            ".swift": "swift",
        }.get(suffix, "python")

    def _extension_for_language(self, language: str) -> str:
        """Return a reasonable extension for single-pair evaluation."""
        return {
            "python": ".py",
            "java": ".java",
            "javascript": ".js",
            "typescript": ".ts",
            "c": ".c",
            "cpp": ".cpp",
            "csharp": ".cs",
        }.get(language.lower(), ".py")

    def _pair_key(self, file_a: str, file_b: str) -> str:
        """Build a stable unordered pair key."""
        return "::".join(sorted((file_a, file_b)))


def run_jplag_batch(
    submissions: Dict[str, str],
    pairs: Iterable[tuple[str, str]],
    progress_cb=None,
) -> Dict[str, Any]:
    """Run the canonical JPlag batch adapter used by benchmark APIs."""
    return JPlagAdapter().run_batch(submissions, pairs, progress_cb=progress_cb)
