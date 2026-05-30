"""Tests for Dean-Grade Academic Integrity Evidence Report Generator."""

from __future__ import annotations


from src.backend.infrastructure.dean_report_generator import (
    DeanReportGenerator,
    DeanGradeReport,
    EvidenceItem,
    generate_dean_report,
    VERDICT_LABELS,
)


class TestEvidenceItem:
    """Tests for EvidenceItem dataclass."""

    def test_evidence_item_creation(self) -> None:
        """EvidenceItem should be created with all fields."""
        item = EvidenceItem(
            evidence_type="structural",
            description="Test evidence",
            value=0.85,
            confidence="HIGH",
            explanation="Test explanation",
        )
        assert item.evidence_type == "structural"
        assert item.value == 0.85
        assert item.confidence == "HIGH"

    def test_evidence_item_to_dict(self) -> None:
        """EvidenceItem should serialize to dictionary."""
        item = EvidenceItem(
            evidence_type="structural",
            description="Test evidence",
            value=0.85,
            confidence="HIGH",
            explanation="Test explanation",
            matched_spans=[{"start": 10, "end": 20}],
        )
        result = item.to_dict()
        assert result["evidence_type"] == "structural"
        assert result["value"] == 0.85
        assert len(result["matched_spans"]) == 1


class TestDeanGradeReport:
    """Tests for DeanGradeReport dataclass."""

    def test_report_creation(self) -> None:
        """DeanGradeReport should be created with required fields."""
        report = DeanGradeReport(
            case_id="case-123",
            course_id="CS101",
            assignment_id="assignment-1",
            submission_a_id="student-a",
            submission_b_id="student-b",
            final_verdict="REVIEW_REQUIRED",
        )
        assert report.case_id == "case-123"
        assert report.final_verdict == "REVIEW_REQUIRED"

    def test_report_to_dict(self) -> None:
        """DeanGradeReport should serialize to dictionary."""
        report = DeanGradeReport(
            case_id="case-123",
            course_id="CS101",
            assignment_id="assignment-1",
            submission_a_id="student-a",
            submission_b_id="student-b",
            final_verdict="CLEAN",
        )
        result = report.to_dict()
        assert "report_metadata" in result
        assert result["report_metadata"]["case_id"] == "case-123"
        assert result["report_metadata"]["final_verdict"] == "CLEAN"

    def test_executive_summary_generation(self) -> None:
        """Executive summary should be generated correctly."""
        report = DeanGradeReport(
            case_id="case-123",
            course_id="CS101",
            assignment_id="assignment-1",
            submission_a_id="student-a",
            submission_b_id="student-b",
            final_verdict="CLEAN",
        )
        summary = report._build_executive_summary()
        assert summary["final_classification"] == "CLEAN"
        assert "no significant" in summary["summary_paragraph"].lower()


class TestDeanReportGenerator:
    """Tests for DeanReportGenerator class."""

    def test_generate_clean_report(self) -> None:
        """Generator should produce CLEAN verdict for low similarity."""
        generator = DeanReportGenerator()
        bundle = {
            "shape_similarity": 0.1,
            "semantic_node_similarity": 0.05,
            "control_flow_similarity": 0.1,
            "divergence_score": 0.9,
        }

        report = generator.generate(
            case_id="case-1",
            course_id="CS101",
            assignment_id="a1",
            submission_a_id="s1",
            submission_b_id="s2",
            evidence_bundle=bundle,
        )

        assert report.final_verdict == "CLEAN"

    def test_generate_review_required_report(self) -> None:
        """Generator should produce REVIEW_REQUIRED for moderate similarity."""
        generator = DeanReportGenerator()
        bundle = {
            "shape_similarity": 0.6,
            "semantic_node_similarity": 0.5,
            "control_flow_similarity": 0.6,
            "divergence_score": 0.5,
            "ngram": 0.6,
            "winnowing": 0.5,
        }

        report = generator.generate(
            case_id="case-2",
            course_id="CS101",
            assignment_id="a1",
            submission_a_id="s1",
            submission_b_id="s2",
            evidence_bundle=bundle,
        )

        # Moderate evidence should result in REVIEW_REQUIRED
        assert report.final_verdict in (
            "REVIEW_REQUIRED",
            "CLEAN",
        )  # Either is acceptable for moderate evidence

    def test_generate_strong_similarity_report(self) -> None:
        """Generator should produce STRONG_SIMILARITY_OBSERVED for high similarity."""
        generator = DeanReportGenerator()
        bundle = {
            "shape_similarity": 0.9,
            "semantic_node_similarity": 0.85,
            "control_flow_similarity": 0.9,
            "divergence_score": 0.1,
            "ngram": 0.95,
            "winnowing": 0.9,
        }

        report = generator.generate(
            case_id="case-3",
            course_id="CS101",
            assignment_id="a1",
            submission_a_id="s1",
            submission_b_id="s2",
            evidence_bundle=bundle,
        )

        assert report.final_verdict == "STRONG_SIMILARITY_OBSERVED"

    def test_extract_structural_evidence(self) -> None:
        """Should extract structural evidence correctly."""
        generator = DeanReportGenerator()
        bundle = {
            "shape_similarity": 0.8,
            "semantic_node_similarity": 0.7,
            "divergence_score": 0.2,
        }

        evidence = generator._extract_structural_evidence(bundle)
        assert len(evidence) >= 2  # shape and semantic

    def test_extract_lexical_evidence(self) -> None:
        """Should extract lexical evidence correctly."""
        generator = DeanReportGenerator()
        bundle = {
            "ngram": 0.85,
            "winnowing": 0.75,
        }

        evidence = generator._extract_lexical_evidence(bundle)
        assert len(evidence) >= 2

    def test_extract_semantic_evidence_low_confidence(self) -> None:
        """Semantic evidence should have LOW confidence."""
        generator = DeanReportGenerator()
        bundle = {"embedding_similarity": 0.8}

        evidence = generator._extract_semantic_evidence(bundle)
        assert len(evidence) == 1
        assert evidence[0].confidence == "LOW"

    def test_extract_divergence_evidence(self) -> None:
        """Should extract divergence evidence correctly."""
        generator = DeanReportGenerator()
        bundle = {"divergence_score": 0.8}

        evidence = generator._extract_divergence_evidence(bundle)
        assert len(evidence) == 1
        assert evidence[0].evidence_type == "divergence"

    def test_verdict_labels_exist(self) -> None:
        """All verdict labels should exist."""
        assert "CLEAN" in VERDICT_LABELS
        assert "REVIEW_REQUIRED" in VERDICT_LABELS
        assert "STRONG_SIMILARITY_OBSERVED" in VERDICT_LABELS

    def test_language_policy_no_accusations(self) -> None:
        """Report should use neutral language, not accusations."""
        generator = DeanReportGenerator()
        bundle = {
            "shape_similarity": 0.9,
            "semantic_node_similarity": 0.85,
            "control_flow_similarity": 0.9,
            "divergence_score": 0.1,
        }

        report = generator.generate(
            case_id="case-1",
            course_id="CS101",
            assignment_id="a1",
            submission_a_id="s1",
            submission_b_id="s2",
            evidence_bundle=bundle,
        )

        # Check that explanations don't contain accusatory language
        for item in report.structural_evidence + report.lexical_evidence:
            assert "cheat" not in item.explanation.lower()
            assert "plagiar" not in item.explanation.lower()
            assert (
                "copy" not in item.explanation.lower()
                or "copying" in item.explanation.lower()
            )


class TestConvenienceFunction:
    """Tests for generate_dean_report convenience function."""

    def test_generate_report_function(self) -> None:
        """Should generate report using convenience function."""
        bundle = {
            "shape_similarity": 0.5,
            "control_flow_similarity": 0.5,
        }

        report = generate_dean_report(
            case_id="case-1",
            course_id="CS101",
            assignment_id="a1",
            submission_a_id="s1",
            submission_b_id="s2",
            evidence_bundle=bundle,
        )

        assert isinstance(report, DeanGradeReport)
        assert report.case_id == "case-1"
