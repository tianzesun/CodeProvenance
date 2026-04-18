"""Tests for Graph Similarity engine."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.backend.engines.similarity.graph_similarity import (
    GraphSimilarity,
    GraphSimilarityResult,
    make_graph_similarity,
)


class TestGraphSimilarity:

    # --- interface tests ---

    def test_compare_identical(self) -> None:
        eng = GraphSimilarity()
        code = "def foo(x):\n    return x + 1\n"
        score = eng.compare({"content": code}, {"content": code})
        assert score == 1.0

    def test_compare_different(self) -> None:
        eng = GraphSimilarity()
        a = "def foo(x):\n    return x + 1\n"
        b = "def bar(y):\n    for i in range(y):\n        print(i)\n"
        score = eng.compare({"content": a}, {"content": b})
        assert 0.0 <= score < 1.0

    def test_empty_content(self) -> None:
        eng = GraphSimilarity()
        assert eng.compare({"content": ""}, {"content": ""}) == 0.0
        assert eng.compare({}, {}) == 0.0

    def test_syntax_error(self) -> None:
        eng = GraphSimilarity()
        assert eng.compare({"content": "def foo("}, {"content": "x = 1"}) == 0.0

    # --- detailed tests ---

    def test_detailed_identical(self) -> None:
        eng = GraphSimilarity()
        code = "x = 1\ny = 2\nz = x + y\n"
        result = eng.compare_detailed(code, code)
        assert isinstance(result, GraphSimilarityResult)
        assert result.overall_score == 1.0

    def test_variable_renaming(self) -> None:
        """Variable-renamed code should still score high."""
        eng = GraphSimilarity()
        a = "def compute(x, y):\n    return x + y\n"
        b = "def compute(a, b):\n    return a + b\n"
        result = eng.compare_detailed(a, b)
        assert result.structural_score == 1.0
        assert result.overall_score > 0.5

    def test_reorder_statements(self) -> None:
        """Reordered independent statements should still score reasonably."""
        eng = GraphSimilarity()
        a = "x = 1\ny = 2\n"
        b = "y = 2\nx = 1\n"
        result = eng.compare_detailed(a, b)
        assert result.overall_score > 0.5

    def test_dead_code_insertion(self) -> None:
        """Inserting dead code should reduce but not eliminate similarity."""
        eng = GraphSimilarity()
        a = "x = 1\nreturn x\n"
        b = "x = 1\nunused = 42\nanother = 99\nreturn x\n"
        result = eng.compare_detailed(a, b)
        assert result.overall_score > 0.3

    def test_compare_functions(self) -> None:
        eng = GraphSimilarity()
        a = "def foo(x):\n    return x * 2\n"
        b = "def foo(a):\n    return a * 2\n"
        result = eng.compare_functions(a, b, "foo", "foo")
        assert result is not None
        assert result.overall_score > 0.5

    def test_compare_functions_not_found(self) -> None:
        eng = GraphSimilarity()
        result = eng.compare_functions("x = 1", "y = 2", "missing_a", "missing_b")
        assert result is None

    # --- component tests ---

    def test_structural_degenerate(self) -> None:
        """Empty graphs should return 0 structural similarity."""
        from src.backend.core.graph.combined_builder import CombinedGraph
        eng = GraphSimilarity()
        a = CombinedGraph()
        b = CombinedGraph()
        assert eng._structural(a, b) == 0.0

    def test_dataflow_degenerate(self) -> None:
        from src.backend.core.graph.combined_builder import CombinedGraph
        eng = GraphSimilarity()
        a = CombinedGraph()
        b = CombinedGraph()
        assert eng._dataflow(a, b) == 1.0  # Both empty, trivially same

    def test_semantic_degenerate(self) -> None:
        from src.backend.core.graph.combined_builder import CombinedGraph
        eng = GraphSimilarity()
        a = CombinedGraph()
        b = CombinedGraph()
        assert eng._semantic(a, b) == 1.0  # Both empty, trivially same

    def test_cosine_identical(self) -> None:
        assert GraphSimilarity._cosine({"a": 1}, {"a": 1}) == 1.0

    def test_cosine_disjoint(self) -> None:
        assert GraphSimilarity._cosine({"a": 1}, {"b": 1}) == 0.0

    def test_cosine_empty(self) -> None:
        assert GraphSimilarity._cosine({}, {}) == 1.0

    def test_dist_sim_identical(self) -> None:
        assert GraphSimilarity._dist_sim([1, 2, 3], [1, 2, 3]) == 1.0

    def test_factory(self) -> None:
        eng = make_graph_similarity()
        assert eng.name == "GraphSimilarity"

    def test_name(self) -> None:
        eng = GraphSimilarity()
        assert eng.get_name() == "GraphSimilarity"


class TestSimilarityEngineIntegration:
    """Test that graph similarity works with SimilarityEngine."""

    def test_register_and_use(self) -> None:
        from src.backend.engines.similarity.base_similarity import SimilarityEngine
        from src.backend.engines.similarity.graph_similarity import GraphSimilarity

        engine = SimilarityEngine()
        engine.add_algorithm(GraphSimilarity(), weight=2.0)
        # Disable deep analysis for predictable scoring
        engine.enable_deep_analysis(False)

        code = "def foo(x): return x + 1\n"
        result = engine.compare(
            {"content": code, "language": "python"},
            {"content": code, "language": "python"},
        )
        assert result["overall_score"] == 1.0
        assert "GraphSimilarity" in result["individual_scores"]
        assert result["individual_scores"]["GraphSimilarity"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])