"""Unit tests for the AI detector accuracy-benchmark endpoint.

Verifies that ``/api/ai-detect/accuracy`` surfaces the real AIGCodeSet
benchmark numbers (grouped-holdout metrics including FPR/PR-AUC,
heuristic-vs-ML comparison, per-generator sensitivity, perplexity-source
comparison) with methodology, runtime and taxonomy-coverage disclosures, and
returns a data-unavailable payload when no report exists.
"""

import asyncio
import json
from unittest.mock import patch


from src.backend.api.server import (
    _read_ai_benchmark_report,
    get_ai_detection_accuracy,
)

MAIN_REPORT = {
    "n_samples": 7336,
    "n_ai": 2795,
    "grouped_holdout": {
        "metrics": {
            "accuracy": 0.681,
            "precision": 0.7627,
            "recall": 0.2381,
            "f1": 0.3629,
            "fpr": 0.1921,
            "auc": 0.6641,
            "pr_auc": 0.3124,
        }
    },
    "heuristic_comparison": {
        "heuristic_only": {"auc": 0.5241},
        "ml_classifier": {"auc": 0.6641},
    },
    "cross_llm": {"GEMINI": {"ai_samples": 191, "metrics": {"auc": 0.597}}},
}

STATISTICAL_REPORT = {"grouped_holdout": {"metrics": {"auc": 0.5451}}}
CODELM_REPORT = {"grouped_holdout": {"metrics": {"auc": 0.6299}}}


def _run_endpoint() -> dict:
    """Invoke the handler directly and return the parsed JSON body."""
    response = asyncio.run(get_ai_detection_accuracy())
    assert response.status_code == 200
    return json.loads(response.body)


class TestReadAIBenchmarkReport:
    """Tests for the report-file loader helper."""

    @patch("src.backend.api.server.AIGCODESET_REPORT_DIR")
    def test_missing_report_returns_none(self, report_dir) -> None:
        """A missing report file must not raise."""
        report_dir.joinpath.return_value.exists.return_value = False
        assert _read_ai_benchmark_report("benchmark_report.json") is None

    @patch("src.backend.api.server.AIGCODESET_REPORT_DIR")
    def test_invalid_json_returns_none(self, report_dir) -> None:
        """Unparsable report content must not raise."""
        path = report_dir.joinpath.return_value
        path.exists.return_value = True
        path.read_text.return_value = "not json"
        assert _read_ai_benchmark_report("benchmark_report.json") is None


class TestAIDetectionAccuracyEndpoint:
    """Tests for the accuracy-benchmark endpoint payload."""

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_returns_grouped_holdout_metrics(self, read_report) -> None:
        """The main report grouped-holdout numbers must be present."""
        body = _run_endpoint()
        assert body["available"] is True
        metrics = body["reports"]["main"]["grouped_holdout"]["metrics"]
        assert metrics["auc"] == 0.6641
        assert metrics["precision"] == 0.7627
        assert body["reports"]["main"]["n_samples"] == 7336

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_returns_heuristic_vs_ml(self, read_report) -> None:
        """The heuristic-vs-ML comparison must be surfaced."""
        body = _run_endpoint()
        cmp = body["reports"]["main"]["heuristic_comparison"]
        assert cmp["heuristic_only"]["auc"] == 0.5241
        assert cmp["ml_classifier"]["auc"] == 0.6641

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_returns_per_generator_sensitivity(self, read_report) -> None:
        """Per-generator sensitivity must be included."""
        body = _run_endpoint()
        assert body["reports"]["main"]["cross_llm"]["GEMINI"]["ai_samples"] == 191
        assert body["reports"]["main"]["cross_llm"]["GEMINI"]["metrics"]["auc"] == 0.597

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_returns_perplexity_source_comparison(self, read_report) -> None:
        """Both perplexity-source reports must be exposed."""
        body = _run_endpoint()
        assert (
            body["reports"]["statistical"]["grouped_holdout"]["metrics"]["auc"]
            == 0.5451
        )
        assert body["reports"]["codelm"]["grouped_holdout"]["metrics"]["auc"] == 0.6299

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: None,
    )
    def test_returns_unavailable_when_no_report(self, read_report) -> None:
        """Without any report the payload must say data is unavailable."""
        body = _run_endpoint()
        assert body["available"] is False
        assert body["reports"]["main"] is None

    def test_runtime_disclosures_present(self) -> None:
        """Runtime config disclosure must be present regardless of reports."""
        with patch(
            "src.backend.api.server._read_ai_benchmark_report",
            side_effect=lambda name: None,
        ):
            body = _run_endpoint()
        assert "ml_classifier_enabled" in body["runtime"]
        assert "perplexity_model" in body["runtime"]
        assert "methodology" in body

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_taxonomy_maps_four_components(self, read_report) -> None:
        """The response must carry the canonical four-part taxonomy tree."""
        body = _run_endpoint()
        taxonomy = body["taxonomy"]
        assert taxonomy["reference"] == "docs/CODEPROVENANCE_BENCHMARK.md"
        assert [c["number"] for c in taxonomy["components"]] == [1, 2, 3, 4]
        assert [c["key"] for c in taxonomy["components"]] == [
            "detection_performance",
            "false_positive_validation",
            "robustness",
            "generalization",
        ]

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_taxonomy_marks_reported_metrics_live(self, read_report) -> None:
        """Metrics present in the report must be surfaced as measured."""
        body = _run_endpoint()
        detection = body["taxonomy"]["components"][0]
        statuses = {item["key"]: item["status"] for item in detection["items"]}
        assert statuses["fpr_in_lab"] == "live"
        assert statuses["pr_auc"] == "live"
        assert statuses["tpr_recall"] == "live"
        assert all(item["status_label"] for item in detection["items"])

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: None,
    )
    def test_taxonomy_reports_gaps_without_artifacts(self, read_report) -> None:
        """With no report and no baseline the measurable items are all missing."""
        with patch(
            "src.backend.engines.ai.fp_baseline.load_human_fp_baseline",
            return_value={},
        ):
            body = _run_endpoint()
        summary = body["taxonomy"]["summary"]
        assert summary["live"] == 0
        assert summary["missing"] == 15
        assert summary["partial"] == 2

    @patch(
        "src.backend.api.server._read_ai_benchmark_report",
        side_effect=lambda name: {
            "benchmark_report.json": MAIN_REPORT,
            "benchmark_report.statistical.json": STATISTICAL_REPORT,
            "benchmark_report.codelm.json": CODELM_REPORT,
        }[name],
    )
    def test_taxonomy_surfaces_real_world_fpr_baseline(self, read_report) -> None:
        """§2b must be live when the tracked human baseline has corpora."""
        with patch(
            "src.backend.engines.ai.fp_baseline.load_human_fp_baseline",
            return_value={"corpora": {"kaggle_student_code": {"count": 174}}},
        ):
            body = _run_endpoint()
        fp_component = body["taxonomy"]["components"][1]
        items = {item["key"]: item for item in fp_component["items"]}
        assert items["real_world_fpr_validation"]["status"] == "live"
        assert "n=174" in items["real_world_fpr_validation"]["evidence"]
