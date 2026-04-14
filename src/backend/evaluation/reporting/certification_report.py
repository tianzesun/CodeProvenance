from __future__ import annotations

import json
import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any

from jinja2 import Environment, FileSystemLoader

# Your internal modules
from evaluation.statistics.statistical_tests import (
    bootstrap_confidence_interval,
    paired_bootstrap_test,
)
from contracts.reproducibility import compute_reproducibility_hash


# =========================
# Contracts (STRICT)
# =========================

@dataclass(frozen=True)
class SystemMetrics:
    name: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float


@dataclass(frozen=True)
class SystemPredictions:
    name: str
    scores: List[float]          # probability or similarity score
    predictions: List[int]      # binary decisions
    labels: List[int]           # ground truth


@dataclass(frozen=True)
class ReportConfig:
    report_version: str
    dataset_name: str
    dataset_version: str
    output_dir: str
    template_dir: str
    confidence: float = 0.95
    seed: int = 42


# =========================
# Core Generator
# =========================

class CertificationReportGenerator:
    def __init__(self, config: ReportConfig):
        self.config = config
        self.env = Environment(
            loader=FileSystemLoader(config.template_dir),
            autoescape=True
        )

    # -------------------------
    # Public API
    # -------------------------

    def generate(
        self,
        metrics: List[SystemMetrics],
        predictions: List[SystemPredictions],
        reproducibility_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main entrypoint.
        Returns report_data (also written to disk).
        """
        self._validate_inputs(metrics, predictions)

        reproducibility = compute_reproducibility_hash(reproducibility_inputs)

        confidence_intervals = self._compute_confidence(predictions)
        significance_tests = self._compute_significance(predictions)

        report_data = {
            "report_version": self.config.report_version,
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "dataset_name": self.config.dataset_name,
            "dataset_version": self.config.dataset_version,
            "reproducibility_hash": reproducibility["combined_hash"],
            "metrics": [asdict(m) for m in metrics],
            "confidence_intervals": confidence_intervals,
            "significance_tests": significance_tests,
            "calibration": self._compute_calibration(predictions),
            "stratified": [],  # placeholder for future extension
            "reproducibility": reproducibility,
        }

        self._write_outputs(report_data)

        return report_data

    # -------------------------
    # Validation
    # -------------------------

    def _validate_inputs(
        self,
        metrics: List[SystemMetrics],
        predictions: List[SystemPredictions],
    ):
        if not metrics or not predictions:
            raise ValueError("Metrics and predictions cannot be empty")

        names_m = {m.name for m in metrics}
        names_p = {p.name for p in predictions}

        if names_m != names_p:
            raise ValueError("Mismatch between metrics and prediction systems")

    # -------------------------
    # Confidence Intervals
    # -------------------------

    def _compute_confidence(self, predictions: List[SystemPredictions]):
        results = []

        for p in predictions:
            ci = bootstrap_confidence_interval(
                p.scores,
                confidence=self.config.confidence,
                seed=self.config.seed,
            )

            results.append({
                "name": p.name,
                "metric": "score",
                "mean": round(ci.mean, 4),
                "lower": round(ci.lower, 4),
                "upper": round(ci.upper, 4),
            })

        return results

    # -------------------------
    # Significance Tests
    # -------------------------

    def _compute_significance(self, predictions: List[SystemPredictions]):
        if len(predictions) < 2:
            return []

        baseline = predictions[0]
        results = []

        for other in predictions[1:]:
            test = paired_bootstrap_test(
                baseline.scores,
                other.scores,
                seed=self.config.seed,
                confidence=self.config.confidence,
            )

            results.append({
                "name": f"{baseline.name} vs {other.name}",
                "delta": round(test.delta, 4),
                "p_value": round(test.p_value, 6),
                "significant": test.significant,
            })

        return results

    # -------------------------
    # Calibration (ECE)
    # -------------------------

    def _compute_calibration(self, predictions: List[SystemPredictions]):
        # Only evaluate first system (primary)
        p = predictions[0]

        scores = p.scores
        labels = p.labels

        bins = 10
        bin_size = 1.0 / bins

        total = len(scores)
        ece = 0.0

        for i in range(bins):
            lower = i * bin_size
            upper = (i + 1) * bin_size

            bin_indices = [
                idx for idx, s in enumerate(scores)
                if lower <= s < upper
            ]

            if not bin_indices:
                continue

            avg_conf = sum(scores[i] for i in bin_indices) / len(bin_indices)
            avg_acc = sum(labels[i] for i in bin_indices) / len(bin_indices)

            ece += (len(bin_indices) / total) * abs(avg_conf - avg_acc)

        return {"ece": round(ece, 6)}

    # -------------------------
    # Output Writers
    # -------------------------

    def _write_outputs(self, report_data: Dict[str, Any]):
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON (machine-readable)
        json_path = output_dir / "certification_report.json"
        with open(json_path, "w") as f:
            json.dump(report_data, f, indent=2)

        # HTML (publication)
        template = self.env.get_template("certification_report.html")
        html = template.render(**report_data)

        html_path = output_dir / "certification_report.html"
        with open(html_path, "w") as f:
            f.write(html)

        print(f"[OK] Report generated:")
        print(f" - {json_path}")
        print(f" - {html_path}")
