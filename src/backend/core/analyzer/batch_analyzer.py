"""Batch analyzer compatibility layer."""

from __future__ import annotations

import csv
import html
import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .code_analyzer import (
    CodeAnalysisResult,
    CodeAnalyzer,
    CodeComparisonResult,
    detect_language,
)

SUPPORTED_EXPORT_FORMATS = ("json", "csv", "html")
DEFAULT_MAX_FILE_BYTES = 5_000_000


@dataclass
class BatchAnalysisResult:
    """Summary of a batch similarity run."""

    total_submissions: int
    total_comparisons: int
    analysis_results: dict[str, CodeAnalysisResult]
    comparison_results: list[CodeComparisonResult]
    execution_time: float
    summary: dict[str, object]
    # Files analyze_directory refused to read, mapped to the reason.
    skipped_files: dict[str, str] = field(default_factory=dict)


class BatchAnalyzer:
    """Analyze many submissions with the legacy API shape."""

    def __init__(self, analyzer: CodeAnalyzer | None = None):
        self.analyzer = analyzer or CodeAnalyzer()

    def analyze_submissions(self, submissions: dict[str, str]) -> BatchAnalysisResult:
        start = time.perf_counter()
        # Same detector as analyze_pairwise: before, per-file results used an
        # extension-only guess (default "python") while comparisons sniffed content,
        # so one file could have two different languages in the same report.
        analysis_results = {
            filename: self.analyzer.analyze_code(
                code, detect_language(filename, code), filename
            )
            for filename, code in submissions.items()
        }
        comparison_results = self.analyzer.analyze_pairwise(submissions)
        execution_time = time.perf_counter() - start

        suspicious_pair_count = sum(1 for r in comparison_results if r.is_suspicious)
        average_similarity = (
            sum(r.overall_score for r in comparison_results) / len(comparison_results)
            if comparison_results
            else 0.0
        )

        language_distribution: dict[str, int] = {}
        for result in analysis_results.values():
            language_distribution[result.language] = (
                language_distribution.get(result.language, 0) + 1
            )

        return BatchAnalysisResult(
            total_submissions=len(submissions),
            total_comparisons=len(comparison_results),
            analysis_results=analysis_results,
            comparison_results=comparison_results,
            execution_time=execution_time,
            summary={
                "language_distribution": language_distribution,
                "average_similarity": average_similarity,
                "suspicious_pair_count": suspicious_pair_count,
            },
        )

    def analyze_directory(
        self,
        directory: str,
        pattern: str = "*",
        *,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> BatchAnalysisResult:
        """Analyze files under ``directory`` matching ``pattern``.

        Submissions are keyed by path relative to ``directory`` (so ``**/*.py``
        no longer silently overwrites same-named files in different folders).
        Binary, non-UTF-8, oversized, or out-of-tree (symlink) files are skipped
        and reported in ``result.skipped_files`` instead of aborting the batch.

        Raises:
            NotADirectoryError: If ``directory`` is not a directory (an empty
                result for a typo'd path hid mistakes).
            ValueError: If ``pattern`` is absolute.
        """
        root = Path(directory).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        try:
            candidates = sorted(root.glob(pattern))
        except NotImplementedError as e:
            raise ValueError(f"Pattern must be relative: {pattern!r}") from e

        submissions: dict[str, str] = {}
        skipped: dict[str, str] = {}
        for file_path in candidates:
            if not file_path.is_file():
                continue
            key = file_path.relative_to(root).as_posix()
            try:
                resolved = file_path.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    skipped[key] = "resolves outside the directory"
                    continue
                if resolved.stat().st_size > max_file_bytes:
                    skipped[key] = f"larger than {max_file_bytes} bytes"
                    continue
                raw = resolved.read_bytes()
                if b"\x00" in raw[:8192]:
                    skipped[key] = "binary file"
                    continue
                submissions[key] = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                skipped[key] = "not valid UTF-8"
            except OSError as e:
                skipped[key] = f"unreadable: {e.strerror or e}"

        result = self.analyze_submissions(submissions)
        result.skipped_files = skipped
        return result

    def export_results(
        self,
        result: BatchAnalysisResult,
        output_dir: str,
        formats: Iterable[str] | str | None = None,
    ) -> dict[str, str]:
        # A bare string used to be iterated per character ("csv" -> c, s, v) and
        # exported nothing; unknown formats were silently ignored.
        if formats is None:
            requested = ["json"]
        elif isinstance(formats, str):
            requested = [formats.lower()]
        else:
            requested = [f.lower() for f in formats] or ["json"]
        unknown = sorted(set(requested) - set(SUPPORTED_EXPORT_FORMATS))
        if unknown:
            raise ValueError(
                f"Unsupported export format(s) {unknown}; "
                f"choose from {list(SUPPORTED_EXPORT_FORMATS)}"
            )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        exported: dict[str, str] = {}

        if "json" in requested:
            json_path = output_path / "batch_analysis.json"
            payload = {
                "total_submissions": result.total_submissions,
                "total_comparisons": result.total_comparisons,
                "execution_time": result.execution_time,
                "summary": result.summary,
                "skipped_files": result.skipped_files,
                "analysis_results": {
                    name: asdict(data) for name, data in result.analysis_results.items()
                },
                "comparison_results": [
                    asdict(data) for data in result.comparison_results
                ],
            }
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            exported["json"] = str(json_path)

        if "csv" in requested:
            csv_path = output_path / "batch_analysis.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["file_a", "file_b", "overall_score", "is_suspicious"],
                )
                writer.writeheader()
                for comparison in result.comparison_results:
                    writer.writerow(
                        {
                            "file_a": _csv_safe(comparison.file_a),
                            "file_b": _csv_safe(comparison.file_b),
                            "overall_score": f"{comparison.overall_score:.6f}",
                            "is_suspicious": comparison.is_suspicious,
                        }
                    )
            exported["csv"] = str(csv_path)

        if "html" in requested:
            html_path = output_path / "batch_analysis.html"
            # Filenames are attacker-controlled (student uploads): escape them.
            rows = "\n".join(
                f"<tr><td>{html.escape(c.file_a)}</td><td>{html.escape(c.file_b)}</td>"
                f"<td>{c.overall_score:.3f}</td><td>{c.is_suspicious}</td></tr>"
                for c in result.comparison_results
            )
            html_path.write_text(
                (
                    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    "<title>Batch Analysis</title></head>"
                    "<body><h1>Batch Analysis</h1>"
                    f"<p>Submissions: {result.total_submissions}</p>"
                    f"<p>Comparisons: {result.total_comparisons}</p>"
                    "<table border='1'><thead><tr><th>File A</th><th>File B</th>"
                    "<th>Score</th><th>Suspicious</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table></body></html>"
                ),
                encoding="utf-8",
            )
            exported["html"] = str(html_path)

        return exported


def analyze_batch(
    submissions: dict[str, str],
    analyzer: CodeAnalyzer | None = None,
) -> BatchAnalysisResult:
    """Analyze a submission mapping with default configuration."""
    return BatchAnalyzer(analyzer=analyzer).analyze_submissions(submissions)


def _csv_safe(value: str) -> str:
    """Neutralise spreadsheet formula injection (=, +, -, @, tab, CR prefixes)."""
    return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value
