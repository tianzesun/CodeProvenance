"""Main report builder for certification reports.

Orchestrates the generation of publication-grade certification reports
with statistical analysis, stratified results, and reproducibility tracking.
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from jinja2 import Environment, FileSystemLoader, Template

from .models import BenchmarkRecord, EngineMetrics, ComparisonResult, records_to_arrays, group_records_by_engine
from .statistical_tests import mcnemar_test, wilcoxon_signed_rank_test, paired_statistical_tests, bonferroni_correction
from .effect_size import cohens_d, cliffs_delta, interpret_effect_size
from .confidence_intervals import bootstrap_ci, wilson_score_interval, ConfidenceInterval
from .stratified import StratifiedAnalyzer, StratifiedResults, compute_metrics_from_records
from .tables import ResultsTable, SignificanceTable, StratifiedTable
from .plots import ReliabilityDiagramPlotter, DegradationCurvePlotter
from .reproducibility import collect_reproducibility_info, ReproducibilityInfo, compute_reproducibility_hash


@dataclass
class CertificationReport:
    """Complete certification report.

    Attributes:
        report_id: Unique report identifier.
        timestamp: Report generation timestamp.
        dataset_name: Name of the evaluation dataset.
        engines: List of engine names evaluated.
        n_samples: Total number of samples.
        main_results: Main results table.
        significance_tests: Statistical significance table.
        stratified_results: Stratified analysis results.
        comparisons: Pairwise comparison results.
        reproducibility: Reproducibility information.
        executive_summary: Human-readable executive summary.
        metadata: Additional metadata.
    """
    report_id: str
    timestamp: str
    dataset_name: str
    engines: List[str]
    n_samples: int
    main_results: ResultsTable
    significance_tests: SignificanceTable
    stratified_results: Dict[str, StratifiedResults]
    comparisons: Dict[str, ComparisonResult]
    reproducibility: ReproducibilityInfo
    executive_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "dataset_name": self.dataset_name,
            "engines": self.engines,
            "n_samples": self.n_samples,
            "main_results": self.main_results.to_dict(),
            "significance_tests": self.significance_tests.to_dict(),
            "stratified_results": {k: v.to_dict() for k, v in self.stratified_results.items()},
            "comparisons": {k: v.to_dict() for k, v in self.comparisons.items()},
            "reproducibility": self.reproducibility.to_dict(),
            "executive_summary": self.executive_summary,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save_json(self, path: Union[str, Path]) -> None:
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())

    def to_html(self) -> str:
        """Generate HTML report using Jinja2 template."""
        # Prepare metrics data
        metrics_data = []
        for engine in self.engines:
            metrics = self.main_results.metrics
            engine_idx = self.engines.index(engine)
            metrics_data.append({
                "name": engine,
                "precision": f"{metrics.get('Precision', [0.0])[engine_idx]:.4f}",
                "recall": f"{metrics.get('Recall', [0.0])[engine_idx]:.4f}",
                "f1": f"{metrics.get('F1', [0.0])[engine_idx]:.4f}",
                "accuracy": f"{metrics.get('Accuracy', [0.0])[engine_idx]:.4f}",
                "roc_auc": "N/A",  # Can be extended
            })

        # Prepare confidence intervals data
        ci_data = []
        for engine in self.engines:
            engine_idx = self.engines.index(engine)
            for metric_name in ["Precision", "Recall", "F1"]:
                if metric_name in self.main_results.confidence_intervals:
                    ci = self.main_results.confidence_intervals[metric_name][engine_idx]
                    ci_data.append({
                        "name": engine,
                        "metric": metric_name,
                        "mean": f"{self.main_results.metrics[metric_name][engine_idx]:.4f}",
                        "lower": f"{ci[0]:.4f}",
                        "upper": f"{ci[1]:.4f}",
                    })

        # Prepare significance tests data
        sig_data = []
        for i, comparison in enumerate(self.significance_tests.comparisons):
            comp_result = list(self.comparisons.values())[i] if i < len(self.comparisons) else None
            sig_data.append({
                "name": comparison,
                "delta": f"{comp_result.f1_diff:+.4f}" if comp_result else "N/A",
                "p_value": f"{self.significance_tests.mcnemar_pvalues[i]:.6f}",
                "significant": "Yes" if self.significance_tests.significant[i] else "No",
            })

        # Prepare stratified data
        stratified_data = []
        for engine_name, strat_results in self.stratified_results.items():
            # Clone type results
            for clone_type, metrics in sorted(strat_results.by_clone_type.items()):
                stratified_data.append({
                    "category": f"{engine_name} - Type {clone_type}",
                    "f1": f"{metrics.f1:.4f}",
                })
            # Difficulty results
            for difficulty, metrics in strat_results.by_difficulty.items():
                stratified_data.append({
                    "category": f"{engine_name} - {difficulty}",
                    "f1": f"{metrics.f1:.4f}",
                })

        # Prepare calibration data (if available)
        calibration_data = {"ece": "N/A"}

        # Prepare reproducibility data
        repro_data = {
            "dataset_hash": self.reproducibility.dataset_hash or "N/A",
            "code_version": self.reproducibility.code_commit[:8] if self.reproducibility.code_commit else "N/A",
            "config_hash": self.reproducibility.config_hash or "N/A",
            "combined_hash": compute_reproducibility_hash(
                self.reproducibility.dataset_hash,
                {"config": self.metadata},
                self.reproducibility.random_seed,
            ),
        }

        # Load and render template
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("certification_report.html")

        html = template.render(
            report_version="1.0",
            generated_at=self.timestamp,
            dataset_name=self.dataset_name,
            dataset_version="1.0",
            reproducibility_hash=repro_data["combined_hash"][:16],
            metrics=metrics_data,
            confidence_intervals=ci_data,
            significance_tests=sig_data,
            calibration=calibration_data,
            stratified=stratified_data,
            reproducibility=repro_data,
        )

        return html

    def save_html(self, path: Union[str, Path]) -> None:
        """Save report to HTML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_html())

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            f"CERTIFICATION REPORT: {self.dataset_name}",
            "=" * 60,
            f"Report ID: {self.report_id}",
            f"Timestamp: {self.timestamp}",
            f"Engines: {', '.join(self.engines)}",
            f"Samples: {self.n_samples}",
            "",
        ]

        if self.executive_summary:
            lines.extend(["EXECUTIVE SUMMARY:", "-" * 40, self.executive_summary, ""])

        lines.extend(["MAIN RESULTS:", "-" * 40, self.main_results.to_markdown(), ""])
        lines.extend(["STATISTICAL SIGNIFICANCE:", "-" * 40, self.significance_tests.to_markdown(), ""])

        lines.append("=" * 60)
        return "\n".join(lines)


class CertificationReportBuilder:
    """Builder for certification reports.

    Orchestrates the complete certification process including:
    - Computing metrics for all engines
    - Running statistical tests
    - Performing stratified analysis
    - Generating publication-grade reports
    """

    def __init__(
        self,
        baseline_engine: Optional[str] = None,
        n_bootstrap: int = 2000,
        confidence_level: float = 0.95,
        alpha: float = 0.05,
        seed: int = 42,
    ) -> None:
        """Initialize report builder.

        Args:
            baseline_engine: Name of baseline engine for comparisons.
            n_bootstrap: Number of bootstrap samples.
            confidence_level: Confidence level for intervals.
            alpha: Significance level for tests.
            seed: Random seed for reproducibility.
        """
        self.baseline_engine = baseline_engine
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level
        self.alpha = alpha
        self.seed = seed
        self.stratified_analyzer = StratifiedAnalyzer(n_bootstrap, confidence_level, seed)

    def build(
        self,
        records: List[BenchmarkRecord],
        dataset_name: str = "evaluation_dataset",
        config: Optional[Dict[str, Any]] = None,
    ) -> CertificationReport:
        """Build complete certification report.

        Args:
            records: List of benchmark records.
            dataset_name: Name of the dataset.
            config: Optional configuration dictionary.

        Returns:
            Complete CertificationReport.
        """
        if not records:
            raise ValueError("No records provided for certification")

        # Generate report ID
        report_id = f"cert_{dataset_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()

        # Group records by engine
        engine_groups = group_records_by_engine(records)
        engines = list(engine_groups.keys())

        # Compute metrics for each engine
        engine_metrics = {}
        for engine_name, engine_records in engine_groups.items():
            engine_metrics[engine_name] = compute_metrics_from_records(
                engine_records, engine_name, self.n_bootstrap, self.confidence_level, self.seed
            )

        # Build main results table
        main_results = ResultsTable(title="Main Results")
        for engine_name in engines:
            metrics = engine_metrics[engine_name]
            main_results.add_engine(
                engine_name,
                {"Precision": metrics.precision, "Recall": metrics.recall, "F1": metrics.f1, "Accuracy": metrics.accuracy},
                {"Precision": metrics.ci_precision, "Recall": metrics.ci_recall, "F1": metrics.ci_f1},
            )

        # Run statistical tests between engines
        significance_tests = SignificanceTable(title="Statistical Significance")
        comparisons = {}

        if len(engines) >= 2:
            # Use baseline or first engine as reference
            baseline = self.baseline_engine or engines[0]

            for engine_name in engines:
                if engine_name == baseline:
                    continue

                # Get paired data
                baseline_records = engine_groups[baseline]
                engine_records = engine_groups[engine_name]

                # Match records by pair_id
                baseline_dict = {r.pair_id: r for r in baseline_records}
                engine_dict = {r.pair_id: r for r in engine_records}

                common_pairs = set(baseline_dict.keys()) & set(engine_dict.keys())
                if not common_pairs:
                    continue

                # Extract paired data
                y_true = np.array([baseline_dict[p].label for p in common_pairs])
                scores_baseline = np.array([baseline_dict[p].score for p in common_pairs])
                scores_engine = np.array([engine_dict[p].score for p in common_pairs])
                decisions_baseline = np.array([baseline_dict[p].decision for p in common_pairs])
                decisions_engine = np.array([engine_dict[p].decision for p in common_pairs])

                # McNemar test
                mcnemar_result = mcnemar_test(y_true, decisions_baseline, decisions_engine, alpha=self.alpha)

                # Wilcoxon test
                wilcoxon_result = wilcoxon_signed_rank_test(scores_baseline, scores_engine, alpha=self.alpha)

                # Effect sizes
                cohens_d_result = cohens_d(scores_baseline, scores_engine)
                cliffs_delta_result = cliffs_delta(scores_baseline, scores_engine)

                # Compute metric differences
                metrics_baseline = engine_metrics[baseline]
                metrics_engine = engine_metrics[engine_name]

                comparison = ComparisonResult(
                    engine_a=baseline,
                    engine_b=engine_name,
                    mcnemar_pvalue=mcnemar_result.p_value,
                    mcnemar_significant=mcnemar_result.significant,
                    wilcoxon_pvalue=wilcoxon_result.p_value,
                    wilcoxon_significant=wilcoxon_result.significant,
                    cohens_d=cohens_d_result.value,
                    cliffs_delta=cliffs_delta_result.value,
                    effect_size_interpretation=cohens_d_result.interpretation,
                    f1_diff=metrics_baseline.f1 - metrics_engine.f1,
                    precision_diff=metrics_baseline.precision - metrics_engine.precision,
                    recall_diff=metrics_baseline.recall - metrics_engine.recall,
                )

                comparisons[f"{baseline}_vs_{engine_name}"] = comparison

                # Add to significance table
                is_significant = mcnemar_result.significant or wilcoxon_result.significant
                significance_tests.add_comparison(
                    f"{baseline} vs {engine_name}",
                    mcnemar_result.p_value,
                    wilcoxon_result.p_value,
                    cohens_d_result.value,
                    is_significant,
                )

        # Stratified analysis
        stratified_results = {}
        for engine_name, engine_records in engine_groups.items():
            stratified_results[engine_name] = self.stratified_analyzer.analyze(
                engine_records, engine_name
            )

        # Collect reproducibility info
        dataset_hash = ""
        if records:
            pair_ids = [r.pair_id for r in records]
            pair_ids_str = "|".join(sorted(set(pair_ids)))
            import hashlib
            dataset_hash = hashlib.sha256(pair_ids_str.encode()).hexdigest()[:16]

        reproducibility = collect_reproducibility_info(
            dataset_hash=dataset_hash,
            config=config,
            random_seed=self.seed,
        )

        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            engines, engine_metrics, comparisons, stratified_results
        )

        return CertificationReport(
            report_id=report_id,
            timestamp=timestamp,
            dataset_name=dataset_name,
            engines=engines,
            n_samples=len(records),
            main_results=main_results,
            significance_tests=significance_tests,
            stratified_results=stratified_results,
            comparisons=comparisons,
            reproducibility=reproducibility,
            executive_summary=executive_summary,
            metadata={
                "n_bootstrap": self.n_bootstrap,
                "confidence_level": self.confidence_level,
                "alpha": self.alpha,
                "seed": self.seed,
            },
        )

    def _generate_executive_summary(
        self,
        engines: List[str],
        engine_metrics: Dict[str, EngineMetrics],
        comparisons: Dict[str, ComparisonResult],
        stratified_results: Dict[str, StratifiedResults],
    ) -> str:
        """Generate executive summary.

        Args:
            engines: List of engine names.
            engine_metrics: Metrics for each engine.
            comparisons: Pairwise comparisons.
            stratified_results: Stratified results.

        Returns:
            Executive summary string.
        """
        if not engines:
            return "No engines evaluated."

        # Find best engine by F1
        best_engine = max(engines, key=lambda e: engine_metrics[e].f1)
        best_f1 = engine_metrics[best_engine].f1

        lines = [
            f"Evaluated {len(engines)} engine(s) on the dataset.",
            f"Best performing engine: {best_engine} (F1={best_f1:.4f})",
        ]

        # Add significant comparisons
        significant_comparisons = [
            (name, comp) for name, comp in comparisons.items()
            if comp.mcnemar_significant or comp.wilcoxon_significant
        ]

        if significant_comparisons:
            lines.append(f"Found {len(significant_comparisons)} statistically significant difference(s).")
            for name, comp in significant_comparisons[:3]:  # Top 3
                if comp.f1_diff > 0:
                    lines.append(f"  - {comp.engine_a} outperforms {comp.engine_b} by {comp.f1_diff:.4f} F1")
                else:
                    lines.append(f"  - {comp.engine_b} outperforms {comp.engine_a} by {-comp.f1_diff:.4f} F1")
        else:
            lines.append("No statistically significant differences found between engines.")

        return " ".join(lines)