"""Tests for the AI accuracy measurement tooling.

``scripts/measure_ai_accuracy.py`` and ``scripts/ab_fusion_strategies.py`` were
added after measuring the AI detector against AIGCodeSet. These tests pin the
statistics helpers, because an AUC or flag-rate helper that is subtly wrong
would silently produce flattering numbers for the detector.

See ``docs/AI_DETECTION_ACCURACY_FINDINGS.md`` for the measurements.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _load(module_name: str):
    """Import a script by path, since ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location(
        module_name, SCRIPTS / f"{module_name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestRocAuc:
    """ROC-AUC via the rank identity must handle the classic edge cases."""

    def test_perfect_separation(self) -> None:
        m = _load("measure_ai_accuracy")
        assert m._roc_auc([0.9, 0.8, 0.7], [0.1, 0.2, 0.3]) == pytest.approx(1.0)

    def test_inverted_separation(self) -> None:
        m = _load("measure_ai_accuracy")
        assert m._roc_auc([0.1, 0.2, 0.3], [0.7, 0.8, 0.9]) == pytest.approx(0.0)

    def test_all_ties_is_chance(self) -> None:
        m = _load("measure_ai_accuracy")
        assert m._roc_auc([0.5, 0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.5)

    def test_ties_are_averaged_not_broken(self) -> None:
        """A tied pair must count half a win, not a win or a loss.

        Signal scores collide constantly (many files read exactly 0.0), so
        getting tie handling wrong would bias every measurement.
        """
        m = _load("measure_ai_accuracy")
        # The single AI sample ties the single human sample.
        assert m._roc_auc([0.4], [0.4]) == pytest.approx(0.5)
        # positives [0.4, 0.9] vs negatives [0.4, 0.1]: 0.9 beats both (2 wins),
        # 0.4 ties 0.4 (0.5) and beats 0.1 (1 win) -> 3.5 / 4 = 0.875.
        assert m._roc_auc([0.4, 0.9], [0.4, 0.1]) == pytest.approx(0.875)

    def test_empty_class_is_nan(self) -> None:
        m = _load("measure_ai_accuracy")
        assert m._roc_auc([], [0.1]) != m._roc_auc([], [0.1])  # NaN


class TestRateAndSummary:
    def test_rate_at_is_inclusive(self) -> None:
        m = _load("measure_ai_accuracy")
        assert m._rate_at([0.39, 0.40, 0.41], 0.40) == pytest.approx(2 / 3)

    def test_summary_reports_shipped_bands(self) -> None:
        m = _load("measure_ai_accuracy")
        out = m._summarize([0.1, 0.5, 0.8])
        assert out["count"] == 3
        # _summarize rounds to 4 decimal places.
        assert out["rate_at_0.40"] == pytest.approx(2 / 3, abs=1e-4)
        assert out["rate_at_0.70"] == pytest.approx(1 / 3, abs=1e-4)
        assert out["max"] == pytest.approx(0.8)

    def test_empty_summary_has_no_rates(self) -> None:
        m = _load("measure_ai_accuracy")
        assert m._summarize([]) == {"count": 0}


class TestSubsampling:
    def test_subsample_is_deterministic(self) -> None:
        """Runs must be comparable across invocations, so sampling is seeded."""
        m = _load("measure_ai_accuracy")
        samples = [(f"f{i}.py", f"code {i}") for i in range(100)]
        first = m._subsample(samples, 20, 17)
        second = m._subsample(samples, 20, 17)
        assert first == second
        assert len(first) == 20

    def test_limit_zero_means_all(self) -> None:
        m = _load("measure_ai_accuracy")
        samples = [(f"f{i}.py", "x") for i in range(10)]
        assert len(m._subsample(samples, 0, 17)) == 10


class TestFusionABHarness:
    """The A/B harness must reproduce the pre-change fusion exactly.

    If these drift, the before/after comparison in the findings doc stops
    meaning "what changed".
    """

    def test_old_heuristic_fuse_matches_documented_formula(self) -> None:
        ab = _load("ab_fusion_strategies")
        zero = ab._old_heuristic_fuse(
            {
                "pattern_library": 0.0,
                "docstring_density": 0.0,
                "stylometry": 0.0,
                "burstiness": 0.0,
            }
        )
        # All four signals at 0.0 blend to raw 0.0. The sigmoid is centred on
        # raw == 0.5, so this lands far below the midpoint -- the origin of the
        # score compression documented in docs/AI_DETECTION_ACCURACY_FINDINGS.md.
        assert zero == pytest.approx(0.0474, abs=1e-3)

        # Signals averaging 0.5 (and the docstring boost firing at +0.18) clear
        # the midpoint, which is why high-AI evidence is where the scores live.
        strong = ab._old_heuristic_fuse(
            {
                "pattern_library": 0.5,
                "docstring_density": 0.5,
                "stylometry": 0.5,
                "burstiness": 0.5,
            }
        )
        assert strong > 0.5
        assert strong < 1.0

        strong = ab._old_heuristic_fuse(
            {
                "pattern_library": 0.60,
                "docstring_density": 0.80,
                "stylometry": 0.70,
                "burstiness": 0.60,
            }
        )
        assert strong > 0.8

    def test_old_weighted_fuse_is_an_unweighted_average(self) -> None:
        ab = _load("ab_fusion_strategies")
        weights = {"a": 0.5, "b": 0.5}
        out = ab._old_weighted_fuse({"a": 0.0, "b": 1.0}, weights)
        # raw 0.5 -> sigmoid midpoint, confirming it is a mean then a sigmoid.
        assert out == pytest.approx(0.5)

    def test_old_weighted_fuse_renormalizes_missing_signals(self) -> None:
        ab = _load("ab_fusion_strategies")
        weights = {"a": 0.5, "b": 0.5}
        out = ab._old_weighted_fuse({"a": 1.0}, weights)
        assert out > 0.5

    def test_statistics_mean_tolerates_empty(self) -> None:
        ab = _load("ab_fusion_strategies")
        assert ab.statistics_mean([]) != ab.statistics_mean([])  # NaN
        assert ab.statistics_mean([1.0, 3.0]) == pytest.approx(2.0)
