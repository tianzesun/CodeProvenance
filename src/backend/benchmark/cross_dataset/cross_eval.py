"""Cross-dataset evaluation orchestrator.

Runs multiple tools across multiple datasets and produces structured
results showing per-dataset rankings, average performance, and
variance/stability analysis.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.backend.benchmark.cross_dataset.unified_format import UnifiedBenchmarkDataset
from src.backend.benchmark.cross_dataset.dataset_registry import DatasetRegistry
from src.backend.benchmark.cross_dataset.tool_adapters import ToolAdapter
from src.backend.benchmark.cross_dataset.eval_runner import EvaluationRunner, EvaluationResult


@dataclass
class DatasetRanking:
    """Tool rankings for a single dataset."""
    dataset_name: str
    rankings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset_name,
            "rankings": self.rankings,
        }


@dataclass
class ToolAggregateStats:
    """Aggregate performance of a tool across all datasets."""
    tool_name: str
    mean_f1: float = 0.0
    mean_precision: float = 0.0
    mean_recall: float = 0.0
    mean_roc_auc: float = 0.0
    mean_pr_auc: float = 0.0
    std_f1: float = 0.0
    std_precision: float = 0.0
    std_recall: float = 0.0
    std_roc_auc: float = 0.0
    std_pr_auc: float = 0.0
    min_f1: float = 0.0
    max_f1: float = 0.0
    datasets_evaluated: int = 0
    per_dataset: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool_name,
            "mean_f1": round(self.mean_f1, 4),
            "mean_precision": round(self.mean_precision, 4),
            "mean_recall": round(self.mean_recall, 4),
            "mean_roc_auc": round(self.mean_roc_auc, 4),
            "mean_pr_auc": round(self.mean_pr_auc, 4),
            "std_f1": round(self.std_f1, 4),
            "std_precision": round(self.std_precision, 4),
            "std_recall": round(self.std_recall, 4),
            "std_roc_auc": round(self.std_roc_auc, 4),
            "std_pr_auc": round(self.std_pr_auc, 4),
            "min_f1": round(self.min_f1, 4),
            "max_f1": round(self.max_f1, 4),
            "datasets_evaluated": self.datasets_evaluated,
            "per_dataset": {
                k: {mk: round(mv, 4) for mk, mv in v.items()}
                for k, v in self.per_dataset.items()
            },
        }


@dataclass
class CrossEvalReport:
    """Complete cross-dataset evaluation report."""
    timestamp: str = ""
    num_datasets: int = 0
    num_tools: int = 0
    per_dataset_rankings: List[DatasetRanking] = field(default_factory=list)
    tool_aggregates: List[ToolAggregateStats] = field(default_factory=list)
    all_results: List[EvaluationResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "num_datasets": self.num_datasets,
            "num_tools": self.num_tools,
            "per_dataset_rankings": [r.to_dict() for r in self.per_dataset_rankings],
            "tool_aggregates": [a.to_dict() for a in self.tool_aggregates],
            "all_results": [r.to_dict() for r in self.all_results],
            "metadata": self.metadata,
        }

    def save(self, path: str) -> str:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return str(out)

    def print_summary(self) -> None:
        print("\n" + "=" * 72)
        print("  CROSS-DATASET BENCHMARK REPORT")
        print("=" * 72)
        print(f"  Datasets: {self.num_datasets}")
        print(f"  Tools:    {self.num_tools}")
        print(f"  Time:     {self.timestamp}")
        print("=" * 72)

        print("\n--- Per-Dataset Rankings (by F1) ---")
        for dr in self.per_dataset_rankings:
            print(f"\n  [{dr.dataset_name}]")
            for rank, entry in enumerate(dr.rankings, 1):
                print(
                    f"    {rank}. {entry['tool']:20s}  "
                    f"F1={entry['f1']:.4f}  "
                    f"P={entry['precision']:.4f}  "
                    f"R={entry['recall']:.4f}  "
                    f"ROC-AUC={entry['roc_auc']:.4f}  "
                    f"PR-AUC={entry['pr_auc']:.4f}"
                )

        print("\n--- Aggregate Tool Performance ---")
        print(
            f"  {'Tool':20s} {'Mean F1':>8s} {'Std F1':>8s} "
            f"{'Min F1':>8s} {'Max F1':>8s} {'Mean ROC':>8s} "
            f"{'Mean PR':>8s} {'Datasets':>8s}"
        )
        print("  " + "-" * 88)
        for agg in sorted(self.tool_aggregates, key=lambda a: a.mean_f1, reverse=True):
            print(
                f"  {agg.tool_name:20s} {agg.mean_f1:8.4f} {agg.std_f1:8.4f} "
                f"{agg.min_f1:8.4f} {agg.max_f1:8.4f} "
                f"{agg.mean_roc_auc:8.4f} {agg.mean_pr_auc:8.4f} "
                f"{agg.datasets_evaluated:8d}"
            )
        print("=" * 72 + "\n")


class CrossDatasetEvaluator:
    """Orchestrates cross-dataset evaluation.

    Usage:
        evaluator = CrossDatasetEvaluator()
        evaluator.register_dataset("mydata", loader_fn)
        evaluator.register_tool("mytool", tool_adapter)
        report = evaluator.run(threshold=0.5)
    """

    def __init__(self, registry: Optional[DatasetRegistry] = None):
        self._registry = registry or DatasetRegistry.get_instance()
        self._tools: Dict[str, ToolAdapter] = {}
        self._dataset_names: List[str] = []
        self._tool_names: List[str] = []
        self._eval_runner = EvaluationRunner()

    def register_dataset(
        self,
        name: str,
        loader: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._registry.register(name, loader, metadata)
        if name not in self._dataset_names:
            self._dataset_names.append(name)

    def register_tool(self, name: str, tool: ToolAdapter) -> None:
        self._tools[name] = tool
        if name not in self._tool_names:
            self._tool_names.append(name)

    def register_tool_from_engine(self, engine, name: Optional[str] = None, **kwargs) -> None:
        from src.backend.benchmark.cross_dataset.tool_adapters import EngineToolAdapter
        adapter = EngineToolAdapter(engine, name=name, **kwargs)
        self.register_tool(adapter.name, adapter)

    def run(
        self,
        dataset_names: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
        threshold: float = 0.5,
        optimize_thresholds: bool = False,
        threshold_strategy: str = "f1_max",
        output_path: Optional[str] = None,
        verbose: bool = True,
    ) -> CrossEvalReport:
        if dataset_names is None:
            dataset_names = self._dataset_names or self._registry.list_datasets()
        if tool_names is None:
            tool_names = self._tool_names

        all_results: List[EvaluationResult] = []
        per_dataset: Dict[str, List[EvaluationResult]] = {
            ds: [] for ds in dataset_names
        }

        total = len(dataset_names) * len(tool_names)
        done = 0

        for ds_name in dataset_names:
            if verbose:
                print(f"\nLoading dataset: {ds_name}")
            try:
                dataset = self._registry.load(ds_name)
            except Exception as e:
                print(f"  SKIP: {ds_name} - {e}")
                continue

            if len(dataset) == 0:
                print(f"  SKIP: {ds_name} - empty dataset")
                continue

            for t_name in tool_names:
                if t_name not in self._tools:
                    continue
                tool = self._tools[t_name]

                current_threshold = threshold
                if optimize_thresholds:
                    scores = []
                    labels = []
                    for pair in dataset.pairs:
                        scores.append(tool.compare(pair.code_a, pair.code_b))
                        labels.append(pair.label)
                    current_threshold, _ = self._eval_runner.find_optimal_threshold(
                        scores, labels, strategy=threshold_strategy,
                    )

                if verbose:
                    print(f"  Running {t_name} on {ds_name} (threshold={current_threshold:.2f})...")

                result = self._eval_runner.evaluate(
                    dataset=dataset,
                    tool=tool,
                    threshold=current_threshold,
                )
                all_results.append(result)
                per_dataset[ds_name].append(result)
                done += 1

                if verbose:
                    print(
                        f"    F1={result.f1:.4f}  "
                        f"P={result.precision:.4f}  "
                        f"R={result.recall:.4f}  "
                        f"ROC-AUC={result.roc_auc:.4f}  "
                        f"PR-AUC={result.pr_auc:.4f}"
                    )

        report = self._build_report(
            dataset_names=dataset_names,
            tool_names=tool_names,
            all_results=all_results,
            per_dataset=per_dataset,
        )

        if output_path:
            report.save(output_path)
            if verbose:
                print(f"\nReport saved to: {output_path}")

        if verbose:
            report.print_summary()

        return report

    def _build_report(
        self,
        dataset_names: List[str],
        tool_names: List[str],
        all_results: List[EvaluationResult],
        per_dataset: Dict[str, List[EvaluationResult]],
    ) -> CrossEvalReport:
        from datetime import datetime

        per_dataset_rankings: List[DatasetRanking] = []
        for ds_name in dataset_names:
            results = per_dataset.get(ds_name, [])
            ranked = sorted(results, key=lambda r: r.f1, reverse=True)
            rankings = []
            for r in ranked:
                rankings.append({
                    "tool": r.tool_name,
                    "f1": r.f1,
                    "precision": r.precision,
                    "recall": r.recall,
                    "accuracy": r.accuracy,
                    "roc_auc": r.roc_auc,
                    "pr_auc": r.pr_auc,
                    "threshold": r.threshold,
                })
            per_dataset_rankings.append(
                DatasetRanking(dataset_name=ds_name, rankings=rankings)
            )

        tool_aggregates = self._compute_aggregates(all_results, tool_names)

        report = CrossEvalReport(
            timestamp=datetime.now().isoformat(),
            num_datasets=len(dataset_names),
            num_tools=len(tool_names),
            per_dataset_rankings=per_dataset_rankings,
            tool_aggregates=tool_aggregates,
            all_results=all_results,
        )
        return report

    def _compute_aggregates(
        self,
        all_results: List[EvaluationResult],
        tool_names: List[str],
    ) -> List[ToolAggregateStats]:
        tool_results: Dict[str, List[EvaluationResult]] = {
            t: [] for t in tool_names
        }
        for r in all_results:
            if r.tool_name in tool_results:
                tool_results[r.tool_name].append(r)

        aggregates = []
        for t_name in tool_names:
            results = tool_results.get(t_name, [])
            if not results:
                continue

            f1s = [r.f1 for r in results]
            precs = [r.precision for r in results]
            recs = [r.recall for r in results]
            rocs = [r.roc_auc for r in results]
            prs = [r.pr_auc for r in results]

            per_ds = {}
            for r in results:
                per_ds[r.dataset_name] = {
                    "f1": r.f1,
                    "precision": r.precision,
                    "recall": r.recall,
                    "roc_auc": r.roc_auc,
                    "pr_auc": r.pr_auc,
                }

            agg = ToolAggregateStats(
                tool_name=t_name,
                mean_f1=float(np.mean(f1s)),
                mean_precision=float(np.mean(precs)),
                mean_recall=float(np.mean(recs)),
                mean_roc_auc=float(np.mean(rocs)),
                mean_pr_auc=float(np.mean(prs)),
                std_f1=float(np.std(f1s)),
                std_precision=float(np.std(precs)),
                std_recall=float(np.std(recs)),
                std_roc_auc=float(np.std(rocs)),
                std_pr_auc=float(np.std(prs)),
                min_f1=float(np.min(f1s)),
                max_f1=float(np.max(f1s)),
                datasets_evaluated=len(results),
                per_dataset=per_ds,
            )
        aggregates.append(agg)

        return aggregates

    def run_significance_tests(self, alpha: float = 0.05) -> List[Dict[str, Any]]:
        """Run pairwise McNemar significance tests between all tools."""
        try:
            from scipy import stats
        except ImportError:
            return []
        import itertools

        tool_names = list(self._tools.keys())
        results = []

        for t1, t2 in itertools.combinations(tool_names, 2):
            preds_t1 = []
            preds_t2 = []

            for ds_name in self._registry.list_datasets():
                try:
                    ds = self._registry.load(ds_name)
                except Exception:
                    continue
                if len(ds) == 0:
                    continue

                t1_obj = self._tools[t1]
                t2_obj = self._tools[t2]

                for pair in ds.pairs:
                    code_a = getattr(pair, "code_a", "")
                    code_b = getattr(pair, "code_b", "")
                    s1 = t1_obj.compare(code_a, code_b)
                    s2 = t2_obj.compare(code_a, code_b)
                    preds_t1.append(1 if s1 >= 0.5 else 0)
                    preds_t2.append(1 if s2 >= 0.5 else 0)

            if len(preds_t1) < 10:
                continue

            b01 = sum(1 for a, b in zip(preds_t1, preds_t2) if a == 1 and b == 0)
            b10 = sum(1 for a, b in zip(preds_t1, preds_t2) if a == 0 and b == 1)

            if b01 + b10 == 0:
                p_val = 1.0
                chi2 = 0.0
            else:
                chi2 = (abs(b01 - b10) - 1) ** 2 / (b01 + b10)
                p_val = 1.0 - stats.chi2.cdf(chi2, 1)

            results.append({
                "tool_a": t1,
                "tool_b": t2,
                "b01": b01,
                "b10": b10,
                "chi2": round(chi2, 4),
                "p_value": round(p_val, 4),
                "significant": p_val < alpha,
                "n_pairs": len(preds_t1),
            })

        return results
