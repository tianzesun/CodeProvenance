"""PAN-style plagiarism benchmark runner.

This runner executes plagiarism tools on supported local datasets, evaluates
them with the project's PAN metric implementation, caches intermediate tool
results, and writes a publication-ready markdown report plus JSON artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import inspect
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

from src.backend.benchmark.contracts.evaluation_result import EnrichedPair

logger = logging.getLogger(__name__)


def _discover_repo_root() -> Path:
    """Locate the repository root."""
    here = Path(__file__).resolve()
    return here.parents[4]


@dataclass(frozen=True)
class TechniqueSignal:
    """Minimal technique signal used by the benchmark runner."""

    name: str
    confidence: float


@dataclass
class TechniqueSummary:
    """Minimal obfuscation summary used for reporting."""

    primary_technique: Optional[str]
    complexity_score: float
    techniques: list[TechniqueSignal] = field(default_factory=list)


@dataclass
class _SimpleScoringTool:
    """Small compare-only adapter used for deterministic benchmark scoring."""

    name: str
    scorer: Any

    def compare(self, code_a: str, code_b: str) -> float:
        """Return a bounded similarity score."""
        raw_score = float(self.scorer(code_a, code_b))
        return max(0.0, min(1.0, raw_score))


class PANDataSet(str, Enum):
    """Stable dataset names exported for backward compatibility."""

    IR_PLAG = "ir-plag"
    CONPLAG_CLASSROOM_JAVA = "conplag-classroom-java"
    CUSTOM = "custom"


_PAN_METRICS_MODULE = None
_TOOL_ADAPTERS_MODULE = None


def _load_pan_metrics_module() -> Any:
    """Load the PAN metrics module without importing package side effects."""
    global _PAN_METRICS_MODULE
    if _PAN_METRICS_MODULE is not None:
        return _PAN_METRICS_MODULE

    module_path = _discover_repo_root() / "src" / "backend" / "evaluation" / "pan_metrics.py"
    spec = importlib.util.spec_from_file_location(
        "codeprovenance_pan_metrics",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load PAN metrics module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _PAN_METRICS_MODULE = module
    return module


_PAN = _load_pan_metrics_module()
Detection = _PAN.Detection
PANMetrics = _PAN.PANMetrics
TextSpan = _PAN.TextSpan
calculate_pan_metrics = _PAN.calculate_pan_metrics
pan_macro_average = _PAN.pan_macro_average
pan_micro_average = _PAN.pan_micro_average


def _load_tool_adapters_module() -> Any:
    """Load the cross-dataset tool adapter module without package side effects."""
    global _TOOL_ADAPTERS_MODULE
    if _TOOL_ADAPTERS_MODULE is not None:
        return _TOOL_ADAPTERS_MODULE

    module_path = (
        _discover_repo_root()
        / "src"
        / "backend"
        / "benchmark"
        / "cross_dataset"
        / "tool_adapters.py"
    )
    spec = importlib.util.spec_from_file_location(
        "codeprovenance_cross_dataset_tool_adapters",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tool adapters module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _TOOL_ADAPTERS_MODULE = module
    return module


@dataclass(frozen=True)
class PANDatasetPair:
    """A benchmark pair normalized for PAN-style scoring."""

    pair_id: str
    dataset_name: str
    language: str
    suspicious_id: str
    source_id: str
    suspicious_path: str
    source_path: str
    suspicious_code: str
    source_code: str
    label: int
    obfuscation_type: str
    obfuscation_strength: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PANDataset:
    """A supported benchmark dataset."""

    name: str
    root_dir: str
    language: str
    pairs: list[PANDatasetPair]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def signature(self) -> str:
        """Return a stable signature for cache invalidation."""
        payload = {
            "name": self.name,
            "root_dir": self.root_dir,
            "pair_count": len(self.pairs),
            "metadata": self.metadata,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]


@dataclass(frozen=True)
class PairEvaluationRecord:
    """Per-pair evaluation record used for reporting and caching."""

    pair_id: str
    score: float
    predicted: bool
    label: int
    obfuscation_type: str
    obfuscation_strength: int
    pan_metrics: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PANBenchmarkResult:
    """Result from running a tool on a dataset."""

    tool_name: str
    dataset_name: str
    total_pairs: int
    pan_metrics: PANMetrics
    execution_time_seconds: float
    per_pair_results: list[PANMetrics] = field(default_factory=list)
    pair_records: list[PairEvaluationRecord] = field(default_factory=list)
    obfuscation_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    strength_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Convert result to a serializable dictionary."""
        return {
            "tool_name": self.tool_name,
            "dataset_name": self.dataset_name,
            "total_pairs": self.total_pairs,
            "execution_time_seconds": round(self.execution_time_seconds, 6),
            "pan_metrics": self.pan_metrics.as_dict(),
            "obfuscation_breakdown": self.obfuscation_breakdown,
            "strength_breakdown": self.strength_breakdown,
            "metadata": self.metadata,
            "pair_records": [asdict(record) for record in self.pair_records],
        }


@dataclass
class BenchmarkComparisonReport:
    """Aggregate report across tools and datasets."""

    results: list[PANBenchmarkResult]
    generated_at: float = field(default_factory=time.time)
    threshold: float = 0.5
    use_micro_average: bool = False

    def get_tool_summary(self) -> dict[str, list[PANBenchmarkResult]]:
        """Group results by tool."""
        grouped: dict[str, list[PANBenchmarkResult]] = {}
        for result in self.results:
            grouped.setdefault(result.tool_name, []).append(result)
        return grouped

    def get_dataset_summary(self) -> dict[str, list[PANBenchmarkResult]]:
        """Group results by dataset."""
        grouped: dict[str, list[PANBenchmarkResult]] = {}
        for result in self.results:
            grouped.setdefault(result.dataset_name, []).append(result)
        return grouped

    def _tool_rankings(self) -> list[dict[str, Any]]:
        """Build aggregate ranking rows for each tool."""
        rankings: list[dict[str, Any]] = []
        for tool_name, tool_results in self.get_tool_summary().items():
            plagdet = _safe_mean(
                result.pan_metrics.plagdet for result in tool_results
            )
            precision = _safe_mean(
                result.pan_metrics.precision for result in tool_results
            )
            recall = _safe_mean(result.pan_metrics.recall for result in tool_results)
            f1_score = _safe_mean(result.pan_metrics.f1_score for result in tool_results)
            granularity = _safe_mean(
                result.pan_metrics.granularity for result in tool_results
            )
            runtime = sum(result.execution_time_seconds for result in tool_results)
            rankings.append(
                {
                    "tool": tool_name,
                    "datasets": len(tool_results),
                    "precision": precision,
                    "recall": recall,
                    "f1_score": f1_score,
                    "granularity": granularity,
                    "plagdet": plagdet,
                    "runtime": runtime,
                }
            )
        return sorted(rankings, key=lambda item: item["plagdet"], reverse=True)

    def generate_comparison_table(self) -> str:
        """Generate the main ranking table."""
        rows = self._tool_rankings()
        if not rows:
            return "No benchmark results available."

        table_rows = [
            [
                row["tool"],
                str(row["datasets"]),
                _fmt_metric(row["precision"]),
                _fmt_metric(row["recall"]),
                _fmt_metric(row["f1_score"]),
                _fmt_metric(row["granularity"]),
                _fmt_metric(row["plagdet"]),
                f"{row['runtime']:.2f}",
            ]
            for row in rows
        ]
        return _markdown_table(
            [
                "Tool",
                "Datasets",
                "Precision",
                "Recall",
                "F1",
                "Granularity",
                "PlagDet",
                "Time (s)",
            ],
            table_rows,
        )

    def save_markdown(self, path: str | Path) -> Path:
        """Write a complete markdown report."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        timestamp = datetime.fromtimestamp(
            self.generated_at, tz=timezone.utc
        ).isoformat()
        averaging = "micro" if self.use_micro_average else "macro"

        lines.append("# PAN Benchmark Report")
        lines.append("")
        lines.append(f"Generated: `{timestamp}`")
        lines.append(f"Threshold: `{self.threshold:.2f}`")
        lines.append(f"Averaging: `{averaging}`")
        lines.append("")
        lines.append("## Main Ranking")
        lines.append("")
        lines.append(self.generate_comparison_table())

        for dataset_name, dataset_results in sorted(self.get_dataset_summary().items()):
            lines.append("")
            lines.append(f"## Dataset: {dataset_name}")
            lines.append("")
            dataset_rows = [
                [
                    result.tool_name,
                    _fmt_metric(result.pan_metrics.precision),
                    _fmt_metric(result.pan_metrics.recall),
                    _fmt_metric(result.pan_metrics.f1_score),
                    _fmt_metric(result.pan_metrics.granularity),
                    _fmt_metric(result.pan_metrics.plagdet),
                    f"{result.execution_time_seconds:.2f}",
                ]
                for result in sorted(
                    dataset_results,
                    key=lambda item: item.pan_metrics.plagdet,
                    reverse=True,
                )
            ]
            lines.append(
                _markdown_table(
                    [
                        "Tool",
                        "Precision",
                        "Recall",
                        "F1",
                        "Granularity",
                        "PlagDet",
                        "Time (s)",
                    ],
                    dataset_rows,
                )
            )

        lines.append("")
        lines.append("## Per Tool Breakdown")
        for tool_name, tool_results in sorted(self.get_tool_summary().items()):
            lines.append("")
            lines.append(f"### {tool_name}")
            lines.append("")
            lines.append(
                _markdown_table(
                    [
                        "Dataset",
                        "Precision",
                        "Recall",
                        "F1",
                        "Granularity",
                        "PlagDet",
                        "Time (s)",
                    ],
                    [
                        [
                            result.dataset_name,
                            _fmt_metric(result.pan_metrics.precision),
                            _fmt_metric(result.pan_metrics.recall),
                            _fmt_metric(result.pan_metrics.f1_score),
                            _fmt_metric(result.pan_metrics.granularity),
                            _fmt_metric(result.pan_metrics.plagdet),
                            f"{result.execution_time_seconds:.2f}",
                        ]
                        for result in sorted(
                            tool_results,
                            key=lambda item: item.dataset_name,
                        )
                    ],
                )
            )

            obfuscation_rows: list[list[str]] = []
            for result in tool_results:
                for obfuscation_type, metrics in sorted(
                    result.obfuscation_breakdown.items()
                ):
                    obfuscation_rows.append(
                        [
                            result.dataset_name,
                            obfuscation_type,
                            _fmt_metric(metrics["precision"]),
                            _fmt_metric(metrics["recall"]),
                            _fmt_metric(metrics["f1_score"]),
                            _fmt_metric(metrics["plagdet"]),
                            str(int(metrics["support"])),
                        ]
                    )
            if obfuscation_rows:
                lines.append("")
                lines.append("Obfuscation breakdown:")
                lines.append("")
                lines.append(
                    _markdown_table(
                        [
                            "Dataset",
                            "Type",
                            "Precision",
                            "Recall",
                            "F1",
                            "PlagDet",
                            "Support",
                        ],
                        obfuscation_rows,
                    )
                )

            strength_rows: list[list[str]] = []
            for result in tool_results:
                for strength, metrics in sorted(
                    result.strength_breakdown.items(),
                    key=lambda item: int(item[0]),
                ):
                    strength_rows.append(
                        [
                            result.dataset_name,
                            strength,
                            _fmt_metric(metrics["precision"]),
                            _fmt_metric(metrics["recall"]),
                            _fmt_metric(metrics["f1_score"]),
                            _fmt_metric(metrics["plagdet"]),
                            str(int(metrics["support"])),
                        ]
                    )
            if strength_rows:
                lines.append("")
                lines.append("Precision/recall by obfuscation strength:")
                lines.append("")
                lines.append(
                    _markdown_table(
                        [
                            "Dataset",
                            "Strength",
                            "Precision",
                            "Recall",
                            "F1",
                            "PlagDet",
                            "Support",
                        ],
                        strength_rows,
                    )
                )

        lines.append("")
        lines.append("## Granularity Analysis")
        lines.append("")
        granularity_rows = [
            [
                result.tool_name,
                result.dataset_name,
                _fmt_metric(result.pan_metrics.granularity),
                _fmt_metric(_granularity_penalty(result.pan_metrics.granularity)),
            ]
            for result in sorted(
                self.results,
                key=lambda item: (item.tool_name, item.dataset_name),
            )
        ]
        lines.append(
            _markdown_table(
                ["Tool", "Dataset", "Granularity", "Penalty"],
                granularity_rows,
            )
        )

        lines.append("")
        lines.append("## Runtime Comparison")
        lines.append("")
        runtime_rows = [
            [
                row["tool"],
                f"{row['runtime']:.2f}",
                _fmt_metric(
                    row["runtime"] / max(row["datasets"], 1)
                ),
            ]
            for row in self._tool_rankings()
        ]
        lines.append(
            _markdown_table(
                ["Tool", "Total Time (s)", "Average Time per Dataset (s)"],
                runtime_rows,
            )
        )

        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    def save_json(self, path: str | Path) -> Path:
        """Write raw benchmark results to JSON."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": self.generated_at,
            "threshold": self.threshold,
            "use_micro_average": self.use_micro_average,
            "results": [result.as_dict() for result in self.results],
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target


class PANBenchmarkRunner:
    """End-to-end PAN-style benchmark runner."""

    def __init__(
        self,
        output_dir: str | Path = "reports/pan_benchmark",
        threshold: float = 0.5,
        use_micro_average: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.threshold = threshold
        self.use_micro_average = use_micro_average
        self.cache_dir = self.output_dir / "cache"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_available_tools(self) -> list[str]:
        """Return benchmark tool names."""
        return sorted(_tool_factories().keys())

    def get_available_datasets(self) -> list[str]:
        """Return supported dataset names available on disk."""
        repo_root = _discover_repo_root()
        datasets: list[str] = []
        if (repo_root / "data" / "datasets" / "IR-Plag-Dataset").exists():
            datasets.append("ir-plag")
        if (repo_root / "data" / "datasets" / "conplag_classroom_java").exists():
            datasets.append("conplag-classroom-java")
        return datasets

    def run_tool_on_dataset(
        self,
        tool_name: str,
        dataset_name: str,
        dataset_path: Optional[Path] = None,
    ) -> PANBenchmarkResult:
        """Run one tool on one dataset with caching."""
        dataset = self._load_dataset(dataset_name, dataset_path)
        cache_path = self._cache_path(tool_name=tool_name, dataset=dataset)
        if cache_path.exists():
            logger.info("Using cached result for %s on %s", tool_name, dataset_name)
            return self._load_cached_result(cache_path)

        logger.info(
            "Running %s on %s with %d pairs",
            tool_name,
            dataset.name,
            len(dataset.pairs),
        )

        tool = self._instantiate_tool(tool_name)
        start_time = time.time()
        pair_records: list[PairEvaluationRecord] = []
        per_pair_metrics: list[PANMetrics] = []
        all_ground_truth: list[list[Detection]] = []
        all_predictions: list[list[Detection]] = []

        for pair in dataset.pairs:
            score, result_metadata = self._score_pair(tool, pair)
            predicted = score >= self.threshold
            ground_truth = self._ground_truth_detections(pair)
            predictions = self._predicted_detections(pair, predicted)
            metrics = calculate_pan_metrics(ground_truth, predictions)

            per_pair_metrics.append(metrics)
            all_ground_truth.append(ground_truth)
            all_predictions.append(predictions)
            pair_records.append(
                PairEvaluationRecord(
                    pair_id=pair.pair_id,
                    score=round(score, 6),
                    predicted=predicted,
                    label=pair.label,
                    obfuscation_type=pair.obfuscation_type,
                    obfuscation_strength=pair.obfuscation_strength,
                    pan_metrics=metrics.as_dict(),
                    metadata=result_metadata,
                )
            )

        execution_time = time.time() - start_time
        final_metrics = (
            pan_micro_average(all_ground_truth, all_predictions)
            if self.use_micro_average
            else pan_macro_average(per_pair_metrics)
        )

        result = PANBenchmarkResult(
            tool_name=tool_name,
            dataset_name=dataset.name,
            total_pairs=len(dataset.pairs),
            pan_metrics=final_metrics,
            execution_time_seconds=execution_time,
            per_pair_results=per_pair_metrics,
            pair_records=pair_records,
            obfuscation_breakdown=self._compute_obfuscation_breakdown(dataset, pair_records),
            strength_breakdown=self._compute_strength_breakdown(dataset, pair_records),
            metadata={
                "dataset_signature": dataset.signature,
                "dataset_root": dataset.root_dir,
                "language": dataset.language,
            },
        )
        self._save_cached_result(cache_path, result)
        return result

    def run_benchmark(
        self,
        tools: Optional[list[str]] = None,
        datasets: Optional[list[str]] = None,
        custom_dataset_path: Optional[Path] = None,
    ) -> BenchmarkComparisonReport:
        """Run the selected benchmark matrix and return a report model."""
        selected_tools = tools or self.get_available_tools()
        selected_datasets = datasets or self.get_available_datasets()
        logger.info(
            "Starting PAN benchmark: tools=%s datasets=%s",
            selected_tools,
            selected_datasets,
        )

        results: list[PANBenchmarkResult] = []
        for dataset_name in selected_datasets:
            for tool_name in selected_tools:
                dataset_path = custom_dataset_path if dataset_name == "custom" else None
                try:
                    results.append(
                        self.run_tool_on_dataset(
                            tool_name=tool_name,
                            dataset_name=dataset_name,
                            dataset_path=dataset_path,
                        )
                    )
                except Exception as exc:
                    logger.exception(
                        "Benchmark failed for tool=%s dataset=%s: %s",
                        tool_name,
                        dataset_name,
                        exc,
                    )

        report = BenchmarkComparisonReport(
            results=results,
            threshold=self.threshold,
            use_micro_average=self.use_micro_average,
        )
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        report.save_json(self.output_dir / f"pan_benchmark_results_{timestamp}.json")
        report.save_markdown(self.output_dir / f"pan_benchmark_report_{timestamp}.md")
        return report

    def _load_dataset(
        self,
        dataset_name: str,
        dataset_path: Optional[Path] = None,
    ) -> PANDataset:
        """Load one supported dataset."""
        normalized_name = dataset_name.lower()
        repo_root = _discover_repo_root()

        if normalized_name in {"ir-plag", "ir_plag"}:
            root = dataset_path or repo_root / "data" / "datasets" / "IR-Plag-Dataset"
            return self._load_ir_plag_dataset(root)

        if normalized_name in {
            "conplag-classroom-java",
            "conplag_classroom_java",
        }:
            root = dataset_path or repo_root / "data" / "datasets" / "conplag_classroom_java"
            return self._load_conplag_classroom_dataset(root)

        if normalized_name == "custom":
            if dataset_path is None:
                raise ValueError("custom dataset requires --dataset-path")
            if (dataset_path / "labels.csv").exists():
                return self._load_conplag_classroom_dataset(dataset_path)
            return self._load_ir_plag_dataset(dataset_path)

        raise ValueError(f"Unsupported dataset: {dataset_name}")

    def _load_ir_plag_dataset(self, root_dir: Path) -> PANDataset:
        """Load the IR-Plag dataset."""
        if not root_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {root_dir}")

        pairs: list[PANDatasetPair] = []
        case_count = 0
        for case_dir in sorted(root_dir.glob("case-*")):
            original_files = sorted((case_dir / "original").glob("*.java"))
            if not original_files:
                continue
            case_count += 1
            original_path = original_files[0]
            original_code = self._read_code(original_path)

            for level_dir in sorted((case_dir / "plagiarized").glob("L*")):
                try:
                    strength = int(level_dir.name.replace("L", ""))
                except ValueError:
                    continue
                for plag_path in sorted(level_dir.rglob("*.java")):
                    plag_code = self._read_code(plag_path)
                    obfuscation_type = self._infer_obfuscation_type(
                        original_code, plag_code
                    )
                    pairs.append(
                        PANDatasetPair(
                            pair_id=(
                                f"{case_dir.name}:{level_dir.name}:"
                                f"{plag_path.parent.name}:{plag_path.name}"
                            ),
                            dataset_name="ir-plag",
                            language="java",
                            suspicious_id=plag_path.stem,
                            source_id=original_path.stem,
                            suspicious_path=str(plag_path),
                            source_path=str(original_path),
                            suspicious_code=plag_code,
                            source_code=original_code,
                            label=1,
                            obfuscation_type=obfuscation_type,
                            obfuscation_strength=strength,
                            metadata={
                                "case": case_dir.name,
                                "variant": plag_path.parent.name,
                                "split": "benchmark",
                            },
                        )
                    )

            for negative_path in sorted((case_dir / "non-plagiarized").rglob("*.java")):
                negative_code = self._read_code(negative_path)
                pairs.append(
                    PANDatasetPair(
                        pair_id=f"{case_dir.name}:negative:{negative_path.parent.name}:{negative_path.name}",
                        dataset_name="ir-plag",
                        language="java",
                        suspicious_id=negative_path.stem,
                        source_id=original_path.stem,
                        suspicious_path=str(negative_path),
                        source_path=str(original_path),
                        suspicious_code=negative_code,
                        source_code=original_code,
                        label=0,
                        obfuscation_type="none",
                        obfuscation_strength=0,
                        metadata={
                            "case": case_dir.name,
                            "variant": negative_path.parent.name,
                            "split": "benchmark",
                        },
                    )
                )

        return PANDataset(
            name="ir-plag",
            root_dir=str(root_dir),
            language="java",
            pairs=pairs,
            metadata={"cases": case_count},
        )

    def _load_conplag_classroom_dataset(self, root_dir: Path) -> PANDataset:
        """Load the classroom-style ConPlag Java dataset."""
        labels_path = root_dir / "labels.csv"
        if not labels_path.exists():
            raise FileNotFoundError(f"Dataset labels not found: {labels_path}")

        pairs: list[PANDatasetPair] = []
        with labels_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                split = row.get("split", "").strip().lower()
                if split and split != "test":
                    continue

                assignment_id = row["assignment_id"]
                file_a = row["file_a"]
                file_b = row["file_b"]
                label = 1 if row["label"].strip().lower() == "plagiarized" else 0

                path_a = (
                    root_dir
                    / "assignments"
                    / assignment_id
                    / "submissions"
                    / file_a
                )
                path_b = (
                    root_dir
                    / "assignments"
                    / assignment_id
                    / "submissions"
                    / file_b
                )
                if not path_a.exists() or not path_b.exists():
                    logger.warning(
                        "Skipping missing pair files for assignment=%s %s %s",
                        assignment_id,
                        file_a,
                        file_b,
                    )
                    continue

                code_a = self._read_code(path_a)
                code_b = self._read_code(path_b)
                if label == 1:
                    obfuscation_type = self._infer_obfuscation_type(code_a, code_b)
                    obfuscation_strength = self._infer_strength(code_a, code_b)
                else:
                    obfuscation_type = "none"
                    obfuscation_strength = 0

                pairs.append(
                    PANDatasetPair(
                        pair_id=f"{assignment_id}:{file_a}:{file_b}",
                        dataset_name="conplag-classroom-java",
                        language="java",
                        suspicious_id=Path(file_a).stem,
                        source_id=Path(file_b).stem,
                        suspicious_path=str(path_a),
                        source_path=str(path_b),
                        suspicious_code=code_a,
                        source_code=code_b,
                        label=label,
                        obfuscation_type=obfuscation_type,
                        obfuscation_strength=obfuscation_strength,
                        metadata={
                            "assignment_id": assignment_id,
                            "split": split or "all",
                        },
                    )
                )

        return PANDataset(
            name="conplag-classroom-java",
            root_dir=str(root_dir),
            language="java",
            pairs=pairs,
            metadata={"labels_file": str(labels_path)},
        )

    def _instantiate_tool(self, tool_name: str) -> Any:
        """Instantiate a benchmark tool from the registry."""
        constructor = _tool_factories().get(tool_name)
        if constructor is None:
            raise ValueError(f"Unknown benchmark tool: {tool_name}")
        signature = inspect.signature(constructor)
        kwargs: dict[str, Any] = {}
        if "threshold" in signature.parameters:
            kwargs["threshold"] = self.threshold
        tool = constructor(**kwargs)

        if tool_name == "moss" and hasattr(tool, "_simulate_moss"):
            return _SimpleScoringTool(name=tool_name, scorer=tool._simulate_moss)
        if tool_name == "jplag" and hasattr(tool, "_simulate_jplag"):
            return _SimpleScoringTool(name=tool_name, scorer=tool._simulate_jplag)
        if tool_name == "dolos" and hasattr(tool, "_simulate_dolos"):
            return _SimpleScoringTool(name=tool_name, scorer=tool._simulate_dolos)
        if tool_name == "nicad" and hasattr(tool, "_simulate_nicad"):
            return _SimpleScoringTool(name=tool_name, scorer=tool._simulate_nicad)
        if tool_name == "pmd":
            return _SimpleScoringTool(name=tool_name, scorer=_token_overlap_score)

        return tool

    def _score_pair(self, tool: Any, pair: PANDatasetPair) -> tuple[float, dict[str, Any]]:
        """Run one pair through a tool and normalize its score."""
        metadata: dict[str, Any] = {}
        if hasattr(tool, "evaluate"):
            enriched_pair = EnrichedPair(
                pair_id=pair.pair_id,
                id_a=pair.suspicious_id,
                id_b=pair.source_id,
                code_a=pair.suspicious_code,
                code_b=pair.source_code,
                label=pair.label,
                clone_type=1 if pair.label else 0,
                difficulty=_difficulty_from_strength(pair.obfuscation_strength),
                language=pair.language,
                metadata=pair.metadata,
            )
            result = tool.evaluate(enriched_pair)
            score = float(getattr(result, "score", 0.0))
            metadata = dict(getattr(result, "metadata", {}) or {})
            metadata["engine"] = getattr(result, "engine", getattr(tool, "name", ""))
        elif hasattr(tool, "compare"):
            score = float(tool.compare(pair.suspicious_code, pair.source_code))
        else:
            raise TypeError(f"Tool does not expose evaluate() or compare(): {tool}")

        return max(0.0, min(1.0, score)), metadata

    def _ground_truth_detections(self, pair: PANDatasetPair) -> list[Detection]:
        """Create full-span ground truth detections for pairwise datasets."""
        if pair.label == 0:
            return []
        return [
            Detection(
                suspicious_span=TextSpan(0, len(pair.suspicious_code)),
                source_span=TextSpan(0, len(pair.source_code)),
            )
        ]

    def _predicted_detections(
        self,
        pair: PANDatasetPair,
        predicted: bool,
    ) -> list[Detection]:
        """Create predicted detections from a binary pair decision."""
        if not predicted:
            return []
        return [
            Detection(
                suspicious_span=TextSpan(0, len(pair.suspicious_code)),
                source_span=TextSpan(0, len(pair.source_code)),
            )
        ]

    def _compute_obfuscation_breakdown(
        self,
        dataset: PANDataset,
        records: list[PairEvaluationRecord],
    ) -> dict[str, dict[str, float]]:
        """Compute metrics for each obfuscation type."""
        breakdown: dict[str, dict[str, float]] = {}
        negative_ids = {
            pair.pair_id for pair in dataset.pairs if pair.label == 0
        }
        positive_types = sorted({
            pair.obfuscation_type
            for pair in dataset.pairs
            if pair.label == 1 and pair.obfuscation_type != "none"
        })
        for obfuscation_type in positive_types:
            included_pairs = {
                pair.pair_id
                for pair in dataset.pairs
                if pair.label == 0 or pair.obfuscation_type == obfuscation_type
            }
            subset_metrics = self._aggregate_subset(dataset, records, included_pairs)
            subset_metrics["support"] = sum(
                1
                for pair in dataset.pairs
                if pair.label == 1 and pair.obfuscation_type == obfuscation_type
            )
            subset_metrics["negative_support"] = len(negative_ids)
            breakdown[obfuscation_type] = subset_metrics
        return breakdown

    def _compute_strength_breakdown(
        self,
        dataset: PANDataset,
        records: list[PairEvaluationRecord],
    ) -> dict[str, dict[str, float]]:
        """Compute metrics for each obfuscation strength."""
        breakdown: dict[str, dict[str, float]] = {}
        strength_values = sorted({
            pair.obfuscation_strength
            for pair in dataset.pairs
            if pair.label == 1 and pair.obfuscation_strength > 0
        })
        for strength in strength_values:
            included_pairs = {
                pair.pair_id
                for pair in dataset.pairs
                if pair.label == 0 or pair.obfuscation_strength == strength
            }
            subset_metrics = self._aggregate_subset(dataset, records, included_pairs)
            subset_metrics["support"] = sum(
                1
                for pair in dataset.pairs
                if pair.label == 1 and pair.obfuscation_strength == strength
            )
            breakdown[str(strength)] = subset_metrics
        return breakdown

    def _aggregate_subset(
        self,
        dataset: PANDataset,
        records: list[PairEvaluationRecord],
        included_pairs: set[str],
    ) -> dict[str, float]:
        """Aggregate PAN metrics for a pair subset."""
        pair_lookup = {pair.pair_id: pair for pair in dataset.pairs}
        subset_metrics: list[PANMetrics] = []
        subset_ground_truth: list[list[Detection]] = []
        subset_predictions: list[list[Detection]] = []

        for record in records:
            if record.pair_id not in included_pairs:
                continue
            pair = pair_lookup[record.pair_id]
            ground_truth = self._ground_truth_detections(pair)
            predictions = self._predicted_detections(pair, record.predicted)
            subset_ground_truth.append(ground_truth)
            subset_predictions.append(predictions)
            subset_metrics.append(calculate_pan_metrics(ground_truth, predictions))

        aggregate = (
            pan_micro_average(subset_ground_truth, subset_predictions)
            if self.use_micro_average
            else pan_macro_average(subset_metrics)
        )
        return {
            "precision": round(aggregate.precision, 6),
            "recall": round(aggregate.recall, 6),
            "f1_score": round(aggregate.f1_score, 6),
            "granularity": round(aggregate.granularity, 6),
            "plagdet": round(aggregate.plagdet, 6),
        }

    def _cache_path(self, tool_name: str, dataset: PANDataset) -> Path:
        """Return the cache file path for one tool/dataset combination."""
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "tool": tool_name,
                    "dataset": dataset.name,
                    "signature": dataset.signature,
                    "threshold": self.threshold,
                    "micro": self.use_micro_average,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{tool_name}_{dataset.name}_{cache_key[:16]}.json"

    def _save_cached_result(self, cache_path: Path, result: PANBenchmarkResult) -> None:
        """Persist one result into the cache."""
        cache_path.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_cached_result(self, cache_path: Path) -> PANBenchmarkResult:
        """Load one cached result."""
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        pair_records = [
            PairEvaluationRecord(**record)
            for record in payload.get("pair_records", [])
        ]
        pan_metrics = PANMetrics(
            precision=float(payload["pan_metrics"]["precision"]),
            recall=float(payload["pan_metrics"]["recall"]),
            f1_score=float(payload["pan_metrics"]["f1_score"]),
            granularity=float(payload["pan_metrics"]["granularity"]),
            plagdet=float(payload["pan_metrics"]["plagdet"]),
        )
        return PANBenchmarkResult(
            tool_name=payload["tool_name"],
            dataset_name=payload["dataset_name"],
            total_pairs=int(payload["total_pairs"]),
            pan_metrics=pan_metrics,
            execution_time_seconds=float(payload["execution_time_seconds"]),
            pair_records=pair_records,
            obfuscation_breakdown=payload.get("obfuscation_breakdown", {}),
            strength_breakdown=payload.get("strength_breakdown", {}),
            metadata=payload.get("metadata", {}),
        )

    def _infer_obfuscation_type(self, code_a: str, code_b: str) -> str:
        """Infer the primary obfuscation type using the technique detector."""
        report = _summarize_obfuscation(code_a=code_a, code_b=code_b)
        return _primary_obfuscation_type(report)

    def _infer_strength(self, code_a: str, code_b: str) -> int:
        """Infer a comparable obfuscation strength from detected techniques."""
        report = _summarize_obfuscation(code_a=code_a, code_b=code_b)
        return _strength_from_report(report)

    @staticmethod
    def _read_code(path: Path) -> str:
        """Read one source file."""
        return path.read_text(encoding="utf-8", errors="replace")


def _tool_factories() -> dict[str, Any]:
    """Return the supported benchmark tools and their adapter classes."""
    tool_adapters = _load_tool_adapters_module()
    from src.backend.benchmark.adapters.external.pmd_adapter import PMDBenchmarkEngine

    return {
        "codeprovenance": tool_adapters.IntegrityDeskAdapter,
        "moss": tool_adapters.MOSSAdapter,
        "jplag": tool_adapters.JPlagAdapter,
        "dolos": tool_adapters.DolosAdapter,
        "nicad": tool_adapters.NiCadAdapter,
        "pmd": PMDBenchmarkEngine,
    }


def _primary_obfuscation_type(report: TechniqueSummary) -> str:
    """Map detailed technique detection to the requested benchmark categories."""
    mapping = {
        "rename": "rename",
        "reorder": "reorder",
        "control_flow": "control_flow",
    }
    if report.primary_technique in mapping:
        return mapping[report.primary_technique]
    if report.techniques:
        for technique in report.techniques:
            if technique.name in mapping:
                return mapping[technique.name]
    return "semantic"


def _strength_from_report(report: TechniqueSummary) -> int:
    """Convert technique complexity into a small strength scale."""
    type_name = _primary_obfuscation_type(report)
    baseline = {
        "rename": 1,
        "reorder": 2,
        "control_flow": 3,
        "semantic": 4,
    }[type_name]
    if report.complexity_score >= 0.80:
        return max(baseline, 4)
    if report.complexity_score >= 0.60:
        return max(baseline, 3)
    if report.complexity_score >= 0.40:
        return max(baseline, 2)
    return baseline


def _difficulty_from_strength(strength: int) -> str:
    """Map obfuscation strength onto the project's difficulty labels."""
    if strength <= 1:
        return "EASY"
    if strength == 2:
        return "MEDIUM"
    if strength in {3, 4}:
        return "HARD"
    return "EXPERT"


def _safe_mean(values: Iterable[float]) -> float:
    """Return the mean of an iterable or zero when empty."""
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def _summarize_obfuscation(code_a: str, code_b: str) -> TechniqueSummary:
    """Infer coarse obfuscation characteristics without optional dependencies."""
    techniques: list[TechniqueSignal] = []

    identifiers_a = _identifiers(code_a)
    identifiers_b = _identifiers(code_b)
    common_identifiers = identifiers_a & identifiers_b
    total_identifiers = len(identifiers_a | identifiers_b)
    rename_ratio = 0.0
    if total_identifiers:
        rename_ratio = 1.0 - (len(common_identifiers) / total_identifiers)
    if total_identifiers >= 4 and rename_ratio >= 0.45:
        techniques.append(TechniqueSignal(name="rename", confidence=rename_ratio))

    flow_a = _control_flow_tokens(code_a)
    flow_b = _control_flow_tokens(code_b)
    flow_overlap = _jaccard(flow_a, flow_b)
    if flow_a and flow_b and flow_overlap < 0.75:
        techniques.append(
            TechniqueSignal(name="control_flow", confidence=max(0.4, 1.0 - flow_overlap))
        )

    statements_a = _normalized_statements(code_a)
    statements_b = _normalized_statements(code_b)
    if (
        len(statements_a) >= 3
        and len(statements_a) == len(statements_b)
        and set(statements_a) == set(statements_b)
        and statements_a != statements_b
    ):
        techniques.append(TechniqueSignal(name="reorder", confidence=0.6))

    if not techniques:
        semantic_confidence = 0.5
        token_overlap = _jaccard(set(code_a.split()), set(code_b.split()))
        if token_overlap < 0.30:
            semantic_confidence = 0.8
        techniques.append(TechniqueSignal(name="semantic", confidence=semantic_confidence))

    primary = max(techniques, key=lambda item: item.confidence).name
    complexity_score = min(
        1.0,
        _safe_mean(signal.confidence for signal in techniques) + (0.1 * max(len(techniques) - 1, 0)),
    )
    return TechniqueSummary(
        primary_technique=primary,
        complexity_score=complexity_score,
        techniques=techniques,
    )


def _identifiers(code: str) -> set[str]:
    """Extract non-keyword identifiers."""
    keywords = {
        "abstract", "as", "assert", "break", "case", "catch", "class", "const",
        "continue", "def", "default", "do", "else", "enum", "except", "extends",
        "false", "final", "finally", "for", "function", "if", "implements",
        "import", "in", "interface", "lambda", "let", "new", "none", "null",
        "package", "pass", "private", "protected", "public", "raise", "return",
        "static", "super", "switch", "this", "throw", "true", "try", "var",
        "void", "while", "with", "yield",
    }
    return {
        token
        for token in re.findall(r"\b[a-zA-Z_]\w*\b", code)
        if token.lower() not in keywords
    }


def _control_flow_tokens(code: str) -> set[str]:
    """Extract control-flow markers."""
    return set(
        re.findall(
            r"\b(if|else|elif|for|while|switch|case|try|except|catch|break|continue)\b",
            code.lower(),
        )
    )


def _normalized_statements(code: str) -> list[str]:
    """Normalize statements for coarse ordering checks."""
    statements: list[str] = []
    for raw_line in code.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = re.sub(r"\b[a-zA-Z_]\w*\b", "__id__", line)
        normalized = re.sub(r"\b\d+\b", "0", normalized)
        statements.append(normalized)
    return statements


def _jaccard(left: set[str], right: set[str]) -> float:
    """Compute Jaccard similarity for small token sets."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _token_overlap_score(code_a: str, code_b: str) -> float:
    """Compute a lightweight token-overlap similarity."""
    tokens_a = set(re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|\S", code_a.lower()))
    tokens_b = set(re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|\S", code_b.lower()))
    return _jaccard(tokens_a, tokens_b)


def _fmt_metric(value: float) -> str:
    """Format a floating-point metric for markdown output."""
    return f"{value:.4f}"


def _granularity_penalty(granularity: float) -> float:
    """Return the PAN granularity penalty term."""
    if granularity <= 0.0:
        return 0.0
    return round(1.0 / max(granularity, 1.0), 4)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a markdown table."""
    if not rows:
        rows = [["-" for _ in headers]]
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        table.append("| " + " | ".join(row) + " |")
    return "\n".join(table)
