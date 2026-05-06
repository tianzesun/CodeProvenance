"""Canonical PMD CPD benchmark adapter backed by the bundled PMD CLI."""

from __future__ import annotations

import csv
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.backend.benchmark.adapters.base_adapter import BaseAdapter
from src.backend.benchmark.contracts.evaluation_result import (
    EnrichedPair,
    EvaluationResult,
)


class PMDBenchmarkEngine(BaseAdapter):
    """Run PMD CPD and convert duplicate blocks into pair scores."""

    TOOL_DIR = Path(__file__).resolve().parents[4] / "tools" / "external" / "pmd"

    def __init__(self, min_tokens: int = 5, threshold: float = 0.5) -> None:
        self._min_tokens = min_tokens
        self._threshold = threshold

    @property
    def name(self) -> str:
        """Return the adapter name."""
        return "pmd"

    @property
    def version(self) -> str:
        """Return the adapter version."""
        return "real-pmd-cpd"

    def is_available(self) -> bool:
        """Return whether the PMD executable is available."""
        return self._find_executable() is not None

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate one pair through the same batch runner used by dashboards."""
        language = getattr(pair, "language", None) or "python"
        extension = self._extension_for_language(str(language))
        file_a = f"a{extension}"
        file_b = f"b{extension}"
        payload = self.run_batch(
            {file_a: pair.code_a, file_b: pair.code_b}, [(file_a, file_b)]
        )
        score = payload["pairs"][0]["score"] if payload.get("pairs") else 0.0
        return self._make_result(
            pair,
            score,
            self._threshold,
            metadata={"minimum_tokens": self._min_tokens, "real_pmd_cpd": True},
        )

    def run_batch(
        self, submissions: Dict[str, str], pairs: Iterable[tuple[str, str]]
    ) -> Dict[str, Any]:
        """Run PMD CPD for all submissions and return requested pair scores."""
        pmd_path = self._find_executable()
        if not pmd_path:
            return {"pairs": []}

        token_counts = {
            filename: max(1, len(self._tokenize_code(content)))
            for filename, content in submissions.items()
        }
        score_by_pair: Dict[str, float] = {}
        groups: Dict[str, Dict[str, str]] = {}
        for filename, content in submissions.items():
            groups.setdefault(self._infer_pmd_language_from_filename(filename), {})[
                filename
            ] = content

        for language, language_submissions in groups.items():
            if len(language_submissions) < 2:
                continue
            group_scores = self._run_group(
                pmd_path, language, language_submissions, token_counts
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

    def compare(self, code1: str, code2: str) -> float:
        """Compare two code strings using PMD CPD."""
        payload = self.run_batch({"a.py": code1, "b.py": code2}, [("a.py", "b.py")])
        return payload["pairs"][0]["score"] if payload.get("pairs") else 0.0

    def _run_group(
        self,
        pmd_path: Path,
        language: str,
        submissions: Dict[str, str],
        token_counts: Dict[str, int],
    ) -> Dict[str, float]:
        """Run PMD for one language group."""
        with tempfile.TemporaryDirectory(prefix="pmd-adapter-") as temp_dir:
            source_root = Path(temp_dir) / "subs"
            source_root.mkdir(parents=True, exist_ok=True)
            written_paths = self._write_submissions(source_root, submissions)

            result = subprocess.run(
                [
                    str(pmd_path),
                    "cpd",
                    "--language",
                    language,
                    "--minimum-tokens",
                    str(self._min_tokens),
                    "--format",
                    "csv",
                    "--no-fail-on-error",
                    "--no-fail-on-violation",
                    str(source_root),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.strip()
                    or result.stdout.strip()
                    or "PMD CPD execution failed"
                )
            return self._parse_cpd_csv(result.stdout, written_paths, token_counts)

    def _parse_cpd_csv(
        self,
        stdout: str,
        written_paths: Dict[str, str],
        token_counts: Dict[str, int],
    ) -> Dict[str, float]:
        """Parse PMD CPD CSV stdout into pair scores."""
        scores: Dict[str, float] = {}
        output_lines = [line for line in stdout.splitlines() if line.strip()]
        if len(output_lines) <= 1:
            return scores

        path_to_filename = {path: filename for filename, path in written_paths.items()}
        reader = csv.reader(output_lines)
        next(reader, None)
        for row in reader:
            if len(row) < 5:
                continue
            try:
                duplicated_tokens = int(row[1])
                occurrence_count = int(row[2])
            except (TypeError, ValueError):
                continue

            file_names: List[str] = []
            for index in range(3, min(len(row), 3 + occurrence_count * 2), 2):
                file_path = row[index + 1]
                filename = path_to_filename.get(file_path)
                if filename:
                    file_names.append(filename)

            for i in range(len(file_names)):
                for j in range(i + 1, len(file_names)):
                    file_a = file_names[i]
                    file_b = file_names[j]
                    denominator = max(
                        1, min(token_counts[file_a], token_counts[file_b])
                    )
                    score = max(0.0, min(1.0, duplicated_tokens / denominator))
                    pair_key = self._pair_key(file_a, file_b)
                    scores[pair_key] = max(scores.get(pair_key, 0.0), score)
        return scores

    def _find_executable(self) -> Optional[Path]:
        """Find the bundled PMD executable."""
        return next(
            (
                candidate
                for candidate in (self.TOOL_DIR / "bin" / "pmd", self.TOOL_DIR / "pmd")
                if candidate.exists()
            ),
            None,
        )

    def _write_submissions(
        self, target_dir: Path, submissions: Dict[str, str]
    ) -> Dict[str, str]:
        """Write submissions to a temporary directory."""
        written_paths: Dict[str, str] = {}
        for filename, content in sorted(submissions.items()):
            file_path = target_dir / Path(filename).name
            file_path.write_text(content, encoding="utf-8")
            written_paths[filename] = str(file_path)
        return written_paths

    def _infer_pmd_language_from_filename(self, filename: str) -> str:
        """Infer PMD CPD language from file suffix."""
        suffix = Path(filename).suffix.lower()
        return {
            ".py": "python",
            ".js": "ecmascript",
            ".ts": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cs": "cs",
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
            "cs": ".cs",
        }.get(language.lower(), ".py")

    def _tokenize_code(self, code: str) -> List[str]:
        """Tokenize code for PMD duplicate-token score normalization."""
        return re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|\S", code.lower())

    def _pair_key(self, file_a: str, file_b: str) -> str:
        """Build a stable unordered pair key."""
        return "::".join(sorted((file_a, file_b)))


def run_pmd_batch(
    submissions: Dict[str, str], pairs: Iterable[tuple[str, str]]
) -> Dict[str, Any]:
    """Run the canonical PMD batch adapter used by benchmark APIs."""
    return PMDBenchmarkEngine().run_batch(submissions, pairs)
