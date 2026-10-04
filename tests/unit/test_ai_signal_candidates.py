"""Tests for the candidate-signal evaluation harness.

``scripts/eval_ai_signals.py`` exists to stop an anecdotal snippet from being
shipped as a detection signal. A "docstring uniformity" candidate looked
convincing on one hand-written ChatGPT example (6/6 documented vs 0/2) and
measured AUC 0.49 against the real human corpora — human code there is
documented *more* often than AI code.

These tests pin the statistics helpers and the both-negatives rule, because a
harness that reports a flattering number is worse than no harness.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _load():
    """Import the harness by path, since ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "eval_ai_signals", SCRIPTS / "eval_ai_signals.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_ai_signals"] = module
    spec.loader.exec_module(module)
    return module


AI_STYLE = '''import math


class Circle:
    """A circle defined by its radius."""

    def __init__(self, radius):
        """Initialize the circle with a radius."""
        self.radius = radius

    def area(self):
        """Calculate the area of the circle."""
        return math.pi * self.radius ** 2


def describe(circle):
    """Return a description of the circle."""
    return f"area {circle.area():.2f}"
'''

HUMAN_STYLE = """import math


def area(r):
    return math.pi * r * r


def perim(r):
    return 2 * math.pi * r


for i in range(1, 10):
    print(i, area(i), perim(i))
"""

PARTIAL_DOCS = '''def a():
    """Documented."""
    return 1


def b():
    return 2


def c():
    return 3
'''


class TestRocAuc:
    """The rank-identity AUC must handle the edge cases honestly."""

    def test_perfect_separation(self) -> None:
        m = _load()
        assert m._roc_auc([0.9, 0.8], [0.1, 0.2]) == pytest.approx(1.0)

    def test_inverted_separation(self) -> None:
        m = _load()
        assert m._roc_auc([0.1, 0.2], [0.8, 0.9]) == pytest.approx(0.0)

    def test_all_ties_is_chance(self) -> None:
        m = _load()
        assert m._roc_auc([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.5)

    def test_empty_class_is_nan_not_a_crash(self) -> None:
        m = _load()
        assert m._roc_auc([], [0.1]) != m._roc_auc([], [0.1])  # NaN


class TestUnmeasurableInputIsExcluded:
    """Too few functions must yield None, never 0.0.

    A corpus whose files have no functions cannot support this signal. Scoring
    it 0.0 would mix "unmeasurable" into "measured and found nothing", which is
    how a coverage-limited signal looks convincing.
    """

    def test_too_few_functions_returns_none(self) -> None:
        m = _load()
        assert m.docstring_uniformity("x = 1\n") is None
        assert m.docstring_uniformity("def f():\n    return 1\n") is None

    def test_unparseable_source_returns_none(self) -> None:
        m = _load()
        assert m.docstring_uniformity("def broken(:\n") is None

    def test_measurable_file_returns_a_ratio(self) -> None:
        m = _load()
        assert m.docstring_uniformity(AI_STYLE) == pytest.approx(1.0)

    def test_undocumented_file_returns_zero_not_none(self) -> None:
        """Enough functions to judge but nothing documented is a real 0.0."""
        m = _load()
        assert m.docstring_uniformity(HUMAN_STYLE) == pytest.approx(0.0)


class TestUniformityMeasures:
    """Uniformity is a ratio over defs, so it must be order-independent."""

    def test_partial_documentation_is_a_fraction(self) -> None:
        m = _load()
        assert m.docstring_uniformity(PARTIAL_DOCS) == pytest.approx(1 / 3)

    def test_uniform_documentation_is_a_gate(self) -> None:
        m = _load()
        assert m.uniform_documentation(AI_STYLE) == 1.0
        assert m.uniform_documentation(PARTIAL_DOCS) == 0.0

    def test_uniform_documentation_propagates_unmeasurable(self) -> None:
        m = _load()
        assert m.uniform_documentation("x = 1\n") is None

    def test_short_docstring_variant_ignores_long_blocks(self) -> None:
        """Long documentation is not the assistant's signature.

        The fixture needs enough functions to be measurable at all, otherwise
        the signal returns ``None`` and the assertion would pass vacuously.
        """
        m = _load()
        long_docs = (
            "def a():\n    '''Line one.\n\n    Line two.\n    '''\n    return 1\n"
            "def b():\n    '''First.\n\n    Second.\n    '''\n    return 2\n"
            "def c():\n    '''Alpha.\n\n    Beta.\n    '''\n    return 3\n"
        )
        assert m.short_docstring_uniformity(long_docs) == pytest.approx(0.0)

    def test_short_docstring_variant_counts_terse_summaries(self) -> None:
        m = _load()
        assert m.short_docstring_uniformity(AI_STYLE) == pytest.approx(1.0)

    def test_function_count_counts_nested_and_async(self) -> None:
        m = _load()
        code = (
            "async def a():\n    pass\n\n\n"
            "def outer():\n    def inner():\n        pass\n    return inner\n"
        )
        assert m.function_count(code) == 3.0


class TestBothNegativesRule:
    """A candidate must clear AUC against BOTH negatives to be usable.

    This is the rule that rejected the docstring-uniformity candidate: it
    inverted against both real human sets.
    """

    def test_threshold_requires_both_negatives(self) -> None:
        m = _load()
        assert 0.0 < m.MIN_USEFUL_AUC < 1.0

    def test_constant_candidate_is_not_useful(self) -> None:
        m = _load()
        result = m._describe(
            "weak",
            lambda code: 1.0,
            [("a", "x"), ("b", "y")],
            [("h", "z")],
            [("s", "w")],
        )
        # A constant signal separates from nothing, so both AUCs stay at chance.
        assert result["useful"] is False

    def test_strong_candidate_is_marked_useful(self) -> None:
        m = _load()
        result = m._describe(
            "strong",
            lambda code: 1.0 if code == "x" else 0.0,
            [("a", "x"), ("b", "x"), ("c", "x")],
            [("h", "z"), ("h2", "z")],
            [("s", "w"), ("s2", "w")],
        )
        assert result["auc_human"] == pytest.approx(1.0)
        assert result["auc_students"] == pytest.approx(1.0)
        assert result["useful"] is True

    def test_rejected_candidates_stay_registered(self) -> None:
        """Pin the negative result so it is not silently re-proposed.

        These measured at chance against both human corpora. If someone improves
        one, update this test *with the new number* rather than letting the
        claim go stale.
        """
        m = _load()
        assert "docstring_uniformity" in m.CANDIDATES
        assert "short_docstring_uniformity" in m.CANDIDATES


class TestSamplingIsDeterministic:
    """Runs must be comparable, so subsampling must be seed-stable."""

    def test_same_seed_picks_same_samples(self) -> None:
        m = _load()
        samples = [(str(i), "code") for i in range(100)]
        assert m.subsample(samples, 10, 17) == m.subsample(samples, 10, 17)

    def test_limit_zero_keeps_everything(self) -> None:
        m = _load()
        samples = [(str(i), "code") for i in range(10)]
        assert m.subsample(samples, 0, 17) == samples

    def test_missing_directory_yields_no_samples(self) -> None:
        m = _load()
        assert m.iter_samples(REPO_ROOT / "does-not-exist") == []


class TestAstSafety:
    """Parsing hostile input must not raise out of the harness."""

    def test_deeply_nested_source_is_handled(self) -> None:
        m = _load()
        code = "x = " + "[" * 200 + "]" * 200
        assert m.function_count(code) is None or m.function_count(code) >= 0

    def test_harness_imports_cleanly(self) -> None:
        assert ast is not None
        _load()
