"""Unit tests for token-level heatmap module."""
import pytest
from src.core.token_heatmap.models import (
    TokenSpan,
    MatchType,
    HeatIntensity,
    HeatmapResult,
    CharacterMap,
    confidence_to_intensity,
)
from src.core.token_heatmap.extractor import ASTTokenExtractor
from src.core.token_heatmap.mapper import CharacterOffsetMapper
from src.core.token_heatmap.intensity import HeatIntensityCalculator
from src.core.token_heatmap.engine import TokenHeatmapEngine


# ─────────────────────────────────────────────
# Tests: Models
# ─────────────────────────────────────────────

class TestTokenSpan:
    """Tests for TokenSpan dataclass."""

    def test_basic_creation(self):
        span = TokenSpan(
            start=10,
            end=20,
            confidence=0.8,
            match_type=MatchType.AST,
        )
        assert span.start == 10
        assert span.end == 20
        assert span.confidence == 0.8
        assert span.match_type == MatchType.AST
        assert span.length == 10

    def test_intensity_property(self):
        assert TokenSpan(0, 10, 0.9, MatchType.AST).intensity == HeatIntensity.CRITICAL
        assert TokenSpan(0, 10, 0.75, MatchType.AST).intensity == HeatIntensity.HIGH
        assert TokenSpan(0, 10, 0.6, MatchType.AST).intensity == HeatIntensity.MEDIUM
        assert TokenSpan(0, 10, 0.4, MatchType.AST).intensity == HeatIntensity.LOW
        assert TokenSpan(0, 10, 0.2, MatchType.AST).intensity == HeatIntensity.NONE

    def test_overlaps(self):
        a = TokenSpan(0, 10, 0.5, MatchType.TOKEN)
        b = TokenSpan(5, 15, 0.6, MatchType.TOKEN)
        c = TokenSpan(10, 20, 0.7, MatchType.TOKEN)  # No overlap (end is exclusive)
        d = TokenSpan(20, 30, 0.8, MatchType.TOKEN)

        assert a.overlaps(b)
        assert b.overlaps(a)
        assert not a.overlaps(c)
        assert not a.overlaps(d)

    def test_contains_offset(self):
        span = TokenSpan(10, 20, 0.5, MatchType.TOKEN)
        assert span.contains_offset(10)
        assert span.contains_offset(15)
        assert span.contains_offset(19)
        assert not span.contains_offset(9)
        assert not span.contains_offset(20)

    def test_intersect(self):
        a = TokenSpan(0, 10, 0.5, MatchType.TOKEN)
        b = TokenSpan(5, 15, 0.8, MatchType.AST)

        intersection = a.intersect(b)
        assert intersection is not None
        assert intersection.start == 5
        assert intersection.end == 10
        assert intersection.confidence == 0.8  # Max confidence
        assert intersection.match_type == MatchType.AST

    def test_intersect_no_overlap(self):
        a = TokenSpan(0, 10, 0.5, MatchType.TOKEN)
        b = TokenSpan(20, 30, 0.8, MatchType.AST)
        assert a.intersect(b) is None

    def test_to_dict(self):
        span = TokenSpan(
            start=10,
            end=25,
            confidence=0.75,
            match_type=MatchType.FUSED,
            token_type="function_call",
            matched_value="foo(bar)",
        )
        d = span.to_dict()
        assert d["start"] == 10
        assert d["end"] == 25
        assert d["confidence"] == 0.75
        assert d["match_type"] == "fused"
        assert d["token_type"] == "function_call"
        assert d["matched_value"] == "foo(bar)"
        assert d["intensity"] == HeatIntensity.HIGH.value

    def test_from_dict(self):
        data = {
            "start": 5,
            "end": 15,
            "confidence": 0.9,
            "match_type": "ast",
            "token_type": "identifier",
            "matched_value": "x",
        }
        span = TokenSpan.from_dict(data)
        assert span.start == 5
        assert span.end == 15
        assert span.confidence == 0.9
        assert span.match_type == MatchType.AST


class TestHeatmapResult:
    """Tests for HeatmapResult dataclass."""

    def test_empty_result(self):
        result = HeatmapResult.empty("A", "B")
        assert result.source_id == "A"
        assert result.target_id == "B"
        assert not result.has_results
        assert result.spans_a == []
        assert result.spans_b == []

    def test_has_results(self):
        result = HeatmapResult(
            source_id="A",
            target_id="B",
            spans_a=[TokenSpan(0, 10, 0.5, MatchType.TOKEN)],
        )
        assert result.has_results

    def test_compute_intensity_distribution(self):
        spans = [
            TokenSpan(0, 10, 0.9, MatchType.AST),
            TokenSpan(10, 20, 0.6, MatchType.TOKEN),
            TokenSpan(20, 30, 0.4, MatchType.TOKEN),
        ]
        result = HeatmapResult.empty()
        dist = result.compute_intensity_distribution(spans)
        
        assert HeatIntensity.CRITICAL.value in dist
        assert HeatIntensity.HIGH.value in dist
        assert HeatIntensity.MEDIUM.value in dist
        assert HeatIntensity.LOW.value in dist

    def test_to_dict(self):
        result = HeatmapResult(
            source_id="src1",
            target_id="src2",
            spans_a=[TokenSpan(0, 10, 0.5, MatchType.TOKEN)],
            overall_confidence=0.6,
            match_count=1,
        )
        d = result.to_dict()
        assert d["source_id"] == "src1"
        assert d["target_id"] == "src2"
        assert len(d["spans_a"]) == 1
        assert d["overall_confidence"] == 0.6
        assert d["match_count"] == 1


class TestCharacterMap:
    """Tests for CharacterMap class."""

    def test_build_simple(self):
        code = "line1\nline2\nline3"
        cmap = CharacterMap().build(code)
        assert cmap.line_offsets == [0, 6, 12]
        assert cmap.total_lines == 3
        assert cmap.total_chars == 17

    def test_offset_to_line_column(self):
        code = "hello\nworld\nfoo"
        cmap = CharacterMap().build(code)
        
        # "hello" starts at 0, "world" starts at 6, "foo" starts at 12
        assert cmap.offset_to_line_column(0) == (1, 0)
        assert cmap.offset_to_line_column(4) == (1, 4)    # 'o' in "hello"
        assert cmap.offset_to_line_column(6) == (2, 0)    # 'w' in "world"
        assert cmap.offset_to_line_column(12) == (3, 0)   # 'f' in "foo"

    def test_line_column_to_offset(self):
        code = "hello\nworld\nfoo"
        cmap = CharacterMap().build(code)
        
        assert cmap.line_column_to_offset(1, 0) == 0
        assert cmap.line_column_to_offset(2, 0) == 6
        assert cmap.line_column_to_offset(3, 2) == 14  # 'o' in "foo"

    def test_get_line_text(self):
        code = "hello\nworld\nfoo"
        cmap = CharacterMap().build(code)
        
        assert cmap.get_line_text(1) == "hello"
        assert cmap.get_line_text(2) == "world"
        assert cmap.get_line_text(3) == "foo"

    def test_span_to_line_range(self):
        code = "hello\nworld\nfoo"
        cmap = CharacterMap().build(code)
        
        span = TokenSpan(0, 11, 0.5, MatchType.TOKEN)  # "hello\nworl"
        line_range = cmap.span_to_line_range(span)
        assert line_range == (1, 2)


class TestConfidenceToIntensity:
    """Tests for confidence_to_intensity function."""

    def test_boundaries(self):
        assert confidence_to_intensity(0.0) == HeatIntensity.NONE
        assert confidence_to_intensity(0.31) == HeatIntensity.LOW
        assert confidence_to_intensity(0.51) == HeatIntensity.MEDIUM
        assert confidence_to_intensity(0.71) == HeatIntensity.HIGH
        assert confidence_to_intensity(0.86) == HeatIntensity.CRITICAL
        assert confidence_to_intensity(1.0) == HeatIntensity.CRITICAL


# ─────────────────────────────────────────────
# Tests: AST Token Extractor
# ─────────────────────────────────────────────

class TestASTTokenExtractor:
    """Tests for ASTTokenExtractor class."""

    def test_detect_language_python(self):
        extractor = ASTTokenExtractor()
        code = "def hello():\n    return 'world'"
        assert extractor.detect_language(code) == "python"

    def test_detect_language_javascript(self):
        extractor = ASTTokenExtractor()
        code = "function hello() { return 'world'; }"
        assert extractor.detect_language(code) == "javascript"

    def test_extract_fallback_tokens(self):
        extractor = ASTTokenExtractor()
        code = "x = 5"
        tokens = extractor.extract(code, "python")
        assert len(tokens) > 0
        # Should contain identifier 'x'
        types = [t["type"] for t in tokens]
        assert "identifier" in types

    def test_extract_preserves_offsets(self):
        extractor = ASTTokenExtractor()
        code = "hello world"
        tokens = extractor.extract(code)
        
        for token in tokens:
            assert token["start"] >= 0
            assert token["end"] > token["start"]
            assert token["end"] <= len(code)
            assert token["text"] == code[token["start"]:token["end"]]

    def test_extract_empty_code(self):
        extractor = ASTTokenExtractor()
        assert extractor.extract("") == []

    def test_extract_structures_python(self):
        extractor = ASTTokenExtractor()
        code = """def foo():
    return 1

def bar():
    return 2
"""
        structures = extractor.extract_structures(code)
        assert len(structures) >= 2
        names = [s["name"] for s in structures]
        assert "foo" in names
        assert "bar" in names


# ─────────────────────────────────────────────
# Tests: Character Offset Mapper
# ─────────────────────────────────────────────

class TestCharacterOffsetMapper:
    """Tests for CharacterOffsetMapper class."""

    def test_build_and_basic(self):
        mapper = CharacterOffsetMapper()
        mapper.build("hello\nworld")
        assert mapper.total_lines == 2
        assert mapper.total_chars == 11

    def test_merge_spans(self):
        mapper = CharacterOffsetMapper()
        mapper.build("hello world")
        
        spans = [
            {"start": 0, "end": 5},
            {"start": 3, "end": 8},
            {"start": 10, "end": 15},
        ]
        merged = mapper.merge_spans(spans)
        assert len(merged) == 2
        assert merged[0] == {"start": 0, "end": 8}
        assert merged[1] == {"start": 10, "end": 15}

    def test_merge_no_overlap(self):
        mapper = CharacterOffsetMapper()
        mapper.build("hello world")
        
        spans = [
            {"start": 0, "end": 3},
            {"start": 5, "end": 8},
        ]
        merged = mapper.merge_spans(spans)
        assert len(merged) == 2


# ─────────────────────────────────────────────
# Tests: Heat Intensity Calculator
# ─────────────────────────────────────────────

class TestHeatIntensityCalculator:
    """Tests for HeatIntensityCalculator class."""

    def test_static_to_intensity(self):
        assert HeatIntensityCalculator.to_intensity(0.9) == HeatIntensity.CRITICAL
        assert HeatIntensityCalculator.to_intensity(0.75) == HeatIntensity.HIGH
        assert HeatIntensityCalculator.to_intensity(0.6) == HeatIntensity.MEDIUM
        assert HeatIntensityCalculator.to_intensity(0.4) == HeatIntensity.LOW
        assert HeatIntensityCalculator.to_intensity(0.1) == HeatIntensity.NONE

    def test_calculate_intensity_ast_bonus(self):
        calc = HeatIntensityCalculator()
        span = TokenSpan(0, 10, 0.7, MatchType.AST)
        result = calc.calculate_intensity(span)
        # AST bonus is 0.15, so 0.7 + 0.15 = 0.85
        assert result.confidence == 0.85

    def test_calculate_intensity_fused_bonus(self):
        calc = HeatIntensityCalculator()
        span = TokenSpan(0, 10, 0.7, MatchType.FUSED)
        result = calc.calculate_intensity(span)
        # Fused bonus is 0.10, so 0.7 + 0.10 = 0.80
        assert result.confidence == 0.80

    def test_calculate_intensity_caps_at_one(self):
        calc = HeatIntensityCalculator()
        span = TokenSpan(0, 10, 0.95, MatchType.AST)
        result = calc.calculate_intensity(span)
        assert result.confidence == 1.0

    def test_merge_overlapping(self):
        calc = HeatIntensityCalculator()
        spans = [
            TokenSpan(0, 10, 0.5, MatchType.TOKEN),
            TokenSpan(5, 15, 0.8, MatchType.AST),
        ]
        merged = calc.merge_overlapping(spans)
        
        # Should have multiple non-overlapping segments
        assert len(merged) >= 2
        
        # First segment should have confidence 0.5
        assert merged[0].confidence == 0.5
        
        # Overlapping region should have max confidence
        overlap_spans = [s for s in merged if s.start >= 5 and s.end <= 10]
        if overlap_spans:
            assert overlap_spans[0].confidence == 0.8

    def test_build_heatmap_array(self):
        calc = HeatIntensityCalculator()
        spans = [
            TokenSpan(0, 5, 0.5, MatchType.TOKEN),
            TokenSpan(3, 8, 0.8, MatchType.AST),
        ]
        heatmap = calc.build_heatmap_array(spans, 10)
        
        assert len(heatmap) == 10
        # First 3 chars: only first span (0.5)
        assert heatmap[0] == 0.5
        assert heatmap[2] == 0.5
        # Chars 3-4: max(0.5, 0.8) = 0.8
        assert heatmap[3] == 0.8
        assert heatmap[4] == 0.8
        # Chars 5-7: only second span (0.8)
        assert heatmap[5] == 0.8
        assert heatmap[7] == 0.8
        # Chars 8-9: no span (0.0)
        assert heatmap[8] == 0.0

    def test_coverage_stats(self):
        calc = HeatIntensityCalculator()
        spans = [
            TokenSpan(0, 5, 0.5, MatchType.TOKEN),
        ]
        stats = calc.get_coverage_stats(spans, 10)
        
        assert stats["total_highlighted"] == 5
        assert stats["coverage_ratio"] == 0.5
        assert stats["avg_confidence"] == 0.5
        assert stats["max_confidence"] == 0.5


# ─────────────────────────────────────────────
# Tests: Token Heatmap Engine
# ─────────────────────────────────────────────

class TestTokenHeatmapEngine:
    """Tests for TokenHeatmapEngine class."""

    def test_build_heatmap_empty(self):
        engine = TokenHeatmapEngine()
        result = engine.build_heatmap("", "code", [])
        assert not result.has_results

    def test_build_heatmap_with_matches(self):
        engine = TokenHeatmapEngine(enable_ast_extraction=False)
        
        code_a = "def hello():\n    return 'world'\n"
        code_b = "def hello():\n    return 'world'\n"
        
        matches = [
            {
                "a_start": 1,
                "a_end": 2,
                "b_start": 1,
                "b_end": 2,
                "confidence": 0.9,
                "match_type": "ast",
            }
        ]
        
        result = engine.build_heatmap(code_a, code_b, matches)
        assert result.has_results
        assert result.overall_confidence > 0
        assert result.match_count > 0

    def test_build_heatmap_with_char_offsets(self):
        engine = TokenHeatmapEngine(enable_ast_extraction=False)
        
        code_a = "x = 5"
        code_b = "x = 5"
        
        matches = [
            {
                "a_start_offset": 0,
                "a_end_offset": 5,
                "b_start_offset": 0,
                "b_end_offset": 5,
                "confidence": 0.95,
                "match_type": "fused",
            }
        ]
        
        result = engine.build_heatmap(code_a, code_b, matches)
        assert result.has_results
        assert len(result.spans_a) > 0
        assert len(result.spans_b) > 0
        
        # Spans should cover the full code
        assert result.spans_a[0].start == 0
        assert result.spans_a[0].end == 5

    def test_build_heatmap_for_single(self):
        engine = TokenHeatmapEngine()
        
        code = "hello world"
        spans_data = [
            {"start": 0, "end": 5, "confidence": 0.8, "match_type": "token"},
        ]
        
        result = engine.build_heatmap_for_single(code, spans_data)
        assert len(result) > 0
        assert result[0].start == 0
        assert result[0].end == 5

    def test_line_to_offset(self):
        engine = TokenHeatmapEngine()
        code = "line1\nline2\nline3"
        
        assert engine._line_to_offset(code, 1) == 0
        assert engine._line_to_offset(code, 2) == 6
        assert engine._line_to_offset(code, 3) == 12

    def test_metadata_in_result(self):
        engine = TokenHeatmapEngine(enable_ast_extraction=False)
        
        code_a = "x = 5"
        code_b = "x = 5"
        
        matches = [
            {
                "a_start": 1,
                "a_end": 1,
                "b_start": 1,
                "b_end": 1,
                "confidence": 0.8,
                "match_type": "token",
            }
        ]
        
        result = engine.build_heatmap(code_a, code_b, matches)
        assert "code_length_a" in result.metadata
        assert "code_length_b" in result.metadata
        assert result.metadata["code_length_a"] == len(code_a)
        assert result.metadata["code_length_b"] == len(code_b)


# ─────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────

class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_full_pipeline_simple_code(self):
        """Test the complete flow from code to heatmap spans."""
        code_a = """def calculate_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
        code_b = """def calculate_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
        
        # Create matches
        matches = [
            {
                "a_start": 1,
                "a_end": 5,
                "b_start": 1,
                "b_end": 5,
                "confidence": 0.95,
                "match_type": "ast",
                "a_snippet": code_a,
                "b_snippet": code_b,
            }
        ]
        
        engine = TokenHeatmapEngine()
        result = engine.build_heatmap(code_a, code_b, matches)
        
        assert result.has_results
        assert result.overall_confidence > 0.7
        assert result.spans_a is not None
        assert result.spans_b is not None

    def test_token_span_serialization_roundtrip(self):
        """Test that TokenSpan can be serialized and deserialized."""
        original = TokenSpan(
            start=10,
            end=25,
            confidence=0.85,
            match_type=MatchType.FUSED,
            token_type="function_call",
            matched_value="foo(bar, baz)",
        )
        
        serialized = original.to_dict()
        restored = TokenSpan.from_dict(serialized)
        
        assert restored.start == original.start
        assert restored.end == original.end
        assert restored.confidence == original.confidence
        assert restored.match_type == original.match_type
        assert restored.token_type == original.token_type
        assert restored.matched_value == original.matched_value

    def test_heatmap_result_serialization(self):
        """Test HeatmapResult serialization roundtrip."""
        result = HeatmapResult(
            source_id="sub1",
            target_id="sub2",
            spans_a=[
                TokenSpan(0, 10, 0.8, MatchType.AST),
                TokenSpan(15, 25, 0.6, MatchType.TOKEN),
            ],
            spans_b=[
                TokenSpan(0, 10, 0.8, MatchType.AST),
            ],
            overall_confidence=0.75,
        )
        
        serialized = result.to_dict()
        restored = HeatmapResult.from_dict(serialized)
        
        assert restored.source_id == result.source_id
        assert restored.target_id == result.target_id
        assert len(restored.spans_a) == len(result.spans_a)
        assert len(restored.spans_b) == len(result.spans_b)
        assert restored.overall_confidence == result.overall_confidence