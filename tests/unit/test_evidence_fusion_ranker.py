"""Tests for evidence-first review ranking guardrails."""

from src.backend.engines.features.feature_extractor import FeatureVector
from src.backend.engines.scoring.evidence_ranker import EvidenceFusionRanker
from src.backend.engines.scoring.fusion_engine import FusionEngine


def test_same_rare_bug_strongly_boosts_review_priority() -> None:
    """Same wrong output should outrank ordinary similarity evidence."""
    rank = EvidenceFusionRanker().rank_pair(
        {
            "fingerprint": 0.25,
            "ast": 0.35,
            "runtime_bug_similarity": 0.9,
            "edge_case_behavior_similarity": 0.85,
        }
    )

    assert rank.review_priority >= 0.86
    assert rank.confidence == "High"
    assert "same wrong or edge-case behavior" in rank.professor_summary


def test_starter_code_and_common_solution_discount_risk() -> None:
    """Shared template and common solution regions should reduce priority."""
    rank = EvidenceFusionRanker().rank_pair(
        {
            "fingerprint": 0.95,
            "ast": 0.9,
            "starter_code_overlap": 0.9,
            "common_solution_score": 0.8,
        },
        base_score=0.92,
    )

    assert rank.review_priority < 0.5
    assert any("starter-code" in guardrail for guardrail in rank.guardrails)
    assert any("common solution" in guardrail for guardrail in rank.guardrails)


def test_embedding_only_signal_cannot_create_high_risk() -> None:
    """Embedding-only evidence is capped to medium/low review priority."""
    rank = EvidenceFusionRanker().rank_pair({"embedding": 0.98}, base_score=0.9)

    assert rank.review_priority <= 0.48
    assert rank.confidence == "Low"
    assert any("embedding-only" in guardrail for guardrail in rank.guardrails)


def test_fusion_engine_exposes_professor_review_priority() -> None:
    """Fusion output should carry queue-ranking metadata beyond final score."""
    result = FusionEngine(weights={"fingerprint": 1.0}).fuse(
        FeatureVector(fingerprint=0.95, ast=0.9, identifier_rename_score=0.7)
    )

    assert 0.0 <= result.final_score <= 1.0
    assert 0.0 <= result.review_priority <= 1.0
    assert result.professor_summary
    assert isinstance(result.evidence_reasons, list)
