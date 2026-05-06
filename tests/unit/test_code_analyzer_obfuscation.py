"""Tests for obfuscation-resistant signals in the compatibility analyzer."""

from src.backend.core.analyzer.code_analyzer import CodeAnalyzer


def test_normalization_graph_detects_renamed_code() -> None:
    """Renamed identifiers should keep a strong normalized graph signal."""
    code_a = """
def total_even(values):
    total = 0
    for value in values:
        if value % 2 == 0:
            total += value
    return total
"""
    code_b = """
def score_items(items):
    score = 0
    for item in items:
        if item % 2 == 0:
            score += item
    return score
"""

    result = CodeAnalyzer(threshold=0.5).compare_codes(
        code_a, code_b, "python", "python"
    )

    assert result.individual_scores["normalization_graph_similarity"] > 0.85
    assert result.overall_score > 0.75


def test_subsequence_merging_tolerates_small_insertions() -> None:
    """Small obfuscating edits should not break copied subsequence evidence."""
    code_a = """
def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value
"""
    code_b = """
def clamp_score(score, floor, ceiling):
    debug = None
    if score < floor:
        return floor
    marker = debug
    if score > ceiling:
        return ceiling
    return score
"""

    result = CodeAnalyzer(threshold=0.5).compare_codes(
        code_a, code_b, "python", "python"
    )

    assert result.individual_scores["subsequence_merge_similarity"] > 0.7
    assert result.is_suspicious


def test_tfidf_baseline_is_exposed_for_paraphrase_style_similarity() -> None:
    """Pair comparison should include a TF-IDF/cosine baseline score."""
    code_a = """
def summarize(values):
    total = sum(values)
    count = len(values)
    return total / count
"""
    code_b = """
def calculate_average(numbers):
    total = sum(numbers)
    amount = len(numbers)
    return total / amount
"""

    result = CodeAnalyzer(threshold=0.5).compare_codes(
        code_a, code_b, "python", "python"
    )

    assert "tfidf_similarity" in result.individual_scores
    assert result.individual_scores["tfidf_similarity"] > 0.5


def test_ai_detection_exposes_model_fusion_fields() -> None:
    """Single-file analysis should expose heuristic and model-backed AI scores."""
    code = '''
# Let us implement a comprehensive solution
def process_data(data):
    """Process the input data and return the result."""
    result = []
    for item in data:
        result.append(item)
    return result
'''

    result = CodeAnalyzer(enable_ai_detection=True).analyze_code(code, "python")

    assert "heuristic_ai_score" in result.ai_detection
    assert "model_ai_score" in result.ai_detection
    assert "model_confidence" in result.ai_detection
    assert 0.0 <= result.ai_detection["ai_score"] <= 1.0
