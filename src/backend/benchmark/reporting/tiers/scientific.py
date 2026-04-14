"""Scientific reporting tier for paper-ready outputs.

Generates publication-ready reports with LaTeX support, statistical analysis,
and reproducibility information.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


@dataclass
class StatisticalTest:
    """Represents a statistical test result."""
    test_name: str
    statistic: float
    p_value: float
    significant: bool
    effect_size: Optional[float] = None
    confidence_interval: Optional[tuple] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "significant": self.significant,
            "effect_size": self.effect_size,
            "confidence_interval": list(self.confidence_interval) if self.confidence_interval else None
        }


@dataclass
class EngineResult:
    """Results for a single engine."""
    engine_name: str
    engine_version: str
    precision: float
    recall: float
    f1_score: float
    accuracy: Optional[float] = None
    auc_roc: Optional[float] = None
    execution_time_ms: float = 0.0
    additional_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "accuracy": self.accuracy,
            "auc_roc": self.auc_roc,
            "execution_time_ms": self.execution_time_ms,
            "additional_metrics": self.additional_metrics
        }


@dataclass
class ReproducibilityInfo:
    """Information for reproducing benchmark results."""
    timestamp: str
    config_hash: str
    dataset_versions: Dict[str, str]
    software_versions: Dict[str, str]
    random_seeds: Dict[str, int]
    environment: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "config_hash": self.config_hash,
            "dataset_versions": self.dataset_versions,
            "software_versions": self.software_versions,
            "random_seeds": self.random_seeds,
            "environment": self.environment
        }


class ScientificReport:
    """Paper-ready benchmark report with LaTeX export.

    Generates comprehensive reports suitable for academic publication,
    including statistical significance testing and reproducibility information.
    """

    def __init__(
        self,
        title: str,
        abstract: str,
        methodology: str,
        results: List[EngineResult],
        statistical_tests: List[StatisticalTest],
        reproducibility_info: ReproducibilityInfo,
        figure_paths: Optional[List[str]] = None
    ):
        """Initialize scientific report.

        Args:
            title: Report title
            abstract: Report abstract
            methodology: Methodology description
            results: List of engine results
            statistical_tests: Statistical significance tests
            reproducibility_info: Reproducibility information
            figure_paths: Paths to generated figures
        """
        self.title = title
        self.abstract = abstract
        self.methodology = methodology
        self.results = results
        self.statistical_tests = statistical_tests
        self.reproducibility_info = reproducibility_info
        self.figure_paths = figure_paths or []

    def to_latex(self) -> str:
        """Generate LaTeX format for papers.

        Returns:
            LaTeX string representation of the report
        """
        latex = f"""\\section{{Results}}

\\subsection{{Overall Performance}}

{self._results_to_latex()}

\\subsection{{Statistical Significance}}

{self._significance_to_latex()}

\\subsection{{Reproducibility}}

{self._reproducibility_to_latex()}
"""
        return latex

    def _results_to_latex(self) -> str:
        """Convert results to LaTeX table."""
        rows = []
        for result in self.results:
            rows.append(
                f"{result.engine_name} ({result.engine_version}) & "
                f"{result.precision:.4f} & {result.recall:.4f} & "
                f"{result.f1_score:.4f} \\\\"
            )

        return f"""\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{l|ccc}}
\\hline
Engine & Precision & Recall & F1 Score \\\\
\\hline
{chr(10).join(rows)}
\\hline
\\end{{tabular}}
\\caption{{Benchmark Results}}
\\label{{tab:results}}
\\end{{table}}"""

    def _significance_to_latex(self) -> str:
        """Convert statistical tests to LaTeX."""
        rows = []
        for test in self.statistical_tests:
            significance = "Yes" if test.significant else "No"
            rows.append(
                f"{test.test_name} & {test.statistic:.4f} & "
                f"{test.p_value:.4f} & {significance} \\\\"
            )

        return f"""\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{l|ccc}}
\\hline
Test & Statistic & p-value & Significant \\\\
\\hline
{chr(10).join(rows)}
\\hline
\\end{{tabular}}
\\caption{{Statistical Significance Tests}}
\\label{{tab:significance}}
\\end{{table}}"""

    def _reproducibility_to_latex(self) -> str:
        """Convert reproducibility info to LaTeX."""
        info = self.reproducibility_info
        return f"""\\begin{{itemize}}
    \\item \\textbf{{Timestamp}}: {info.timestamp}
    \\item \\textbf{{Config Hash}}: \\texttt{{{info.config_hash}}}
    \\item \\textbf{{Dataset Versions}}: {', '.join(f'{k}={v}' for k, v in info.dataset_versions.items())}
    \\item \\textbf{{Software Versions}}: {', '.join(f'{k}={v}' for k, v in info.software_versions.items())}
\\end{{itemize}}"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.

        Returns:
            Dictionary representation of the report
        """
        return {
            "title": self.title,
            "abstract": self.abstract,
            "methodology": self.methodology,
            "results": [r.to_dict() for r in self.results],
            "statistical_tests": [t.to_dict() for t in self.statistical_tests],
            "reproducibility_info": self.reproducibility_info.to_dict(),
            "figure_paths": self.figure_paths
        }

    def to_json(self, indent: int = 2) -> str:
        """Generate JSON format.

        Args:
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScientificReport':
        """Create report from dictionary.

        Args:
            data: Dictionary containing report data

        Returns:
            ScientificReport instance
        """
        results = [
            EngineResult(
                engine_name=r["engine_name"],
                engine_version=r["engine_version"],
                precision=r["precision"],
                recall=r["recall"],
                f1_score=r["f1_score"],
                accuracy=r.get("accuracy"),
                auc_roc=r.get("auc_roc"),
                execution_time_ms=r.get("execution_time_ms", 0.0),
                additional_metrics=r.get("additional_metrics", {})
            )
            for r in data["results"]
        ]

        statistical_tests = [
            StatisticalTest(
                test_name=t["test_name"],
                statistic=t["statistic"],
                p_value=t["p_value"],
                significant=t["significant"],
                effect_size=t.get("effect_size"),
                confidence_interval=tuple(t["confidence_interval"]) if t.get("confidence_interval") else None
            )
            for t in data["statistical_tests"]
        ]

        repro_info = data["reproducibility_info"]
        reproducibility_info = ReproducibilityInfo(
            timestamp=repro_info["timestamp"],
            config_hash=repro_info["config_hash"],
            dataset_versions=repro_info["dataset_versions"],
            software_versions=repro_info["software_versions"],
            random_seeds=repro_info["random_seeds"],
            environment=repro_info["environment"]
        )

        return cls(
            title=data["title"],
            abstract=data["abstract"],
            methodology=data["methodology"],
            results=results,
            statistical_tests=statistical_tests,
            reproducibility_info=reproducibility_info,
            figure_paths=data.get("figure_paths", [])
        )