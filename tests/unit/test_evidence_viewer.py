"""Unit tests for evidence_viewer module."""

import pytest

from src.backend.evaluation.evidence_viewer import (
    EvidenceViewer,
    EvidenceView,
    MatchedElement,
    DiffHunk,
    generate_evidence_view,
)


class TestMatchedElement:
    """Tests for MatchedElement dataclass."""

    def test_create_matched_element(self) -> None:
        """Test creating a matched element."""
        element = MatchedElement(
            element_type="function",
            element_name="calculate_sum",
            start_line_a=1,
            end_line_a=10,
            start_line_b=1,
            end_line_b=12,
            similarity=0.85,
        )
        assert element.element_name == "calculate_sum"
        assert element.similarity == 0.85

    def test_matched_element_with_confidence(self) -> None:
        """Test matched element with confidence."""
        element = MatchedElement(
            element_type="class",
            element_name="MyClass",
            start_line_a=1,
            end_line_a=20,
            start_line_b=1,
            end_line_b=20,
            similarity=0.90,
            confidence=0.95,
            details=["Class structure match"],
        )
        assert element.confidence == 0.95
        assert len(element.details) == 1


class TestDiffHunk:
    """Tests for DiffHunk dataclass."""

    def test_create_diff_hunk(self) -> None:
        """Test creating a diff hunk."""
        hunk = DiffHunk(
            hunk_type="added",
            line_number=5,
            content="def new_function():",
        )
        assert hunk.hunk_type == "added"
        assert hunk.line_number == 5


class TestEvidenceViewer:
    """Tests for EvidenceViewer class."""

    def test_generate_view_basic(self) -> None:
        """Test generating a basic evidence view."""
        viewer = EvidenceViewer()
        result = viewer.generate_view(
            code_a="def foo():\n    return 1",
            code_b="def bar():\n    return 2",
            submission_a_id="sub_a",
            submission_b_id="sub_b",
            similarity_score=0.85,
        )

        assert result.submission_a_id == "sub_a"
        assert result.similarity_score == 0.85
        assert result.verdict == "HIGH_RISK"

    def test_determine_verdict_high_risk(self) -> None:
        """Test verdict determination for high risk."""
        viewer = EvidenceViewer()
        assert viewer._determine_verdict(0.90) == "HIGH_RISK"
        assert viewer._determine_verdict(0.85) == "HIGH_RISK"

    def test_determine_verdict_medium_risk(self) -> None:
        """Test verdict determination for medium risk."""
        viewer = EvidenceViewer()
        assert viewer._determine_verdict(0.70) == "MEDIUM_RISK"
        assert viewer._determine_verdict(0.75) == "MEDIUM_RISK"
        assert viewer._determine_verdict(0.84) == "MEDIUM_RISK"

    def test_determine_verdict_low_risk(self) -> None:
        """Test verdict determination for low risk."""
        viewer = EvidenceViewer()
        assert viewer._determine_verdict(0.50) == "LOW_RISK"
        assert viewer._determine_verdict(0.40) == "INCONCLUSIVE"  # Below threshold

    def test_determine_verdict_inconclusive(self) -> None:
        """Test verdict determination for inconclusive."""
        viewer = EvidenceViewer()
        assert viewer._determine_verdict(0.30) == "INCONCLUSIVE"

    def test_generate_diff(self) -> None:
        """Test diff generation."""
        viewer = EvidenceViewer()
        code_a = "def foo():\n    return 1\n"
        code_b = "def bar():\n    return 2\n"

        hunks = viewer._generate_diff(code_a, code_b)
        assert len(hunks) > 0

    def test_generate_diff_identical(self) -> None:
        """Test diff for identical code."""
        viewer = EvidenceViewer()
        code = "def foo():\n    return 1\n"

        hunks = viewer._generate_diff(code, code)
        assert all(h.hunk_type == "context" for h in hunks)

    def test_calculate_confidence_with_details(self) -> None:
        """Test confidence calculation with engine details."""
        viewer = EvidenceViewer()
        engine_details = {"MOSS": 0.80, "JPlag": 0.85}
        confidence = viewer._calculate_confidence(0.80, engine_details)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_no_details(self) -> None:
        """Test confidence calculation without engine details."""
        viewer = EvidenceViewer()
        confidence = viewer._calculate_confidence(0.80, None)
        assert confidence == 0.5

    def test_generate_analysis_notes(self) -> None:
        """Test analysis notes generation."""
        viewer = EvidenceViewer()
        notes = viewer._generate_analysis_notes(0.90, [], None)
        assert len(notes) > 0
        assert any("High similarity" in n for n in notes)

    def test_generate_recommendations_high_risk(self) -> None:
        """Test recommendations for high risk."""
        viewer = EvidenceViewer()
        recs = viewer._generate_recommendations("HIGH_RISK", [])
        assert any("Flag" in r for r in recs)

    def test_generate_recommendations_low_risk(self) -> None:
        """Test recommendations for low risk."""
        viewer = EvidenceViewer()
        recs = viewer._generate_recommendations("LOW_RISK", [])
        assert any("No immediate action" in r for r in recs)


class TestGenerateEvidenceView:
    """Tests for generate_evidence_view convenience function."""

    def test_generate_evidence_view_dict(self) -> None:
        """Test generating evidence view as dict."""
        result = generate_evidence_view(
            code_a="def foo():\n    return 1",
            code_b="def bar():\n    return 2",
            submission_a_id="sub_a",
            submission_b_id="sub_b",
            similarity_score=0.75,
        )

        assert isinstance(result, dict)
        assert result["submission_a_id"] == "sub_a"
        assert result["similarity_score"] == 0.75

    def test_generate_evidence_view_with_engine_details(self) -> None:
        """Test generating evidence view with engine details."""
        result = generate_evidence_view(
            code_a="def foo(): return 1",
            code_b="def bar(): return 2",
            submission_a_id="a",
            submission_b_id="b",
            similarity_score=0.80,
            engine_details={"MOSS": 0.78, "JPlag": 0.82},
        )

        assert result["confidence"] > 0.5


class TestEvidenceView:
    """Tests for EvidenceView dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        view = EvidenceView(
            submission_a_id="sub_a",
            submission_b_id="sub_b",
            similarity_score=0.85,
            verdict="HIGH_RISK",
            confidence=0.9,
            matched_elements=[],
            diff_hunks=[],
            analysis_notes=["Test note"],
            recommendations=["Test recommendation"],
        )

        d = view.to_dict()
        assert d["submission_a_id"] == "sub_a"
        assert d["similarity_score"] == 0.85
        assert d["verdict"] == "HIGH_RISK"
        assert d["analysis_notes"] == ["Test note"]


class TestEvidenceViewerEdgeCases:
    """Tests for edge cases in EvidenceViewer."""

    def test_find_matched_elements(self) -> None:
        """Test finding matched elements."""
        viewer = EvidenceViewer()
        code_a = "def my_function():\n    pass\n"
        code_b = "def my_function():\n    return 1\n"

        elements = viewer._find_matched_elements(code_a, code_b)
        # Should find the function name match
        assert isinstance(elements, list)

    def test_find_matched_elements_no_matches(self) -> None:
        """Test with no matches."""
        viewer = EvidenceViewer()
        code_a = "def foo():\n    pass\n"
        code_b = "def bar():\n    pass\n"

        elements = viewer._find_matched_elements(code_a, code_b)
        assert isinstance(elements, list)

    def test_generate_analysis_notes_with_matches(self) -> None:
        """Test analysis notes with matched elements."""
        viewer = EvidenceViewer()
        elements = [
            MatchedElement(
                element_type="function",
                element_name="test",
                start_line_a=1,
                end_line_a=1,
                start_line_b=1,
                end_line_b=1,
                similarity=0.9,
            )
        ]
        notes = viewer._generate_analysis_notes(0.90, elements, None)
        assert any("matched" in n.lower() for n in notes)

    def test_generate_analysis_notes_with_engine_details(self) -> None:
        """Test analysis notes with engine details."""
        viewer = EvidenceViewer()
        notes = viewer._generate_analysis_notes(0.80, [], {"MOSS": 0.78})
        assert any("engine" in n.lower() for n in notes)

    def test_generate_recommendations_inconclusive(self) -> None:
        """Test recommendations for inconclusive verdict."""
        viewer = EvidenceViewer()
        recs = viewer._generate_recommendations("INCONCLUSIVE", [])
        assert any("further" in r.lower() for r in recs)

    def test_generate_recommendations_with_matches(self) -> None:
        """Test recommendations with matched elements."""
        viewer = EvidenceViewer()
        elements = [
            MatchedElement(
                element_type="function",
                element_name="test",
                start_line_a=1,
                end_line_a=1,
                start_line_b=1,
                end_line_b=1,
                similarity=0.9,
            )
        ]
        recs = viewer._generate_recommendations("HIGH_RISK", elements)
        assert isinstance(recs, list)

    def test_generate_view_with_engine_details(self) -> None:
        """Test view generation with engine details."""
        viewer = EvidenceViewer()
        result = viewer.generate_view(
            code_a="def foo(): return 1",
            code_b="def bar(): return 2",
            submission_a_id="a",
            submission_b_id="b",
            similarity_score=0.80,
            engine_details={"MOSS": 0.78, "JPlag": 0.82},
        )
        assert result.confidence > 0.5

    def test_generate_view_exact_match(self) -> None:
        """Test view generation with identical code."""
        viewer = EvidenceViewer()
        code = "def foo():\n    return 1\n"
        result = viewer.generate_view(
            code_a=code,
            code_b=code,
            submission_a_id="a",
            submission_b_id="b",
            similarity_score=1.0,
        )
        assert result.verdict == "HIGH_RISK"
        assert result.similarity_score == 1.0
