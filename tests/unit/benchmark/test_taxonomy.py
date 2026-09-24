"""Unit tests for the canonical benchmark taxonomy and coverage status.

The taxonomy must never claim a metric is measured unless the corresponding
artifact is actually present in the payload handed to
:func:`build_taxonomy_status`.
"""

from __future__ import annotations

import json

from src.backend.benchmark.taxonomy import (
    STATUS_GAP,
    STATUS_LIVE,
    STATUS_MISSING,
    STATUS_PARTIAL,
    build_taxonomy_status,
    taxonomy_summary,
)

GROUPED_METRICS = {
    "accuracy": 0.681,
    "precision": 0.7627,
    "recall": 0.2381,
    "f1": 0.3629,
    "fpr": 0.19,
    "auc": 0.6641,
    "pr_auc": 0.3124,
}

REPORTS = {"main": {"grouped_holdout": {"metrics": GROUPED_METRICS}}}
BASELINE = {
    "corpora": {
        "kaggle_student_code": {"count": 174},
        "poolc_sample": {"count": 40},
    }
}


def _component(components, key):
    """Return one component by key."""
    return next(component for component in components if component.key == key)


def _statuses(component) -> dict[str, str]:
    """Map item key to status for a component."""
    return {item.key: item.status for item in component.items}


class TestTaxonomyStructure:
    """The static tree must match the canonical four-part benchmark."""

    def test_four_components_in_canonical_order(self) -> None:
        components = build_taxonomy_status(REPORTS, BASELINE)
        assert [component.number for component in components] == [1, 2, 3, 4]
        assert [component.key for component in components] == [
            "detection_performance",
            "false_positive_validation",
            "robustness",
            "generalization",
        ]
        assert components[0].title == "Detection Performance"
        assert components[1].title == "False Positive Validation"

    def test_to_dict_is_json_serialisable(self) -> None:
        components = build_taxonomy_status(REPORTS, BASELINE)
        payload = [component.to_dict() for component in components]
        encoded = json.dumps(payload)
        assert "Real-World FPR Validation" in encoded
        detection = payload[0]["items"][0]
        assert detection["key"] == "tpr_recall"
        assert detection["status_label"] == "Measured"


class TestDetectionStatus:
    """§1 items are live only for metrics present in the report."""

    def test_all_live_when_every_metric_reported(self) -> None:
        component = _component(
            build_taxonomy_status(REPORTS, BASELINE), "detection_performance"
        )
        assert _statuses(component) == {
            "tpr_recall": STATUS_LIVE,
            "precision": STATUS_LIVE,
            "f1": STATUS_LIVE,
            "fpr_in_lab": STATUS_LIVE,
            "roc_auc": STATUS_LIVE,
            "pr_auc": STATUS_LIVE,
        }

    def test_missing_metric_is_reported_as_gap(self) -> None:
        reports = {
            "main": {
                "grouped_holdout": {
                    "metrics": {
                        k: v for k, v in GROUPED_METRICS.items() if k != "pr_auc"
                    }
                }
            }
        }
        component = _component(
            build_taxonomy_status(reports, BASELINE), "detection_performance"
        )
        assert _statuses(component)["pr_auc"] == STATUS_GAP

    def test_no_report_marks_detection_missing(self) -> None:
        component = _component(
            build_taxonomy_status(None, BASELINE), "detection_performance"
        )
        assert set(_statuses(component).values()) == {STATUS_MISSING}

    def test_empty_reports_mapping_marks_detection_missing(self) -> None:
        component = _component(build_taxonomy_status({}, None), "detection_performance")
        assert set(_statuses(component).values()) == {STATUS_MISSING}

    def test_report_without_grouped_metrics_is_not_live(self) -> None:
        components = build_taxonomy_status({"main": {"n_samples": 10}}, BASELINE)
        statuses = _statuses(_component(components, "detection_performance"))
        assert set(statuses.values()) == {STATUS_MISSING}


class TestRealWorldFprValidation:
    """§2b is driven by the tracked human-code baseline artifact."""

    def test_live_when_baseline_corpora_present(self) -> None:
        component = _component(
            build_taxonomy_status(REPORTS, BASELINE), "false_positive_validation"
        )
        item = next(i for i in component.items if i.key == "real_world_fpr_validation")
        assert item.status == STATUS_LIVE
        assert "n=214" in item.evidence
        assert "kaggle_student_code" in item.evidence

    def test_missing_without_baseline(self) -> None:
        component = _component(
            build_taxonomy_status(REPORTS, None), "false_positive_validation"
        )
        item = next(i for i in component.items if i.key == "real_world_fpr_validation")
        assert item.status == STATUS_MISSING

    def test_in_lab_fpr_tracks_detection_report(self) -> None:
        component = _component(
            build_taxonomy_status(REPORTS, BASELINE), "false_positive_validation"
        )
        assert _statuses(component)["synthetic_human_code"] == STATUS_LIVE


class TestHonestyOfGaps:
    """Robustness and generalization must not over-claim coverage."""

    def test_robustness_only_refactoring_is_partial(self) -> None:
        component = _component(build_taxonomy_status(REPORTS, BASELINE), "robustness")
        assert _statuses(component) == {
            "refactoring": STATUS_PARTIAL,
            "code_completion": STATUS_MISSING,
            "ai_assisted": STATUS_MISSING,
            "mixed_authorship": STATUS_MISSING,
        }

    def test_generalization_python_live_java_partial(self) -> None:
        component = _component(
            build_taxonomy_status(REPORTS, BASELINE), "generalization"
        )
        statuses = _statuses(component)
        assert statuses["python"] == STATUS_LIVE
        assert statuses["java"] == STATUS_PARTIAL
        assert statuses["c_cpp"] == STATUS_MISSING
        assert statuses["javascript"] == STATUS_MISSING

    def test_python_not_live_without_reports(self) -> None:
        component = _component(build_taxonomy_status(None, BASELINE), "generalization")
        assert _statuses(component)["python"] == STATUS_MISSING


class TestTaxonomySummary:
    """Summary counts must add up to the number of items in the tree."""

    def test_counts_match_items(self) -> None:
        components = build_taxonomy_status(REPORTS, BASELINE)
        summary = taxonomy_summary(components)
        total_items = sum(len(component.items) for component in components)
        assert sum(summary.values()) == total_items == 17
        assert summary[STATUS_LIVE] == 9
        assert summary[STATUS_PARTIAL] == 2
        assert summary[STATUS_MISSING] == 6

    def test_counts_without_artifacts_are_mostly_missing(self) -> None:
        summary = taxonomy_summary(build_taxonomy_status(None, None))
        assert summary[STATUS_LIVE] == 0
        assert summary[STATUS_PARTIAL] == 2
        assert summary[STATUS_MISSING] == 15

    def test_status_labels_are_present_for_every_status(self) -> None:
        from src.backend.benchmark.taxonomy import STATUS_LABELS

        for status in (STATUS_LIVE, STATUS_PARTIAL, STATUS_GAP, STATUS_MISSING):
            assert STATUS_LABELS[status]
