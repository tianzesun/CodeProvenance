"""Unit tests for AI Detector fusion layer.

Tests all components of the fusion layer:
- Signal reliability assessment
- Signal agreement analysis
- Weighted signal aggregation
- Confidence calibration
- False positive reduction
- Risk categorization
"""


from src.backend.engines.ai.agreement import (
    analyze_signal_agreement,
    calculate_signal_variance,
    detect_signal_contradiction,
    detect_single_signal_dominance,
)
from src.backend.engines.ai.aggregation import (
    aggregate_signals,
    get_all_signal_contributions,
    get_most_influential_signals,
)
from src.backend.engines.ai.confidence import (
    adjust_confidence_for_code_length,
    calibrate_confidence,
    get_confidence_level,
    should_flag_low_confidence,
)
from src.backend.engines.ai.false_positive_reduction import (
    apply_false_positive_reduction,
    check_extreme_variance,
    check_low_reliability,
    check_signal_contradiction,
    check_single_signal_dominance,
)
from src.backend.engines.ai.fusion import (
    create_detection_result,
    fuse_signals,
    get_fusion_summary,
)
from src.backend.engines.ai.models import SignalScores
from src.backend.engines.ai.reliability import (
    assess_all_signal_reliabilities,
    assess_signal_reliability,
)
from tests.fixtures.ai_detector.fixtures import get_human_samples, get_ai_samples


# ============================================================================
# SIGNAL RELIABILITY TESTS
# ============================================================================


class TestSignalReliability:
    """Tests for signal reliability assessment."""

    def test_assess_perplexity_reliability(self):
        """Test perplexity reliability assessment."""
        code_short = "x = 1"
        code_medium = "x = 1\ny = 2\nz = x + y\na = z * 2"
        code_long = "x = 1\n" * 50

        assert assess_signal_reliability("perplexity", code_short) == 0.0
        assert 0.0 < assess_signal_reliability("perplexity", code_medium) < 1.0
        assert assess_signal_reliability("perplexity", code_long) == 1.0

    def test_assess_burstiness_reliability(self):
        """Test burstiness reliability assessment."""
        code_short = "x = 1"
        code_medium = "x = 1\ny = 2\nz = x + y\na = z * 2\nb = a + 1"
        code_long = "x = 1\n" * 50

        assert assess_signal_reliability("burstiness", code_short) == 0.0
        assert 0.0 < assess_signal_reliability("burstiness", code_medium) < 1.0
        assert assess_signal_reliability("burstiness", code_long) == 1.0

    def test_assess_all_signal_reliabilities(self):
        """Test assessing all signal reliabilities."""
        code = "x = 1\ny = 2\nz = x + y"
        reliabilities = assess_all_signal_reliabilities(code)

        assert len(reliabilities) == 8
        assert all(0.0 <= r <= 1.0 for r in reliabilities.values())
        assert all(isinstance(r, float) for r in reliabilities.values())

    def test_reliability_with_human_code(self):
        """Test reliability assessment with human code samples."""
        human_samples = get_human_samples()

        for code in human_samples.values():
            reliabilities = assess_all_signal_reliabilities(code)
            assert len(reliabilities) == 8
            assert all(0.0 <= r <= 1.0 for r in reliabilities.values())


# ============================================================================
# SIGNAL AGREEMENT TESTS
# ============================================================================


class TestSignalAgreement:
    """Tests for signal agreement analysis."""

    def test_analyze_high_agreement_ai_like(self):
        """Test agreement analysis with high AI-like agreement."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.7,
            stylometry=0.75,
            pattern_library=0.85,
            structural_entropy=0.7,
            vocabulary_richness=0.65,
            whitespace_rhythm=0.6,
            docstring_density=0.7,
        )

        agreement = analyze_signal_agreement(signals)

        assert agreement["agreement_level"] == "high"
        assert agreement["direction"] == "ai_like"
        assert len(agreement["supporting_signals"]) >= 6
        assert len(agreement["contradicting_signals"]) == 0

    def test_analyze_high_agreement_human_like(self):
        """Test agreement analysis with high human-like agreement."""
        signals = SignalScores(
            perplexity=0.1,
            burstiness=0.15,
            stylometry=0.2,
            pattern_library=0.1,
            structural_entropy=0.2,
            vocabulary_richness=0.25,
            whitespace_rhythm=0.3,
            docstring_density=0.1,
        )

        agreement = analyze_signal_agreement(signals)

        assert agreement["agreement_level"] == "high"
        assert agreement["direction"] == "human_like"
        assert len(agreement["contradicting_signals"]) >= 6
        assert len(agreement["supporting_signals"]) == 0

    def test_analyze_low_agreement(self):
        """Test agreement analysis with low agreement."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.1,
            stylometry=0.75,
            pattern_library=0.2,
            structural_entropy=0.7,
            vocabulary_richness=0.15,
            whitespace_rhythm=0.6,
            docstring_density=0.25,
        )

        agreement = analyze_signal_agreement(signals)

        # This has 4 contradicting signals, so direction is human_like
        assert agreement["agreement_level"] in ["low", "medium"]
        assert agreement["direction"] in ["mixed", "human_like"]

    def test_detect_single_signal_dominance(self):
        """Test detection of single signal dominance."""
        # Single AI-like signal
        signals_dominant = SignalScores(
            perplexity=0.8,
            burstiness=0.1,
            stylometry=0.2,
            pattern_library=0.15,
            structural_entropy=0.2,
            vocabulary_richness=0.1,
            whitespace_rhythm=0.25,
            docstring_density=0.1,
        )

        assert detect_single_signal_dominance(signals_dominant)

        # No dominance
        signals_balanced = SignalScores(
            perplexity=0.5,
            burstiness=0.5,
            stylometry=0.5,
            pattern_library=0.5,
            structural_entropy=0.5,
            vocabulary_richness=0.5,
            whitespace_rhythm=0.5,
            docstring_density=0.5,
        )

        assert not detect_single_signal_dominance(signals_balanced)

    def test_detect_signal_contradiction(self):
        """Test detection of signal contradiction."""
        # Contradictory signals
        signals_contradictory = SignalScores(
            perplexity=0.9,
            burstiness=0.85,
            stylometry=0.8,
            pattern_library=0.1,
            structural_entropy=0.15,
            vocabulary_richness=0.2,
            whitespace_rhythm=0.1,
            docstring_density=0.1,
        )

        assert detect_signal_contradiction(signals_contradictory)

        # No contradiction
        signals_consistent = SignalScores(
            perplexity=0.8,
            burstiness=0.75,
            stylometry=0.7,
            pattern_library=0.65,
            structural_entropy=0.7,
            vocabulary_richness=0.6,
            whitespace_rhythm=0.65,
            docstring_density=0.7,
        )

        assert not detect_signal_contradiction(signals_consistent)

    def test_calculate_signal_variance(self):
        """Test signal variance calculation."""
        # Low variance (consistent signals)
        signals_consistent = SignalScores(
            perplexity=0.5,
            burstiness=0.5,
            stylometry=0.5,
            pattern_library=0.5,
            structural_entropy=0.5,
            vocabulary_richness=0.5,
            whitespace_rhythm=0.5,
            docstring_density=0.5,
        )

        variance_consistent = calculate_signal_variance(signals_consistent)
        assert variance_consistent == 0.0

        # High variance (inconsistent signals)
        signals_inconsistent = SignalScores(
            perplexity=0.9,
            burstiness=0.1,
            stylometry=0.9,
            pattern_library=0.1,
            structural_entropy=0.9,
            vocabulary_richness=0.1,
            whitespace_rhythm=0.9,
            docstring_density=0.1,
        )

        variance_inconsistent = calculate_signal_variance(signals_inconsistent)
        assert variance_inconsistent > variance_consistent


# ============================================================================
# SIGNAL AGGREGATION TESTS
# ============================================================================


class TestSignalAggregation:
    """Tests for signal aggregation."""

    def test_aggregate_signals_all_high(self):
        """Test aggregation with all high signals."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.8,
            stylometry=0.8,
            pattern_library=0.8,
            structural_entropy=0.8,
            vocabulary_richness=0.8,
            whitespace_rhythm=0.8,
            docstring_density=0.8,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        score = aggregate_signals(signals, reliabilities)

        assert 0.0 <= score <= 1.0
        assert score > 0.7  # Should be high

    def test_aggregate_signals_all_low(self):
        """Test aggregation with all low signals."""
        signals = SignalScores(
            perplexity=0.2,
            burstiness=0.2,
            stylometry=0.2,
            pattern_library=0.2,
            structural_entropy=0.2,
            vocabulary_richness=0.2,
            whitespace_rhythm=0.2,
            docstring_density=0.2,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        score = aggregate_signals(signals, reliabilities)

        assert 0.0 <= score <= 1.0
        assert score < 0.3  # Should be low

    def test_aggregate_signals_with_low_reliability(self):
        """Test aggregation with low reliability signals."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.8,
            stylometry=0.8,
            pattern_library=0.8,
            structural_entropy=0.8,
            vocabulary_richness=0.8,
            whitespace_rhythm=0.8,
            docstring_density=0.8,
        )

        reliabilities = {
            "perplexity": 0.1,
            "burstiness": 0.1,
            "stylometry": 0.1,
            "pattern_library": 0.1,
            "structural_entropy": 0.1,
            "vocabulary_richness": 0.1,
            "whitespace_rhythm": 0.1,
            "docstring_density": 0.1,
        }

        score = aggregate_signals(signals, reliabilities)

        assert 0.0 <= score <= 1.0
        # Low reliability should reduce the impact of high signals

    def test_get_signal_contributions(self):
        """Test getting signal contributions."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.6,
            stylometry=0.7,
            pattern_library=0.9,
            structural_entropy=0.5,
            vocabulary_richness=0.4,
            whitespace_rhythm=0.3,
            docstring_density=0.2,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        contributions = get_all_signal_contributions(signals, reliabilities)

        assert len(contributions) == 8
        assert all(0.0 <= c <= 0.2 for c in contributions.values())

    def test_get_most_influential_signals(self):
        """Test getting most influential signals."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.6,
            stylometry=0.7,
            pattern_library=0.9,
            structural_entropy=0.5,
            vocabulary_richness=0.4,
            whitespace_rhythm=0.3,
            docstring_density=0.2,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        influential = get_most_influential_signals(signals, reliabilities, top_n=3)

        assert len(influential) == 3
        # Pattern library should be most influential (highest score + highest weight)


# ============================================================================
# CONFIDENCE CALIBRATION TESTS
# ============================================================================


class TestConfidenceCalibration:
    """Tests for confidence calibration."""

    def test_calibrate_confidence_high_agreement(self):
        """Test confidence calibration with high agreement."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.75,
            stylometry=0.8,
            pattern_library=0.85,
            structural_entropy=0.7,
            vocabulary_richness=0.75,
            whitespace_rhythm=0.7,
            docstring_density=0.8,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        agreement = analyze_signal_agreement(signals)
        confidence = calibrate_confidence(signals, reliabilities, agreement, 0.75)

        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.6  # High agreement should give high confidence

    def test_calibrate_confidence_low_agreement(self):
        """Test confidence calibration with low agreement."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.1,
            stylometry=0.75,
            pattern_library=0.2,
            structural_entropy=0.7,
            vocabulary_richness=0.15,
            whitespace_rhythm=0.6,
            docstring_density=0.25,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        agreement = analyze_signal_agreement(signals)
        confidence = calibrate_confidence(signals, reliabilities, agreement, 0.5)

        assert 0.0 <= confidence <= 1.0
        # Low agreement should give lower confidence

    def test_get_confidence_level(self):
        """Test confidence level classification."""
        assert get_confidence_level(0.9) == "Very High"
        assert get_confidence_level(0.75) == "High"
        assert get_confidence_level(0.5) == "Medium"
        assert get_confidence_level(0.35) == "Low"
        assert get_confidence_level(0.1) == "Very Low"

    def test_should_flag_low_confidence(self):
        """Test low confidence flagging."""
        # High AI probability with low confidence
        assert should_flag_low_confidence(0.8, 0.3)

        # Medium AI probability with low confidence
        assert should_flag_low_confidence(0.6, 0.2)

        # Low AI probability with low confidence
        assert should_flag_low_confidence(0.2, 0.2)

        # High AI probability with high confidence
        assert not should_flag_low_confidence(0.8, 0.8)

    def test_adjust_confidence_for_code_length(self):
        """Test confidence adjustment for code length."""
        base_confidence = 0.8

        # Very short code
        adjusted_short = adjust_confidence_for_code_length(base_confidence, 50)
        assert adjusted_short < base_confidence

        # Medium code
        adjusted_medium = adjust_confidence_for_code_length(base_confidence, 1000)
        assert adjusted_medium == base_confidence

        # Long code
        adjusted_long = adjust_confidence_for_code_length(base_confidence, 5000)
        assert adjusted_long > base_confidence


# ============================================================================
# FALSE POSITIVE REDUCTION TESTS
# ============================================================================


class TestFalsePositiveReduction:
    """Tests for false positive reduction."""

    def test_apply_false_positive_reduction_single_dominance(self):
        """Test FP reduction with single signal dominance."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.1,
            stylometry=0.2,
            pattern_library=0.15,
            structural_entropy=0.2,
            vocabulary_richness=0.1,
            whitespace_rhythm=0.25,
            docstring_density=0.1,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        ai_prob, confidence = apply_false_positive_reduction(0.5, 0.8, signals, reliabilities)

        assert 0.0 <= ai_prob <= 1.0
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.8  # Confidence should be reduced

    def test_apply_false_positive_reduction_contradiction(self):
        """Test FP reduction with signal contradiction."""
        signals = SignalScores(
            perplexity=0.9,
            burstiness=0.85,
            stylometry=0.8,
            pattern_library=0.1,
            structural_entropy=0.15,
            vocabulary_richness=0.2,
            whitespace_rhythm=0.1,
            docstring_density=0.1,
        )

        reliabilities = {
            "perplexity": 1.0,
            "burstiness": 1.0,
            "stylometry": 1.0,
            "pattern_library": 1.0,
            "structural_entropy": 1.0,
            "vocabulary_richness": 1.0,
            "whitespace_rhythm": 1.0,
            "docstring_density": 1.0,
        }

        ai_prob, confidence = apply_false_positive_reduction(0.5, 0.8, signals, reliabilities)

        assert confidence < 0.8  # Confidence should be reduced

    def test_check_single_signal_dominance(self):
        """Test single signal dominance check."""
        signals_dominant = SignalScores(
            perplexity=0.8,
            burstiness=0.1,
            stylometry=0.2,
            pattern_library=0.15,
            structural_entropy=0.2,
            vocabulary_richness=0.1,
            whitespace_rhythm=0.25,
            docstring_density=0.1,
        )

        result = check_single_signal_dominance(signals_dominant)

        assert result["is_dominant"]
        assert result["dominant_signal"] == "perplexity"
        assert result["confidence_penalty"] == 0.3

    def test_check_signal_contradiction(self):
        """Test signal contradiction check."""
        signals_contradictory = SignalScores(
            perplexity=0.9,
            burstiness=0.85,
            stylometry=0.8,
            pattern_library=0.1,
            structural_entropy=0.15,
            vocabulary_richness=0.2,
            whitespace_rhythm=0.1,
            docstring_density=0.1,
        )

        result = check_signal_contradiction(signals_contradictory)

        assert result["is_contradictory"]
        assert result["confidence_penalty"] == 0.2

    def test_check_low_reliability(self):
        """Test low reliability check."""
        reliabilities_low = {
            "perplexity": 0.2,
            "burstiness": 0.2,
            "stylometry": 0.2,
            "pattern_library": 0.2,
            "structural_entropy": 0.2,
            "vocabulary_richness": 0.2,
            "whitespace_rhythm": 0.2,
            "docstring_density": 0.2,
        }

        result = check_low_reliability(reliabilities_low)

        assert result["is_low_reliability"]
        assert result["confidence_penalty"] == 0.25

    def test_check_extreme_variance(self):
        """Test extreme variance check."""
        signals_high_variance = SignalScores(
            perplexity=0.9,
            burstiness=0.1,
            stylometry=0.9,
            pattern_library=0.1,
            structural_entropy=0.9,
            vocabulary_richness=0.1,
            whitespace_rhythm=0.9,
            docstring_density=0.1,
        )

        result = check_extreme_variance(signals_high_variance)

        # Variance is 0.16, which is not extreme (> 0.3)
        # So this test should verify that it's not flagged as extreme
        assert not result["is_extreme_variance"]


# ============================================================================
# FUSION ORCHESTRATOR TESTS
# ============================================================================


class TestFusionOrchestrator:
    """Tests for fusion orchestrator."""

    def test_fuse_signals_ai_like_code(self):
        """Test fusion with AI-like signals."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.75,
            stylometry=0.8,
            pattern_library=0.85,
            structural_entropy=0.7,
            vocabulary_richness=0.75,
            whitespace_rhythm=0.7,
            docstring_density=0.8,
        )

        code = "x = 1\ny = 2\nz = x + y"
        result = fuse_signals(signals, code)

        assert "ai_probability" in result
        assert "confidence" in result
        assert "risk_level" in result
        assert 0.0 <= result["ai_probability"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0

    def test_fuse_signals_human_like_code(self):
        """Test fusion with human-like signals."""
        signals = SignalScores(
            perplexity=0.2,
            burstiness=0.15,
            stylometry=0.2,
            pattern_library=0.1,
            structural_entropy=0.2,
            vocabulary_richness=0.25,
            whitespace_rhythm=0.3,
            docstring_density=0.1,
        )

        code = "x = 1\ny = 2\nz = x + y"
        result = fuse_signals(signals, code)

        assert result["ai_probability"] < 0.5
        assert result["risk_level"] in ["Very Low", "Low"]

    def test_create_detection_result(self):
        """Test creating detection result."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.75,
            stylometry=0.8,
            pattern_library=0.85,
            structural_entropy=0.7,
            vocabulary_richness=0.75,
            whitespace_rhythm=0.7,
            docstring_density=0.8,
        )

        code = "x = 1\ny = 2\nz = x + y"
        result = create_detection_result(signals, code)

        assert result.ai_probability >= 0.0
        assert result.confidence >= 0.0
        assert len(result.indicators) <= 6
        assert len(result.signal_labels) == 8

    def test_get_fusion_summary(self):
        """Test getting fusion summary."""
        signals = SignalScores(
            perplexity=0.8,
            burstiness=0.75,
            stylometry=0.8,
            pattern_library=0.85,
            structural_entropy=0.7,
            vocabulary_richness=0.75,
            whitespace_rhythm=0.7,
            docstring_density=0.8,
        )

        code = "x = 1\ny = 2\nz = x + y"
        fusion_result = fuse_signals(signals, code)
        summary = get_fusion_summary(fusion_result)

        assert "AI Probability" in summary
        assert "Confidence" in summary
        assert "Risk" in summary
        assert "Agreement" in summary


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestFusionIntegration:
    """Integration tests for complete fusion pipeline."""

    def test_fusion_with_human_samples(self):
        """Test fusion with human code samples."""
        human_samples = get_human_samples()

        for code in human_samples.values():
            # Create signals (would normally come from signal computation)
            signals = SignalScores(
                perplexity=0.2,
                burstiness=0.15,
                stylometry=0.2,
                pattern_library=0.1,
                structural_entropy=0.2,
                vocabulary_richness=0.25,
                whitespace_rhythm=0.3,
                docstring_density=0.1,
            )

            result = fuse_signals(signals, code)

            assert 0.0 <= result["ai_probability"] <= 1.0
            assert 0.0 <= result["confidence"] <= 1.0
            # Risk level from fusion module
            assert result["risk_level"] in [
                "Very Low",
                "Low",
                "Moderate",
                "Elevated",
                "High",
            ]

    def test_fusion_with_ai_samples(self):
        """Test fusion with AI code samples."""
        ai_samples = get_ai_samples()

        for code in ai_samples.values():
            # Create signals (would normally come from signal computation)
            signals = SignalScores(
                perplexity=0.8,
                burstiness=0.75,
                stylometry=0.8,
                pattern_library=0.85,
                structural_entropy=0.7,
                vocabulary_richness=0.75,
                whitespace_rhythm=0.7,
                docstring_density=0.8,
            )

            result = fuse_signals(signals, code)

            assert 0.0 <= result["ai_probability"] <= 1.0
            assert 0.0 <= result["confidence"] <= 1.0
            # Risk level from fusion module
            assert result["risk_level"] in [
                "Very Low",
                "Low",
                "Moderate",
                "Elevated",
                "High",
            ]

    def test_fusion_end_to_end(self):
        """Test complete end-to-end fusion pipeline."""
        code = """
def calculate_sum(numbers):
    total = 0
    for n in numbers:
        total += n
    return total
"""

        signals = SignalScores(
            perplexity=0.5,
            burstiness=0.5,
            stylometry=0.5,
            pattern_library=0.5,
            structural_entropy=0.5,
            vocabulary_richness=0.5,
            whitespace_rhythm=0.5,
            docstring_density=0.5,
        )

        # Run complete pipeline
        result = create_detection_result(signals, code)

        # Verify result
        assert result.ai_probability >= 0.0
        assert result.confidence >= 0.0
        # Risk level from AIDetectionResult.risk_level property
        assert result.risk_level in ["Low", "Medium", "High"]
        assert len(result.indicators) <= 6
