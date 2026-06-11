"""Unit tests for AI Detector data models.

Tests the SignalScores and AIDetectionResult classes to ensure:
- All scores are properly bounded [0.0, 1.0]
- Weights sum to 1.0
- Validation catches invalid inputs
- Serialization/deserialization works correctly
"""

import pytest
from src.backend.engines.ai.models import SignalScores, AIDetectionResult


class TestSignalScores:
    """Tests for SignalScores data model."""
    
    def test_valid_signal_scores(self):
        """Test creating valid signal scores."""
        scores = SignalScores(
            perplexity=0.5,
            burstiness=0.6,
            stylometry=0.7,
            pattern_library=0.8,
            structural_entropy=0.4,
            vocabulary_richness=0.3,
            whitespace_rhythm=0.2,
            docstring_density=0.1,
        )
        assert scores.perplexity == 0.5
        assert scores.burstiness == 0.6
    
    def test_default_signal_scores(self):
        """Test creating signal scores with defaults."""
        scores = SignalScores()
        assert scores.perplexity == 0.0
        assert scores.burstiness == 0.0
        assert scores.stylometry == 0.0
    
    def test_signal_score_bounds_too_low(self):
        """Test that scores below 0.0 are rejected."""
        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            SignalScores(perplexity=-0.1)
    
    def test_signal_score_bounds_too_high(self):
        """Test that scores above 1.0 are rejected."""
        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            SignalScores(perplexity=1.1)
    
    def test_signal_score_boundary_zero(self):
        """Test that score of 0.0 is valid."""
        scores = SignalScores(perplexity=0.0)
        assert scores.perplexity == 0.0
    
    def test_signal_score_boundary_one(self):
        """Test that score of 1.0 is valid."""
        scores = SignalScores(perplexity=1.0)
        assert scores.perplexity == 1.0
    
    def test_weights_sum_to_one(self):
        """Test that signal weights sum to 1.0."""
        weight_sum = sum(SignalScores.WEIGHTS.values())
        assert abs(weight_sum - 1.0) < 1e-9
    
    def test_to_dict(self):
        """Test converting signal scores to dictionary."""
        scores = SignalScores(
            perplexity=0.5,
            burstiness=0.6,
            stylometry=0.7,
            pattern_library=0.8,
            structural_entropy=0.4,
            vocabulary_richness=0.3,
            whitespace_rhythm=0.2,
            docstring_density=0.1,
        )
        result = scores.to_dict()
        assert result['perplexity'] == 0.5
        assert result['burstiness'] == 0.6
        assert len(result) == 8
    
    def test_from_dict(self):
        """Test creating signal scores from dictionary."""
        data = {
            'perplexity': 0.5,
            'burstiness': 0.6,
            'stylometry': 0.7,
            'pattern_library': 0.8,
            'structural_entropy': 0.4,
            'vocabulary_richness': 0.3,
            'whitespace_rhythm': 0.2,
            'docstring_density': 0.1,
        }
        scores = SignalScores.from_dict(data)
        assert scores.perplexity == 0.5
        assert scores.burstiness == 0.6
    
    def test_from_dict_with_missing_fields(self):
        """Test creating signal scores from incomplete dictionary."""
        data = {'perplexity': 0.5}
        scores = SignalScores.from_dict(data)
        assert scores.perplexity == 0.5
        assert scores.burstiness == 0.0


class TestAIDetectionResult:
    """Tests for AIDetectionResult data model."""
    
    def test_valid_result(self):
        """Test creating a valid detection result."""
        signals = SignalScores(perplexity=0.5, burstiness=0.6)
        result = AIDetectionResult(
            ai_probability=0.65,
            confidence=0.8,
            signals=signals,
            signal_labels={'perplexity': 'Token Entropy'},
            indicators=['Pattern 1', 'Pattern 2'],
            flagged_lines=[5, 10, 15],
            language='python',
        )
        assert result.ai_probability == 0.65
        assert result.confidence == 0.8
    
    def test_ai_probability_bounds_too_low(self):
        """Test that ai_probability below 0.0 is rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="ai_probability must be in \\[0.0, 1.0\\]"):
            AIDetectionResult(
                ai_probability=-0.1,
                confidence=0.5,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=[],
            )
    
    def test_ai_probability_bounds_too_high(self):
        """Test that ai_probability above 1.0 is rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="ai_probability must be in \\[0.0, 1.0\\]"):
            AIDetectionResult(
                ai_probability=1.1,
                confidence=0.5,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=[],
            )
    
    def test_confidence_bounds_too_low(self):
        """Test that confidence below 0.0 is rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="confidence must be in \\[0.0, 1.0\\]"):
            AIDetectionResult(
                ai_probability=0.5,
                confidence=-0.1,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=[],
            )
    
    def test_confidence_bounds_too_high(self):
        """Test that confidence above 1.0 is rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="confidence must be in \\[0.0, 1.0\\]"):
            AIDetectionResult(
                ai_probability=0.5,
                confidence=1.1,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=[],
            )
    
    def test_too_many_indicators(self):
        """Test that more than 6 indicators are rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="indicators must have at most 6 items"):
            AIDetectionResult(
                ai_probability=0.5,
                confidence=0.5,
                signals=signals,
                signal_labels={},
                indicators=['1', '2', '3', '4', '5', '6', '7'],
                flagged_lines=[],
            )
    
    def test_too_many_flagged_lines(self):
        """Test that more than 30 flagged lines are rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="flagged_lines must have at most 30 items"):
            AIDetectionResult(
                ai_probability=0.5,
                confidence=0.5,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=list(range(1, 32)),
            )
    
    def test_invalid_flagged_line_number(self):
        """Test that invalid line numbers are rejected."""
        signals = SignalScores()
        with pytest.raises(ValueError, match="each flagged line must be a positive integer"):
            AIDetectionResult(
                ai_probability=0.5,
                confidence=0.5,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=[0],  # Line numbers must be >= 1
            )
    
    def test_risk_level_low(self):
        """Test risk level classification for low probability."""
        signals = SignalScores()
        result = AIDetectionResult(
            ai_probability=0.3,
            confidence=0.5,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert result.risk_level == 'Low'
    
    def test_risk_level_medium(self):
        """Test risk level classification for medium probability."""
        signals = SignalScores()
        result = AIDetectionResult(
            ai_probability=0.55,
            confidence=0.5,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert result.risk_level == 'Medium'
    
    def test_risk_level_high(self):
        """Test risk level classification for high probability."""
        signals = SignalScores()
        result = AIDetectionResult(
            ai_probability=0.8,
            confidence=0.5,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert result.risk_level == 'High'
    
    def test_risk_level_boundary_low_medium(self):
        """Test risk level boundary between low and medium."""
        signals = SignalScores()
        result = AIDetectionResult(
            ai_probability=0.45,
            confidence=0.5,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert result.risk_level == 'Medium'
    
    def test_risk_level_boundary_medium_high(self):
        """Test risk level boundary between medium and high."""
        signals = SignalScores()
        result = AIDetectionResult(
            ai_probability=0.70,
            confidence=0.5,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert result.risk_level == 'High'
    
    def test_confidence_levels(self):
        """Test confidence level classification."""
        signals = SignalScores()
        
        # High confidence
        result_high = AIDetectionResult(
            ai_probability=0.5,
            confidence=0.8,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert result_high.is_high_confidence
        assert not result_high.is_medium_confidence
        assert not result_high.is_low_confidence
        
        # Medium confidence
        result_medium = AIDetectionResult(
            ai_probability=0.5,
            confidence=0.5,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert not result_medium.is_high_confidence
        assert result_medium.is_medium_confidence
        assert not result_medium.is_low_confidence
        
        # Low confidence
        result_low = AIDetectionResult(
            ai_probability=0.5,
            confidence=0.2,
            signals=signals,
            signal_labels={},
            indicators=[],
            flagged_lines=[],
        )
        assert not result_low.is_high_confidence
        assert not result_low.is_medium_confidence
        assert result_low.is_low_confidence
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        signals = SignalScores(perplexity=0.5)
        result = AIDetectionResult(
            ai_probability=0.65,
            confidence=0.8,
            signals=signals,
            signal_labels={'perplexity': 'Token Entropy'},
            indicators=['Pattern 1'],
            flagged_lines=[5],
            language='python',
        )
        result_dict = result.to_dict()
        assert result_dict['ai_probability'] == 0.65
        assert result_dict['confidence'] == 0.8
        assert result_dict['language'] == 'python'
    
    def test_from_dict(self):
        """Test creating result from dictionary."""
        data = {
            'ai_probability': 0.65,
            'confidence': 0.8,
            'signals': {'perplexity': 0.5},
            'signal_labels': {'perplexity': 'Token Entropy'},
            'indicators': ['Pattern 1'],
            'flagged_lines': [5],
            'language': 'python',
        }
        result = AIDetectionResult.from_dict(data)
        assert result.ai_probability == 0.65
        assert result.confidence == 0.8
        assert result.language == 'python'


class TestPropertyBounds:
    """Property-based tests for score bounds (Property 1)."""
    
    def test_all_signal_scores_bounded(self):
        """Property: All signal scores must be in [0.0, 1.0]."""
        # Test with various valid scores
        for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
            signals = SignalScores(
                perplexity=score,
                burstiness=score,
                stylometry=score,
                pattern_library=score,
                structural_entropy=score,
                vocabulary_richness=score,
                whitespace_rhythm=score,
                docstring_density=score,
            )
            assert 0.0 <= signals.perplexity <= 1.0
            assert 0.0 <= signals.burstiness <= 1.0
    
    def test_result_probabilities_bounded(self):
        """Property: Result probabilities must be in [0.0, 1.0]."""
        signals = SignalScores()
        for prob in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = AIDetectionResult(
                ai_probability=prob,
                confidence=prob,
                signals=signals,
                signal_labels={},
                indicators=[],
                flagged_lines=[],
            )
            assert 0.0 <= result.ai_probability <= 1.0
            assert 0.0 <= result.confidence <= 1.0
