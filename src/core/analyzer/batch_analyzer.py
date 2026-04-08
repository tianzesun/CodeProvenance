"""Batch analyzer compatibility layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional

from src.core.analyzer.code_analyzer import CodeAnalysisResult, CodeAnalyzer, CodeComparisonResult


@dataclass
class BatchAnalysisResult:
    """Summary of a batch similarity run."""

    total_submissions: int
    total_comparisons: int
    analysis_results: Dict[str, CodeAnalysisResult]
    comparison_results: List[CodeComparisonResult]
    execution_time: float
    summary: Dict[str, object]


class BatchAnalyzer:
    """Analyze many submissions with the legacy API shape."""

    def __init__(self, analyzer: Optional[CodeAnalyzer] = None):
        self.analyzer = analyzer or CodeAnalyzer()

    def analyze_submissions(self, submissions: Dict[str, str]) -> BatchAnalysisResult:
        start = time.perf_counter()
        analysis_results = {
            filename: self.analyzer.analyze_code(
                code,
                _detect_language_from_name(filename),
                filename,
            )
            for filename, code in submissions.items()
        }
        comparison_results = self.analyzer.analyze_pairwise(submissions)
        execution_time = time.perf_counter() - start
        suspicious_pair_count = sum(1 for result in comparison_results if result.is_suspicious)
        average_similarity = (
            sum(result.overall_score for result in comparison_results) / len(comparison_results)
            if comparison_results
            else 0.0
        )

        language_distribution: Dict[str, int] = {}
        for result in analysis_results.values():
            language_distribution[result.language] = language_distribution.get(result.language, 0) + 1

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

    def analyze_directory(self, directory: str, pattern: str = "*") -> BatchAnalysisResult:
        path = Path(directory)
        submissions = {
            file_path.name: file_path.read_text(encoding="utf-8")
            for file_path in sorted(path.glob(pattern))
            if file_path.is_file()
        }
        return self.analyze_submissions(submissions)

    def export_results(
        self,
        result: BatchAnalysisResult,
        output_dir: str,
        formats: Optional[Iterable[str]] = None,
    ) -> Dict[str, str]:
        requested_formats = list(formats or ["json"])
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        exported: Dict[str, str] = {}
        if "json" in requested_formats:
            json_path = output_path / "batch_analysis.json"
            payload = {
                "total_submissions": result.total_submissions,
                "total_comparisons": result.total_comparisons,
                "execution_time": result.execution_time,
                "summary": result.summary,
                "analysis_results": {name: asdict(data) for name, data in result.analysis_results.items()},
                "comparison_results": [asdict(data) for data in result.comparison_results],
            }
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            exported["json"] = str(json_path)

        if "csv" in requested_formats:
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
                            "file_a": comparison.file_a,
                            "file_b": comparison.file_b,
                            "overall_score": f"{comparison.overall_score:.6f}",
                            "is_suspicious": comparison.is_suspicious,
                        }
                    )
            exported["csv"] = str(csv_path)

        if "html" in requested_formats:
            html_path = output_path / "batch_analysis.html"
            rows = "\n".join(
                f"<tr><td>{comparison.file_a}</td><td>{comparison.file_b}</td>"
                f"<td>{comparison.overall_score:.3f}</td><td>{comparison.is_suspicious}</td></tr>"
                for comparison in result.comparison_results
            )
            html_path.write_text(
                (
                    "<html><body><h1>Batch Analysis</h1>"
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
    submissions: Dict[str, str],
    analyzer: Optional[CodeAnalyzer] = None,
) -> BatchAnalysisResult:
    """Analyze a submission mapping with default configuration."""
    return BatchAnalyzer(analyzer=analyzer).analyze_submissions(submissions)


def _detect_language_from_name(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".java":
        return "java"
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return "javascript"
    return "python"
