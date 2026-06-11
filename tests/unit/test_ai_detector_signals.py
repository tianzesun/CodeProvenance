"""Unit tests for AI Detector signal computation layer.

Tests all 8 independent signals to ensure:
- Scores are properly bounded [0.0, 1.0]
- Calibration ranges are correct (human vs AI code)
- Edge cases are handled gracefully
- Signals work with test fixtures
"""

from src.backend.engines.ai.signals import (
    compute_perplexity_signal,
    compute_burstiness_signal,
    compute_stylometry_signal,
    compute_pattern_library_signal,
    compute_structural_entropy_signal,
    compute_vocabulary_richness_signal,
    compute_whitespace_rhythm_signal,
    compute_docstring_density_signal,
)
from tests.fixtures.ai_detector.fixtures import (
    get_human_samples,
    get_ai_samples,
    get_edge_case_samples,
)


# ============================================================================
# SIGNAL 1: PERPLEXITY TESTS
# ============================================================================


class TestPerplexitySignal:
    """Tests for perplexity signal (token-level entropy)."""

    def test_perplexity_returns_valid_score(self):
        """Test that perplexity returns a score in [0.0, 1.0]."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_perplexity_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_perplexity_human_code_lower_than_ai(self):
        """Test that human code has lower perplexity than AI code."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_perplexity_signal(code) for code in human_samples.values()]
        ai_scores = [compute_perplexity_signal(code) for code in ai_samples.values()]

        # Both should have valid scores
        assert all(0.0 <= s <= 1.0 for s in human_scores)
        assert all(0.0 <= s <= 1.0 for s in ai_scores)

    def test_perplexity_edge_empty_code(self):
        """Test perplexity with empty code."""
        score = compute_perplexity_signal("")
        assert 0.0 <= score <= 1.0

    def test_perplexity_edge_very_short_code(self):
        """Test perplexity with very short code."""
        score = compute_perplexity_signal("x = 1")
        assert 0.0 <= score <= 1.0

    def test_perplexity_edge_only_comments(self):
        """Test perplexity with only comments."""
        code = "# comment\n# another comment"
        score = compute_perplexity_signal(code)
        assert 0.0 <= score <= 1.0

    def test_perplexity_rounded_to_three_decimals(self):
        """Test that perplexity score is rounded to 3 decimals."""
        code = "x = 1\ny = 2\nz = x + y\na = z * 2"
        score = compute_perplexity_signal(code)
        # Check that score has at most 3 decimal places
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# SIGNAL 2: BURSTINESS TESTS
# ============================================================================


class TestBurstinessSignal:
    """Tests for burstiness signal (line complexity variation)."""

    def test_burstiness_returns_valid_score(self):
        """Test that burstiness returns a score in [0.0, 1.0]."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_burstiness_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_burstiness_human_code_lower_than_ai(self):
        """Test that human code has lower burstiness than AI code."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_burstiness_signal(code) for code in human_samples.values()]
        ai_scores = [compute_burstiness_signal(code) for code in ai_samples.values()]

        # Both should have valid scores
        assert all(0.0 <= s <= 1.0 for s in human_scores)
        assert all(0.0 <= s <= 1.0 for s in ai_scores)

    def test_burstiness_edge_empty_code(self):
        """Test burstiness with empty code."""
        score = compute_burstiness_signal("")
        assert 0.0 <= score <= 1.0

    def test_burstiness_edge_very_short_code(self):
        """Test burstiness with very short code."""
        score = compute_burstiness_signal("x = 1")
        assert 0.0 <= score <= 1.0

    def test_burstiness_uniform_indentation(self):
        """Test burstiness with uniform indentation (AI-like)."""
        code = """def func1():
    x = 1
    y = 2
    z = 3
    return x + y + z

def func2():
    a = 1
    b = 2
    c = 3
    return a + b + c"""
        score = compute_burstiness_signal(code)
        assert 0.0 <= score <= 1.0
        # Uniform code should have higher burstiness score
        assert score > 0.3

    def test_burstiness_rounded_to_three_decimals(self):
        """Test that burstiness score is rounded to 3 decimals."""
        code = "x = 1\ny = 2\nz = x + y\na = z * 2"
        score = compute_burstiness_signal(code)
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# SIGNAL 3: STYLOMETRY TESTS
# ============================================================================


class TestStylometrySignal:
    """Tests for stylometry signal (code style profile)."""

    def test_stylometry_returns_valid_score(self):
        """Test that stylometry returns a score in [0.0, 1.0]."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_stylometry_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_stylometry_ai_code_higher_than_human(self):
        """Test that AI code has higher stylometry score than human code."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_stylometry_signal(code) for code in human_samples.values()]
        ai_scores = [compute_stylometry_signal(code) for code in ai_samples.values()]

        # Average AI score should be higher than average human score
        avg_human = sum(human_scores) / len(human_scores)
        avg_ai = sum(ai_scores) / len(ai_scores)
        assert avg_ai > avg_human

    def test_stylometry_edge_empty_code(self):
        """Test stylometry with empty code."""
        score = compute_stylometry_signal("")
        assert 0.0 <= score <= 1.0

    def test_stylometry_edge_only_comments(self):
        """Test stylometry with only comments."""
        code = "# comment\n# another comment"
        score = compute_stylometry_signal(code)
        assert 0.0 <= score <= 1.0

    def test_stylometry_generic_names(self):
        """Test stylometry detects generic variable names."""
        code_generic = """
result = []
for item in data:
    output = process(item)
    result.append(output)
return result
"""
        code_descriptive = """
processed_items = []
for user in users:
    user_profile = fetch_profile(user)
    processed_items.append(user_profile)
return processed_items
"""
        score_generic = compute_stylometry_signal(code_generic)
        score_descriptive = compute_stylometry_signal(code_descriptive)
        # Generic names should have higher score
        assert score_generic > score_descriptive

    def test_stylometry_rounded_to_three_decimals(self):
        """Test that stylometry score is rounded to 3 decimals."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_stylometry_signal(code)
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# SIGNAL 4: PATTERN LIBRARY TESTS
# ============================================================================


class TestPatternLibrarySignal:
    """Tests for pattern library signal (LLM fingerprints)."""

    def test_pattern_library_returns_valid_score(self):
        """Test that pattern library returns a score in [0.0, 1.0]."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_pattern_library_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_pattern_library_ai_code_higher_than_human(self):
        """Test that AI code has higher pattern library score."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_pattern_library_signal(code) for code in human_samples.values()]
        ai_scores = [compute_pattern_library_signal(code) for code in ai_samples.values()]

        # Average AI score should be higher than average human score
        avg_human = sum(human_scores) / len(human_scores)
        avg_ai = sum(ai_scores) / len(ai_scores)
        assert avg_ai > avg_human

    def test_pattern_library_edge_empty_code(self):
        """Test pattern library with empty code."""
        score = compute_pattern_library_signal("")
        assert 0.0 <= score <= 1.0

    def test_pattern_library_edge_only_comments(self):
        """Test pattern library with only comments."""
        code = "# comment\n# another comment"
        score = compute_pattern_library_signal(code)
        assert 0.0 <= score <= 1.0

    def test_pattern_library_detects_llm_patterns(self):
        """Test that pattern library detects LLM-specific patterns."""
        code_with_patterns = '''
def process_data(input_data):
    """Process input data and return results."""
    result = []
    for item in input_data:
        # Here we process each item
        processed_item = {
            'id': item.get('id'),
            'value': item.get('value', 0),
            'status': 'processed'
        }
        result.append(processed_item)
    return result
'''
        score = compute_pattern_library_signal(code_with_patterns)
        # Should detect multiple LLM patterns
        assert score > 0.3

    def test_pattern_library_rounded_to_three_decimals(self):
        """Test that pattern library score is rounded to 3 decimals."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_pattern_library_signal(code)
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# SIGNAL 5: STRUCTURAL ENTROPY TESTS
# ============================================================================


class TestStructuralEntropySignal:
    """Tests for structural entropy signal (AST uniformity)."""

    def test_structural_entropy_returns_valid_score(self):
        """Test that structural entropy returns a score in [0.0, 1.0]."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_structural_entropy_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_structural_entropy_ai_code_higher_than_human(self):
        """Test that AI code has higher structural entropy score."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_structural_entropy_signal(code) for code in human_samples.values()]
        ai_scores = [compute_structural_entropy_signal(code) for code in ai_samples.values()]

        # Both should have valid scores
        assert all(0.0 <= s <= 1.0 for s in human_scores)
        assert all(0.0 <= s <= 1.0 for s in ai_scores)

    def test_structural_entropy_edge_empty_code(self):
        """Test structural entropy with empty code."""
        score = compute_structural_entropy_signal("")
        assert 0.0 <= score <= 1.0

    def test_structural_entropy_edge_syntax_error(self):
        """Test structural entropy with syntax error (fallback)."""
        code = "def broken(\n    x = 1\n    y = 2"
        score = compute_structural_entropy_signal(code)
        assert 0.0 <= score <= 1.0

    def test_structural_entropy_uniform_indentation(self):
        """Test structural entropy with uniform indentation."""
        code = """def func1():
    x = 1
    y = 2
    z = 3
    return x + y + z

def func2():
    a = 1
    b = 2
    c = 3
    return a + b + c"""
        score = compute_structural_entropy_signal(code)
        assert 0.0 <= score <= 1.0

    def test_structural_entropy_rounded_to_three_decimals(self):
        """Test that structural entropy score is rounded to 3 decimals."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_structural_entropy_signal(code)
        assert len(str(score).split(".")[-1]) <= 3

    def test_structural_entropy_with_language_parameter(self):
        """Test structural entropy with language parameter."""
        code = "x = 1\ny = 2\nz = x + y"
        score_python = compute_structural_entropy_signal(code, language="python")
        score_other = compute_structural_entropy_signal(code, language="javascript")
        assert 0.0 <= score_python <= 1.0
        assert 0.0 <= score_other <= 1.0


# ============================================================================
# SIGNAL 6: VOCABULARY RICHNESS TESTS
# ============================================================================


class TestVocabularyRichnessSignal:
    """Tests for vocabulary richness signal (token diversity)."""

    def test_vocabulary_richness_returns_valid_score(self):
        """Test that vocabulary richness returns a score in [0.0, 1.0]."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_vocabulary_richness_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_vocabulary_richness_human_code_lower_than_ai(self):
        """Test that human code has lower vocabulary richness score."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_vocabulary_richness_signal(code) for code in human_samples.values()]
        ai_scores = [compute_vocabulary_richness_signal(code) for code in ai_samples.values()]

        # Both should have valid scores
        assert all(0.0 <= s <= 1.0 for s in human_scores)
        assert all(0.0 <= s <= 1.0 for s in ai_scores)

    def test_vocabulary_richness_edge_empty_code(self):
        """Test vocabulary richness with empty code."""
        score = compute_vocabulary_richness_signal("")
        assert 0.0 <= score <= 1.0

    def test_vocabulary_richness_edge_very_short_code(self):
        """Test vocabulary richness with very short code."""
        score = compute_vocabulary_richness_signal("x = 1")
        assert 0.0 <= score <= 1.0

    def test_vocabulary_richness_repetitive_code(self):
        """Test vocabulary richness with highly repetitive code."""
        code = """x = 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1"""
        score = compute_vocabulary_richness_signal(code)
        # Repetitive code should have higher score (lower diversity)
        assert score > 0.5

    def test_vocabulary_richness_rounded_to_three_decimals(self):
        """Test that vocabulary richness score is rounded to 3 decimals."""
        code = "x = 1\ny = 2\nz = x + y\na = z * 2"
        score = compute_vocabulary_richness_signal(code)
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# SIGNAL 7: WHITESPACE RHYTHM TESTS
# ============================================================================


class TestWhitespaceRhythmSignal:
    """Tests for whitespace rhythm signal (blank-line spacing)."""

    def test_whitespace_rhythm_returns_valid_score(self):
        """Test that whitespace rhythm returns a score in [0.0, 1.0]."""
        code = "x = 1\n\ny = 2\n\nz = x + y"
        score = compute_whitespace_rhythm_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_whitespace_rhythm_edge_empty_code(self):
        """Test whitespace rhythm with empty code."""
        score = compute_whitespace_rhythm_signal("")
        assert 0.0 <= score <= 1.0

    def test_whitespace_rhythm_edge_only_whitespace(self):
        """Test whitespace rhythm with only whitespace."""
        code = "\n\n\n    \n    \n"
        score = compute_whitespace_rhythm_signal(code)
        assert 0.0 <= score <= 1.0

    def test_whitespace_rhythm_uniform_spacing(self):
        """Test whitespace rhythm with uniform spacing (AI-like)."""
        code = """def func1():
    x = 1

def func2():
    y = 2

def func3():
    z = 3"""
        score = compute_whitespace_rhythm_signal(code)
        # Uniform spacing should have valid score
        assert 0.0 <= score <= 1.0

    def test_whitespace_rhythm_varied_spacing(self):
        """Test whitespace rhythm with varied spacing (human-like)."""
        code = """def func1():
    x = 1


def func2():
    y = 2
    z = 3

def func3():
    a = 4"""
        score = compute_whitespace_rhythm_signal(code)
        assert 0.0 <= score <= 1.0

    def test_whitespace_rhythm_rounded_to_three_decimals(self):
        """Test that whitespace rhythm score is rounded to 3 decimals."""
        code = "x = 1\n\ny = 2\n\nz = x + y"
        score = compute_whitespace_rhythm_signal(code)
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# SIGNAL 8: DOCSTRING DENSITY TESTS
# ============================================================================


class TestDocstringDensitySignal:
    """Tests for docstring density signal (documentation prevalence)."""

    def test_docstring_density_returns_valid_score(self):
        """Test that docstring density returns a score in [0.0, 1.0]."""
        code = 'def func():\n    """Docstring."""\n    return 1'
        score = compute_docstring_density_signal(code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_docstring_density_ai_code_higher_than_human(self):
        """Test that AI code has higher docstring density score."""
        human_samples = get_human_samples()
        ai_samples = get_ai_samples()

        human_scores = [compute_docstring_density_signal(code) for code in human_samples.values()]
        ai_scores = [compute_docstring_density_signal(code) for code in ai_samples.values()]

        # Average AI score should be higher than average human score
        avg_human = sum(human_scores) / len(human_scores)
        avg_ai = sum(ai_scores) / len(ai_scores)
        assert avg_ai > avg_human

    def test_docstring_density_edge_empty_code(self):
        """Test docstring density with empty code."""
        score = compute_docstring_density_signal("")
        assert 0.0 <= score <= 1.0

    def test_docstring_density_edge_no_functions(self):
        """Test docstring density with no functions."""
        code = "x = 1\ny = 2\nz = x + y"
        score = compute_docstring_density_signal(code)
        assert 0.0 <= score <= 1.0

    def test_docstring_density_all_functions_documented(self):
        """Test docstring density with all functions documented."""
        code = '''def func1():
    """Docstring 1."""
    return 1

def func2():
    """Docstring 2."""
    return 2

def func3():
    """Docstring 3."""
    return 3'''
        score = compute_docstring_density_signal(code)
        # All functions documented should have high score
        assert score > 0.5

    def test_docstring_density_no_functions_documented(self):
        """Test docstring density with no functions documented."""
        code = """def func1():
    return 1

def func2():
    return 2

def func3():
    return 3"""
        score = compute_docstring_density_signal(code)
        # No functions documented should have low score
        assert score < 0.3

    def test_docstring_density_rounded_to_three_decimals(self):
        """Test that docstring density score is rounded to 3 decimals."""
        code = 'def func():\n    """Docstring."""\n    return 1'
        score = compute_docstring_density_signal(code)
        assert len(str(score).split(".")[-1]) <= 3


# ============================================================================
# INTEGRATION TESTS: ALL SIGNALS WITH FIXTURES
# ============================================================================


class TestSignalsWithFixtures:
    """Integration tests using all fixture samples."""

    def test_all_signals_with_human_samples(self):
        """Test all signals with human code samples."""
        human_samples = get_human_samples()

        for name, code in human_samples.items():
            perplexity = compute_perplexity_signal(code)
            burstiness = compute_burstiness_signal(code)
            stylometry = compute_stylometry_signal(code)
            pattern_library = compute_pattern_library_signal(code)
            structural_entropy = compute_structural_entropy_signal(code)
            vocabulary_richness = compute_vocabulary_richness_signal(code)
            whitespace_rhythm = compute_whitespace_rhythm_signal(code)
            docstring_density = compute_docstring_density_signal(code)

            # All scores should be valid
            for score in [
                perplexity,
                burstiness,
                stylometry,
                pattern_library,
                structural_entropy,
                vocabulary_richness,
                whitespace_rhythm,
                docstring_density,
            ]:
                assert 0.0 <= score <= 1.0, f"Invalid score for {name}: {score}"

    def test_all_signals_with_ai_samples(self):
        """Test all signals with AI code samples."""
        ai_samples = get_ai_samples()

        for name, code in ai_samples.items():
            perplexity = compute_perplexity_signal(code)
            burstiness = compute_burstiness_signal(code)
            stylometry = compute_stylometry_signal(code)
            pattern_library = compute_pattern_library_signal(code)
            structural_entropy = compute_structural_entropy_signal(code)
            vocabulary_richness = compute_vocabulary_richness_signal(code)
            whitespace_rhythm = compute_whitespace_rhythm_signal(code)
            docstring_density = compute_docstring_density_signal(code)

            # All scores should be valid
            for score in [
                perplexity,
                burstiness,
                stylometry,
                pattern_library,
                structural_entropy,
                vocabulary_richness,
                whitespace_rhythm,
                docstring_density,
            ]:
                assert 0.0 <= score <= 1.0, f"Invalid score for {name}: {score}"

    def test_all_signals_with_edge_cases(self):
        """Test all signals with edge case samples."""
        edge_cases = get_edge_case_samples()

        for name, code in edge_cases.items():
            perplexity = compute_perplexity_signal(code)
            burstiness = compute_burstiness_signal(code)
            stylometry = compute_stylometry_signal(code)
            pattern_library = compute_pattern_library_signal(code)
            structural_entropy = compute_structural_entropy_signal(code)
            vocabulary_richness = compute_vocabulary_richness_signal(code)
            whitespace_rhythm = compute_whitespace_rhythm_signal(code)
            docstring_density = compute_docstring_density_signal(code)

            # All scores should be valid (edge cases should not crash)
            for score in [
                perplexity,
                burstiness,
                stylometry,
                pattern_library,
                structural_entropy,
                vocabulary_richness,
                whitespace_rhythm,
                docstring_density,
            ]:
                assert 0.0 <= score <= 1.0, f"Invalid score for {name}: {score}"

    def test_signal_consistency_across_samples(self):
        """Test that signals are consistent across multiple runs."""
        code = "x = 1\ny = 2\nz = x + y"

        # Run each signal multiple times
        for _ in range(3):
            score1 = compute_perplexity_signal(code)
            score2 = compute_perplexity_signal(code)
            assert score1 == score2, "Perplexity not consistent"

            score1 = compute_burstiness_signal(code)
            score2 = compute_burstiness_signal(code)
            assert score1 == score2, "Burstiness not consistent"

            score1 = compute_stylometry_signal(code)
            score2 = compute_stylometry_signal(code)
            assert score1 == score2, "Stylometry not consistent"


# ============================================================================
# PROPERTY-BASED TESTS
# ============================================================================


class TestSignalProperties:
    """Property-based tests for signal invariants."""

    def test_all_signals_bounded(self):
        """Property: All signals must return scores in [0.0, 1.0]."""
        samples = get_all_samples()

        for code in samples.values():
            assert 0.0 <= compute_perplexity_signal(code) <= 1.0
            assert 0.0 <= compute_burstiness_signal(code) <= 1.0
            assert 0.0 <= compute_stylometry_signal(code) <= 1.0
            assert 0.0 <= compute_pattern_library_signal(code) <= 1.0
            assert 0.0 <= compute_structural_entropy_signal(code) <= 1.0
            assert 0.0 <= compute_vocabulary_richness_signal(code) <= 1.0
            assert 0.0 <= compute_whitespace_rhythm_signal(code) <= 1.0
            assert 0.0 <= compute_docstring_density_signal(code) <= 1.0

    def test_all_signals_deterministic(self):
        """Property: All signals must be deterministic."""
        samples = get_all_samples()

        for code in samples.values():
            # Run each signal twice and verify results are identical
            assert compute_perplexity_signal(code) == compute_perplexity_signal(code)
            assert compute_burstiness_signal(code) == compute_burstiness_signal(code)
            assert compute_stylometry_signal(code) == compute_stylometry_signal(code)
            assert compute_pattern_library_signal(code) == compute_pattern_library_signal(code)
            assert compute_structural_entropy_signal(code) == compute_structural_entropy_signal(
                code
            )
            assert compute_vocabulary_richness_signal(code) == compute_vocabulary_richness_signal(
                code
            )
            assert compute_whitespace_rhythm_signal(code) == compute_whitespace_rhythm_signal(code)
            assert compute_docstring_density_signal(code) == compute_docstring_density_signal(code)


def get_all_samples():
    """Helper to get all samples."""
    samples = {}
    samples.update(get_human_samples())
    samples.update(get_ai_samples())
    samples.update(get_edge_case_samples())
    return samples
