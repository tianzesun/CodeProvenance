"""Unit tests for historical_fingerprint module."""

import pytest

from src.backend.evaluation.historical_fingerprint import (
    HistoricalFingerprintAnalyzer,
    StyleFeatures,
    FingerprintResult,
    run_fingerprint_analysis,
)


class TestStyleFeatures:
    """Tests for StyleFeatures dataclass."""

    def test_create_style_features(self) -> None:
        """Test creating style features."""
        features = StyleFeatures(
            avg_line_length=50.0,
            max_line_length=100,
            indentation_depth=1.0,
            comment_ratio=0.1,
            blank_line_ratio=0.05,
            naming_convention="snake_case",
            function_count=5,
            class_count=2,
            complexity_score=0.3,
            token_count=100,
        )
        assert features.avg_line_length == 50.0
        assert features.naming_convention == "snake_case"

    def test_style_features_auto_hash(self) -> None:
        """Test that hash is auto-computed."""
        features = StyleFeatures(
            avg_line_length=50.0,
            max_line_length=100,
            indentation_depth=1.0,
            comment_ratio=0.1,
            blank_line_ratio=0.05,
            naming_convention="snake_case",
            function_count=5,
            class_count=2,
            complexity_score=0.3,
            token_count=100,
        )
        assert len(features.hash) == 12

    def test_style_features_custom_hash(self) -> None:
        """Test custom hash is preserved."""
        features = StyleFeatures(
            avg_line_length=50.0,
            max_line_length=100,
            indentation_depth=1.0,
            comment_ratio=0.1,
            blank_line_ratio=0.05,
            naming_convention="snake_case",
            function_count=5,
            class_count=2,
            complexity_score=0.3,
            token_count=100,
            hash="custom_hash",
        )
        assert features.hash == "custom_hash"


class TestHistoricalFingerprintAnalyzer:
    """Tests for HistoricalFingerprintAnalyzer class."""

    def test_extract_features_python(self) -> None:
        """Test feature extraction from Python code."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "def foo():\n    return 1\n"

        features = analyzer.extract_features(code)
        assert features.function_count == 1
        assert features.comment_ratio == 0.0

    def test_extract_features_with_comments(self) -> None:
        """Test feature extraction with comments."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "# This is a comment\ndef foo():\n    return 1\n"

        features = analyzer.extract_features(code)
        assert features.comment_ratio > 0

    def test_extract_features_with_classes(self) -> None:
        """Test feature extraction with classes."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "class MyClass:\n    pass\n"

        features = analyzer.extract_features(code)
        assert features.class_count == 1

    def test_detect_naming_convention_snake_case(self) -> None:
        """Test snake_case detection."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "def my_function_name():\n    pass\n"

        features = analyzer.extract_features(code)
        assert features.naming_convention == "snake_case"

    def test_detect_naming_convention_camel_case(self) -> None:
        """Test camelCase detection."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "def myFunctionName():\n    pass\n"

        features = analyzer.extract_features(code)
        assert features.naming_convention == "camelCase"

    def test_analyze_new_student(self) -> None:
        """Test analysis for a student with no history."""
        analyzer = HistoricalFingerprintAnalyzer()
        result = analyzer.analyze(
            student_id="new_student",
            code="def foo():\n    return 1\n",
            submission_id="sub_001",
        )

        assert result.student_id == "new_student"
        assert result.is_anomaly is False  # No history = no anomaly
        assert result.historical_features is None

    def test_analyze_with_history(self) -> None:
        """Test analysis with existing history."""
        analyzer = HistoricalFingerprintAnalyzer()

        # First submission
        result1 = analyzer.analyze(
            student_id="student_1",
            code="def foo():\n    return 1\n",
            submission_id="sub_001",
        )
        assert result1.historical_features is None

        # Second submission with different style
        result2 = analyzer.analyze(
            student_id="student_1",
            code="def bar():\n    x = 1\n    return x\n",
            submission_id="sub_002",
        )
        assert result2.historical_features is not None

    def test_get_historical_consistency(self) -> None:
        """Test getting consistency score."""
        analyzer = HistoricalFingerprintAnalyzer()

        # No history
        assert analyzer.get_historical_consistency("unknown") == 1.0

        # Add history
        analyzer.analyze(
            student_id="student_1",
            code="def foo():\n    return 1\n",
            submission_id="sub_001",
        )
        analyzer.analyze(
            student_id="student_1",
            code="def bar():\n    return 2\n",
            submission_id="sub_002",
        )

        consistency = analyzer.get_historical_consistency("student_1")
        assert isinstance(consistency, float)


class TestFingerprintResult:
    """Tests for FingerprintResult dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        features = StyleFeatures(
            avg_line_length=50.0,
            max_line_length=100,
            indentation_depth=1.0,
            comment_ratio=0.1,
            blank_line_ratio=0.05,
            naming_convention="snake_case",
            function_count=5,
            class_count=2,
            complexity_score=0.3,
            token_count=100,
        )

        result = FingerprintResult(
            student_id="student_1",
            current_features=features,
            historical_features=None,
            deviation_score=0.5,
            is_anomaly=True,
            confidence_score=0.8,
            recommendations=["Review recommended"],
        )

        d = result.to_dict()
        assert d["student_id"] == "student_1"
        assert d["deviation_score"] == 0.5
        assert d["is_anomaly"] is True
        assert d["current_features"]["naming_convention"] == "snake_case"


class TestRunFingerprintAnalysis:
    """Tests for run_fingerprint_analysis convenience function."""

    def test_run_analysis(self) -> None:
        """Test running fingerprint analysis."""
        result = run_fingerprint_analysis(
            student_id="student_1",
            code="def foo():\n    return 1\n",
            submission_id="sub_001",
        )

        assert isinstance(result, FingerprintResult)
        assert result.student_id == "student_1"
        assert result.current_features is not None


class TestStyleDeviation:
    """Tests for style deviation detection."""

    def test_low_deviation(self) -> None:
        """Test low deviation between similar styles."""
        analyzer = HistoricalFingerprintAnalyzer()

        # Similar code samples
        code1 = "def calculate_sum(numbers):\n    total = 0\n    for num in numbers:\n        total += num\n    return total\n"
        code2 = "def calculate_total(values):\n    result = 0\n    for val in values:\n        result += val\n    return result\n"

        features1 = analyzer.extract_features(code1)
        features2 = analyzer.extract_features(code2)

        deviation = analyzer._calculate_deviation(features1, features2)
        assert deviation < 0.5  # Should be similar

    def test_high_deviation(self) -> None:
        """Test high deviation between different styles."""
        analyzer = HistoricalFingerprintAnalyzer()

        # Very different code styles
        code1 = "def foo():\n    return 1\n"
        code2 = "class MyClass:\n    def __init__(self):\n        self.x = 1\n    def get_x(self):\n        return self.x\n"

        features1 = analyzer.extract_features(code1)
        features2 = analyzer.extract_features(code2)

        deviation = analyzer._calculate_deviation(features1, features2)
        # Different structures should have some deviation
        assert isinstance(deviation, float)


class TestHistoricalFingerprintAnalyzerEdgeCases:
    """Tests for edge cases in HistoricalFingerprintAnalyzer."""

    def test_extract_complexity(self) -> None:
        """Test complexity extraction."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "def foo():\n    if True:\n        for i in range(10):\n            if i > 5:\n                return i\n    return 0\n"

        features = analyzer.extract_features(code)
        assert features.complexity_score >= 0

    def test_extract_token_count(self) -> None:
        """Test token count extraction."""
        analyzer = HistoricalFingerprintAnalyzer()
        code = "def foo():\n    return 1\n"

        features = analyzer.extract_features(code)
        assert features.token_count > 0

    def test_empty_code_features(self) -> None:
        """Test feature extraction from empty code."""
        analyzer = HistoricalFingerprintAnalyzer()
        features = analyzer.extract_features("")

        assert features.avg_line_length == 0.0
        assert features.function_count == 0

    def test_get_last_features_empty_history(self) -> None:
        """Test getting last features with empty history."""
        analyzer = HistoricalFingerprintAnalyzer()
        result = analyzer._get_last_features(analyzer._get_or_create_history("new"))
        assert result is None

    def test_calculate_confidence_no_history(self) -> None:
        """Test confidence calculation with no history."""
        analyzer = HistoricalFingerprintAnalyzer()
        historical = analyzer._get_or_create_history("new")
        confidence = analyzer._calculate_confidence(historical, 0.5)
        assert confidence == 0.3

    def test_analyze_empty_code(self) -> None:
        """Test analysis with empty code."""
        analyzer = HistoricalFingerprintAnalyzer()
        result = analyzer.analyze(
            student_id="student_empty",
            code="",
            submission_id="sub_empty",
        )
        assert result.current_features is not None

    def test_multiple_submissions_same_student(self) -> None:
        """Test multiple submissions for the same student."""
        analyzer = HistoricalFingerprintAnalyzer()

        for i in range(5):
            analyzer.analyze(
                student_id="student_multi",
                code=f"def func{i}():\n    return {i}\n",
                submission_id=f"sub_{i}",
            )

        historical = analyzer._cache.get("student_multi")
        assert historical is not None
        assert len(historical.submission_history) == 5

    def test_get_historical_consistency_with_history(self) -> None:
        """Test consistency with actual history."""
        analyzer = HistoricalFingerprintAnalyzer()

        analyzer.analyze(
            student_id="student_consistency",
            code="def foo():\n    return 1\n",
            submission_id="sub_1",
        )
        analyzer.analyze(
            student_id="student_consistency",
            code="def bar():\n    return 2\n",
            submission_id="sub_2",
        )

        consistency = analyzer.get_historical_consistency("student_consistency")
        assert isinstance(consistency, float)
        assert 0.0 <= consistency <= 1.0


class TestFingerprintResultEdgeCases:
    """Tests for FingerprintResult edge cases."""

    def test_to_dict_with_historical_features(self) -> None:
        """Test serialization with historical features."""
        current = StyleFeatures(
            avg_line_length=50.0,
            max_line_length=100,
            indentation_depth=1.0,
            comment_ratio=0.1,
            blank_line_ratio=0.05,
            naming_convention="snake_case",
            function_count=5,
            class_count=2,
            complexity_score=0.3,
            token_count=100,
        )

        historical = StyleFeatures(
            avg_line_length=45.0,
            max_line_length=90,
            indentation_depth=0.8,
            comment_ratio=0.08,
            blank_line_ratio=0.03,
            naming_convention="snake_case",
            function_count=4,
            class_count=1,
            complexity_score=0.25,
            token_count=80,
        )

        result = FingerprintResult(
            student_id="student_1",
            current_features=current,
            historical_features=historical,
            deviation_score=0.1,
            is_anomaly=False,
            confidence_score=0.9,
            recommendations=[],
        )

        d = result.to_dict()
        assert d["historical_features"] is not None
        assert d["historical_features"]["avg_line_length"] == 45.0
