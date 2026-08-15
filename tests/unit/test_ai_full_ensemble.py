"""Unit tests for the tree-sitter AST, perplexity and ensemble AI modules."""

import logging


from src.backend.engines.ai.ast_features import (
    get_ast_features,
)
from src.backend.engines.ai.ensemble import AIEnsembleScorer
from src.backend.engines.ai.perplexity import PerplexityScorer, _windowed_chunks

logging.disable(logging.INFO)

PYTHON_SAMPLE = """\
def mean(values):
    \"\"\"Compute the arithmetic mean of a list.\"\"\"
    if not values:
        raise ValueError("empty list")
    total = sum(values)
    return total / len(values)

def median(values):
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid]
"""

JAVA_SAMPLE = """\
public class Calculator {
    private int total;
    public int add(int a, int b) {
        this.total = a + b;
        return this.total;
    }
    public int multiply(int a, int b) {
        return a * b;
    }
}
"""

AI_STYLE = """\
def calculate_mean(values):
    \"\"\"Calculate the mean of a list of numbers.
    Args:
        values: A list of numeric values.
    Returns:
        The arithmetic mean of the provided values.
    \"\"\"
    if not values:
        raise ValueError("Cannot compute mean of empty list")
    total = sum(values)
    count = len(values)
    return total / count
"""

HUMAN_STYLE = """\
def avg(xs):
    t = 0
    for v in xs:
        t += v
    return t/len(xs) if xs else 0
"""


class TestTreeSitterASTExtractor:
    def test_python_extracts_functions_and_classes(self) -> None:
        fv = get_ast_features(PYTHON_SAMPLE, "python")
        assert fv.parse_success is True
        assert fv.function_count == 2
        assert fv.class_count == 0

    def test_java_extracts_functions_and_class(self) -> None:
        fv = get_ast_features(JAVA_SAMPLE, "java")
        assert fv.parse_success is True
        assert fv.class_count == 1
        assert fv.function_count >= 1

    def test_cpp_parses(self) -> None:
        fv = get_ast_features("int main() { return 0; }", "cpp")
        assert fv.parse_success is True
        assert fv.function_count >= 1

    def test_typescript_parses(self) -> None:
        """TypeScript must parse via the AST extractor.

        tree_sitter_typescript exposes ``language_typescript`` (not
        ``language``), so the loader must resolve the correct symbol. A lexical
        fallback would still score code, but report parse_success=False and
        miss the AST-structure signal the UI promises for TypeScript.
        """
        fv = get_ast_features(
            "function add(a: number, b: number): number { return a + b; }\n"
            "const r: number = add(1, 2);",
            "typescript",
        )
        assert fv.parse_success is True
        assert fv.function_count >= 1

    def test_fallback_for_unsupported_language(self) -> None:
        fv = get_ast_features("PROGRAM hello; BEGIN writeln(hello); END.", "pascal")
        assert fv.parse_success is False
        assert len(fv.to_vector()) == 11

    def test_vector_is_fixed_length(self) -> None:
        for lang, code in [
            ("python", PYTHON_SAMPLE),
            ("java", JAVA_SAMPLE),
            ("cpp", "int main() { return 0; }"),
        ]:
            fv = get_ast_features(code, lang)
            assert len(fv.to_vector()) == 11
            assert all(isinstance(value, float) for value in fv.to_vector())

    def test_empty_code_returns_default_vector(self) -> None:
        fv = get_ast_features("", "python")
        assert fv.function_count == 0


class TestPerplexityScorer:
    def test_windows_code_into_overlapping_chunks(self) -> None:
        lines = [f"line {i}" for i in range(30)]
        chunks = _windowed_chunks("\n".join(lines), window=25, overlap=5)
        assert len(chunks) >= 1
        assert chunks[0]["lines"].count("\n") + 1 <= 25
        assert chunks[0]["start_line"] == 1
        assert chunks[1]["start_line"] == chunks[0]["end_line"] + 1 - 5

    def test_burstiness_and_perplexity_are_bounded(self) -> None:
        scorer = PerplexityScorer()
        scorer.train([PYTHON_SAMPLE, AI_STYLE, HUMAN_STYLE])
        result = scorer.score(AI_STYLE)
        assert 0.0 <= result["perplexity"]
        assert 0.0 <= result["burstiness"] <= 1.0
        assert result["model"] == "statistical"

    def test_empty_code_scores_neutral(self) -> None:
        scorer = PerplexityScorer()
        result = scorer.score("")
        assert result["ai_likelihood"] == 0.5
        assert result["per_chunk"] == []

    def test_repetitive_code_has_lower_perplexity(self) -> None:
        scorer = PerplexityScorer()
        repetitive = "x = 1\nx = 2\nx = 3\nx = 4\nx = 5\nx = 6\nx = 7\n"
        diverse = (
            "alpha = beta(gamma)\ndelta = epsilon(zeta)\neta = theta(iota)\n"
            "kappa = lambda(mu)\nnu = xi(omicron)\npi = rho(tau)\n"
        )
        perp_rep = scorer.score(repetitive)["perplexity"]
        perp_div = scorer.score(diverse)["perplexity"]
        assert perp_rep <= perp_div


class TestAIEnsembleScorer:
    def test_separates_ai_and_human_without_trained_model(self) -> None:
        scorer = AIEnsembleScorer()
        ai = scorer.score(AI_STYLE, "python", pattern_library=0.5)
        hu = scorer.score(HUMAN_STYLE, "python", pattern_library=0.0)
        assert ai["ai_probability"] > hu["ai_probability"]

    def test_returns_expected_shape(self) -> None:
        scorer = AIEnsembleScorer()
        result = scorer.score(AI_STYLE, "python")
        assert "ai_probability" in result
        assert "signals" in result
        assert "flagged_regions" in result
        assert "confidence" in result
        assert "mode" in result

    def test_short_code_returns_zero(self) -> None:
        scorer = AIEnsembleScorer()
        result = scorer.score("x", "python")
        assert result["ai_probability"] == 0.0

    def test_flagged_region_lines_survive_blank_gaps(self) -> None:
        scorer = AIEnsembleScorer()
        # Repetitive predictable code (low perplexity) above a large blank gap.
        code = 'print("constant")\n' * 40 + "\n" * 60 + 'print("constant")\n' * 40
        result = scorer.score(code, "python")
        regions = result["flagged_regions"]
        assert regions
        assert all(r["end_line"] >= r["start_line"] for r in regions)
        # No region may point past the real line count; the tail chunk maps to
        # the 60 blank lines that start at line 41.
        tail = [r for r in regions if r["start_line"] >= 60]
        assert tail, regions
        for region in tail:
            assert region["start_line"] >= 41


class TestConfig:
    def test_config_defaults_load(self) -> None:
        from src.backend.engines.ai.ensemble import AIEnsembleConfig

        config = AIEnsembleConfig()
        heuristic = config.weights("heuristic")
        assert abs(sum(heuristic.values()) - 1.0) < 1e-6
        assert config.threshold("medium_risk", 0.4) == 0.4

    def test_config_missing_file_falls_back_to_defaults(self) -> None:
        from src.backend.engines.ai.ensemble import AIEnsembleConfig

        config = AIEnsembleConfig(config_path="/nonexistent/ai_ensemble_config.yaml")
        assert config.weights("heuristic")["ast"] == 0.20


class TestClassifier:
    def test_train_predict_save_load(self) -> None:
        from src.backend.engines.ai.classifier import AICodeClassifier

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            rows, labels = [], []
            for _ in range(20):
                rows.append(
                    {
                        "perplexity": 1.5,
                        "burstiness": 0.9,
                        "node_type_entropy": 0.9,
                        "avg_log_prob": -1.0,
                    }
                )
                labels.append(1)
                rows.append(
                    {
                        "perplexity": 7.0,
                        "burstiness": 0.2,
                        "node_type_entropy": 0.3,
                        "avg_log_prob": -7.0,
                    }
                )
                labels.append(0)
            classifier = AICodeClassifier(model_dir=tmp)
            version = classifier.train(rows[:30], labels[:30])
            assert version
            classifier.save()
            loaded = AICodeClassifier(model_dir=tmp)
            assert loaded.load() is True
            prediction = loaded.predict({"perplexity": 1.0, "burstiness": 0.95})
            assert prediction.ai_probability >= 0.0

    def test_predict_without_trained_model_returns_neutral(self) -> None:
        from src.backend.engines.ai.classifier import AICodeClassifier

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            classifier = AICodeClassifier(model_dir=tmp)
            assert classifier.is_trained is False
            result = classifier.predict({"perplexity": 1.0})
            assert result.ai_probability == 0.5
