"""Benchmark runner pipelines for EvalForge v2."""

from __future__ import annotations

import concurrent.futures
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.backend.evalforge.core import BaseDetector, BenchmarkResult, CodePair
from src.backend.evalforge.core.dataset import Dataset
from src.backend.evalforge.core.metrics import compute_metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkRunner:
    """Core benchmark execution pipeline."""

    dataset: Dataset
    detectors: list[BaseDetector]
    max_workers: int = 4
    results: list[BenchmarkResult] = field(default_factory=list)

    def run(self) -> list[BenchmarkResult]:
        """Run benchmark on all detector-dataset pairs."""
        logger.info(
            f"Running benchmark on {len(self.dataset)} pairs with {len(self.detectors)} detectors"
        )

        results = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            futures = []

            for pair in self.dataset:
                for detector in self.detectors:
                    future = executor.submit(self._score_pair, pair, detector)
                    futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"Scoring failed: {e}")

        logger.info(f"Completed {len(results)} total evaluations")
        self.results = results
        return results

    def _score_pair(
        self, pair: CodePair, detector: BaseDetector
    ) -> BenchmarkResult | None:
        """Score a single pair with a single detector."""
        try:
            detection_result = detector.score(pair.code_a, pair.code_b)

            return BenchmarkResult(
                pair_id=pair.id,
                detector_name=detector.name,
                score=detection_result.score,
                confidence=detection_result.confidence,
                label=pair.label.value,
                transform_path=pair.transform_path,
                metadata={**detection_result.metadata, **pair.metadata},
            )
        except Exception as e:
            logger.debug(f"Failed to score {pair.id} with {detector.name}: {e}")
            return None

    def evaluate(self) -> dict[str, Any]:
        """Compute evaluation metrics for all detectors."""
        if not self.results:
            raise ValueError("No results available. Run benchmark first.")

        # Group results by detector
        detector_results = {}
        for result in self.results:
            detector_results.setdefault(result.detector_name, []).append(result)

        evaluation = {}

        for detector_name, results in detector_results.items():
            scores = [r.score for r in results]
            labels = [r.label for r in results]

            metrics = compute_metrics(scores, labels)
            evaluation[detector_name] = {
                "metrics": metrics,
                "n_pairs": len(results),
                "n_positive": sum(1 for r in results if r.is_positive_label),
                "n_negative": sum(1 for r in results if not r.is_positive_label),
            }

        # Add inter-detector agreement metrics
        evaluation["agreement"] = self._compute_agreement(detector_results)

        return evaluation

    def _compute_agreement(
        self, detector_results: dict[str, list[BenchmarkResult]]
    ) -> dict[str, Any]:
        """Compute inter-detector agreement metrics."""
        from scipy.stats import kendalltau, pearsonr

        detectors = list(detector_results.keys())
        agreement = {}

        if len(detectors) >= 2:
            # Compute pairwise correlations
            correlations = {}
            for i in range(len(detectors)):
                for j in range(i + 1, len(detectors)):
                    d1, d2 = detectors[i], detectors[j]

                    # Align results by pair_id
                    scores1 = []
                    scores2 = []

                    results1 = {r.pair_id: r for r in detector_results[d1]}
                    results2 = {r.pair_id: r for r in detector_results[d2]}

                    for pair_id, r1 in results1.items():
                        if pair_id in results2:
                            scores1.append(r1.score)
                            scores2.append(results2[pair_id].score)

                    if len(scores1) > 5:
                        pearson, _ = pearsonr(scores1, scores2)
                        kendall, _ = kendalltau(scores1, scores2)
                        correlations[f"{d1}_vs_{d2}"] = {
                            "pearson": round(pearson, 4),
                            "kendall": round(kendall, 4),
                            "n_pairs": len(scores1),
                        }

            agreement["pairwise_correlations"] = correlations

        return agreement

    def save_results(self, path: Path) -> None:
        """Save raw benchmark results to JSON."""
        data = {
            "dataset_name": self.dataset.name,
            "detectors": [d.name for d in self.detectors],
            "results": [
                {
                    "pair_id": r.pair_id,
                    "detector": r.detector_name,
                    "score": round(r.score, 4),
                    "confidence": round(r.confidence, 4),
                    "label": r.label,
                    "transform_path": r.transform_path,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_results(
        cls, path: Path, dataset: Dataset, detectors: list[BaseDetector]
    ) -> BenchmarkRunner:
        """Load saved benchmark results."""
        data = json.loads(path.read_text())

        results = []
        for r in data["results"]:
            results.append(
                BenchmarkResult(
                    pair_id=r["pair_id"],
                    detector_name=r["detector"],
                    score=r["score"],
                    confidence=r["confidence"],
                    label=r["label"],
                    transform_path=r["transform_path"],
                    metadata=r.get("metadata", {}),
                )
            )

        runner = cls(dataset=dataset, detectors=detectors)
        runner.results = results
        return runner


@dataclass
class Experiment:
    """Full experiment configuration and execution."""

    name: str
    dataset: Dataset
    detectors: list[BaseDetector]
    transformations: list[list[str]] | None = None
    max_workers: int = 8

    def run(self) -> dict[str, Any]:
        """Run full experiment with transformations."""
        logger.info(f"Starting experiment: {self.name}")

        experiment_results = {}

        # Run baseline (no transformations)
        logger.info("Running baseline benchmark")
        baseline_runner = BenchmarkRunner(
            self.dataset, self.detectors, self.max_workers
        )
        baseline_results = baseline_runner.run()
        baseline_eval = baseline_runner.evaluate()

        experiment_results["baseline"] = {
            "evaluation": baseline_eval,
            "results": baseline_results,
        }

        # Run robustness tests if transformations specified
        if self.transformations:
            experiment_results["robustness"] = []

            for transform_chain in self.transformations:
                logger.info(
                    f"Running robustness test with transformations: {transform_chain}"
                )

                transformed_dataset = self.dataset.apply_transformations(
                    transform_chain
                )
                runner = BenchmarkRunner(
                    transformed_dataset, self.detectors, self.max_workers
                )
                results = runner.run()
                eval_result = runner.evaluate()

                experiment_results["robustness"].append(
                    {
                        "transformations": transform_chain,
                        "evaluation": eval_result,
                        "results": results,
                    }
                )

        return experiment_results


def run_standard_benchmark(
    dataset_name: str, detectors: list[str] | None = None
) -> BenchmarkRunner:
    """Convenience function to run standard benchmark."""
    from src.backend.evalforge.detectors import get_all_detectors, get_detector

    if dataset_name == "poj104":
        dataset = Dataset.load_poj104()
    elif dataset_name == "bigclonebench":
        dataset = Dataset.load_bigclonebench()
    elif dataset_name.startswith("codesearchnet"):
        lang = dataset_name.split("_")[-1] if "_" in dataset_name else "python"
        dataset = Dataset.load_codesearchnet(lang)
    elif dataset_name == "codexglue_clone":
        dataset = Dataset.load_codexglue_clone()
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    if detectors:
        detector_instances = [
            d for d in [get_detector(name) for name in detectors] if d
        ]
    else:
        detector_instances = get_all_detectors()

    runner = BenchmarkRunner(dataset, detector_instances)
    runner.run()

    return runner
