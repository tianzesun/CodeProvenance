"""Performance and equivalence tests for stylometry extraction on large files.

AI detection was slow on large submissions (a 40k-line file spent ~16s inside
``StylometryExtractor.extract``). Two defects caused it:

* the module walked the AST **five** times (once to gather features, then again
  for classes, imports, ``if`` count and boolean-op count);
* ``_compute_nesting_depth`` recursed once per function over that function's
  whole subtree, which spent most of its budget on Python call overhead.

Both are now a single walk plus an explicit stack. These tests pin the two
properties that matter: the features are **unchanged**, and the traversal count
actually dropped - so a future edit cannot quietly reintroduce the cost.
"""

from __future__ import annotations

import ast
import time

from src.backend.engines.features.code_stylometry import StylometryExtractor


def synth(lines: int) -> str:
    """Build valid Python of roughly *lines* lines in a consistent style."""
    out: list[str] = ["import math", "import sys", ""]
    made = 2
    index = 0
    while made < lines:
        out.append("")
        out.append(f"def function_{index}(a, b):")
        out.append(f'    """Compute the result of function {index}."""')
        made += 3
        for k in range(8):
            out.append(f"    value_{k} = a * {k} + b - {made}")
            made += 1
        out.append("    return " + " + ".join(f"value_{k}" for k in range(8)))
        made += 1
        index += 1
    return "\n".join(out[:lines]) + "\n"


NESTED = '''
class Outer:
    """A container."""

    def run(self, data):
        """Run the thing."""
        for item in data:
            if item:
                while item:
                    try:
                        with item as handle:
                            if handle:
                                return handle
                    except ValueError:
                        pass
        return None
'''


class TestNestingDepth:
    """The iterative depth walk must match the recursive definition exactly."""

    def test_counts_only_compound_statements(self) -> None:
        extractor = StylometryExtractor()
        features = extractor.extract(NESTED)

        # for > if > while > try > with > if == 6 levels of compound nesting.
        assert features.avg_nesting_depth == 6.0

    def test_flat_code_has_zero_depth(self) -> None:
        extractor = StylometryExtractor()
        features = extractor.extract("def f(a):\n    return a + 1\n")

        assert features.avg_nesting_depth == 0.0

    def test_empty_body_is_safe(self) -> None:
        """A function with an empty body must not raise."""
        extractor = StylometryExtractor()

        assert extractor.extract("def f():\n    pass\n") is not None


class TestSingleTraversal:
    """The AST must be walked once, not once per derived count."""

    def test_walk_is_called_once_per_extract(self, monkeypatch) -> None:
        calls: list[int] = []
        original = ast.walk

        def counting_walk(node):
            """Count invocations of the module-level ``ast.walk``."""
            calls.append(1)
            return original(node)

        monkeypatch.setattr(ast, "walk", counting_walk)
        StylometryExtractor().extract(NESTED)

        assert len(calls) == 1

    def test_features_survive_the_single_walk(self) -> None:
        """Counts derived from the cached walk must still be populated."""
        features = StylometryExtractor().extract(NESTED)

        assert features.num_classes == 1
        assert features.num_functions == 1
        assert features.has_try_except is True


class TestLargeFileCost:
    """A large file must extract without super-linear cost."""

    @staticmethod
    def _time_extract(lines: int) -> float:
        """Return seconds to extract *lines* of synthetic code."""
        extractor = StylometryExtractor()
        start = time.perf_counter()
        extractor.extract(synth(lines))
        return time.perf_counter() - start

    def test_scales_sub_quadratically(self) -> None:
        """Quadrupling the input must not cost anywhere near 16x.

        A relative bound is used rather than an absolute wall-clock threshold:
        an absolute one turns into a flaky test whenever the machine is busy,
        which is exactly when nobody wants a red build. The old recursive
        nesting-depth walk made this ratio quadratic; a single traversal keeps
        it roughly linear.
        """
        # Warm up so first-call import/caching cost is not counted as scaling.
        self._time_extract(2_000)

        small = self._time_extract(5_000)
        large = self._time_extract(20_000)

        assert small > 0
        ratio = large / small
        # 4x the input. Linear ~4x, quadratic ~16x; 10x leaves generous headroom
        # for scheduler noise while still failing on a real regression.
        assert ratio < 10.0, f"4x input cost {ratio:.1f}x time (small={small:.3f}s)"

    def test_forty_thousand_lines_extracts(self) -> None:
        """The reported failing size must produce real features."""
        features = StylometryExtractor().extract(synth(40_000))

        assert features.num_functions > 1000
        assert features.num_classes == 0

    def test_results_are_reproducible(self) -> None:
        """Repeated extraction must agree - the extractor resets its counters."""
        code = synth(2_000)

        first = StylometryExtractor().extract(code)
        second = StylometryExtractor().extract(code)

        assert first.num_functions == second.num_functions
        assert first.avg_nesting_depth == second.avg_nesting_depth
        assert first.comment_density == second.comment_density

    def test_reuse_of_one_extractor_does_not_leak_nodes(self) -> None:
        """A reused extractor must not accumulate nodes across calls."""
        extractor = StylometryExtractor()
        code = synth(500)

        extractor.extract(code)
        extractor.extract(code)

        assert len(extractor._nodes) == len(list(ast.walk(ast.parse(code))))
