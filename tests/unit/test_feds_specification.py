"""Unit tests for the Formal Evidence Decision Specification (FEDS) with Policy Engine."""

from __future__ import annotations

import pytest

from src.backend.engines.detection.feds_specification import (
    EXAMPLE_CASES,
    EvidenceModel,
    FEDS,
    FEDSDecision,
)
from src.backend.engines.detection.policy_engine import (
    PolicyEngine,
    PolicyRule,
    PolicyDecision,
)


class TestEvidenceModel:
    """Tests for the EvidenceModel class."""

    def test_get_models_returns_all_types(self) -> None:
        """Verify all evidence types are defined."""
        models = EvidenceModel.get_models()
        assert "identity" in models
        assert "structural" in models
        assert "lexical" in models
        assert "semantic" in models
        assert "behavioral" in models

    def test_semantic_has_capped_range(self) -> None:
        """Semantic evidence range is capped at 0.95."""
        models = EvidenceModel.get_models()
        assert models["semantic"].valid_range == (0.0, 0.95)

    def test_semantic_never_standalone(self) -> None:
        """Semantic evidence has constraint against standalone verdicts."""
        models = EvidenceModel.get_models()
        constraints = models["semantic"].reliability_constraints
        assert any("NEVER standalone" in c for c in constraints)


class TestPolicyEngine:
    """Tests for the PolicyEngine class."""

    @pytest.fixture
    def engine(self) -> PolicyEngine:
        """Create a PolicyEngine instance for testing."""
        return PolicyEngine()

    def test_load_policy(self, engine: PolicyEngine) -> None:
        """Policy loads successfully."""
        assert engine.config is not None
        assert str(engine.version) == "1.0"

    def test_rules_parsed(self, engine: PolicyEngine) -> None:
        """Rules are parsed and sorted by priority."""
        assert len(engine.rules) > 0
        priorities = [r.priority for r in engine.rules]
        assert priorities == sorted(priorities)

    def test_identical_files_returns_true(self, engine: PolicyEngine) -> None:
        """Identical files (exact_match=true) produce TRUE verdict."""
        evidence = {"layer1": {"has_exact_file_match": True}}
        decision = engine.evaluate(1.0, 0.95, 0.90, evidence)
        assert decision.verdict == "TRUE"
        assert "identity_override" in decision.decision_path

    def test_structural_dominance_returns_true(self, engine: PolicyEngine) -> None:
        """Strong structural evidence produces TRUE."""
        evidence = {"layer2": {"engine_scores": {"logic_flow": 0.96}}}
        decision = engine.evaluate(0.40, 0.96, 0.20, evidence)
        assert decision.verdict == "TRUE"
        assert "structural_dominance" in decision.decision_path

    def test_fallback_returns_clean(self, engine: PolicyEngine) -> None:
        """No evidence produces CLEAN verdict."""
        evidence = {}
        decision = engine.evaluate(0.10, 0.15, 0.20, evidence)
        assert decision.verdict == "CLEAN"

    def test_audit_record_generated(self, engine: PolicyEngine) -> None:
        """Audit record is generated for each decision."""
        evidence = {"layer1": {"has_exact_file_match": True}}
        decision = engine.evaluate(1.0, 0.95, 0.90, evidence)
        audit = engine.get_audit_record(decision, {"user": "test"})

        assert "policy_version" in audit
        assert "verdict" in audit
        assert "decision_path" in audit
        assert "evidence_snapshot" in audit


class TestFEDS:
    """Tests for the FEDS class using PolicyEngine."""

    @pytest.fixture
    def feds(self) -> FEDS:
        """Create a FEDS instance for testing."""
        return FEDS()

    def test_identical_files_returns_true(self, feds: FEDS) -> None:
        """Identical files produce TRUE verdict."""
        evidence = {"layer1": {"has_exact_file_match": True, "engine_scores": {}}}
        decision = feds.evaluate(1.0, 0.95, 0.90, evidence)
        assert decision.verdict == "TRUE"
        assert "identity_override" in decision.decision_path

    def test_high_confidence_combined_returns_true(self, feds: FEDS) -> None:
        """High confidence combined (L1 ≥ 0.85 AND L2 ≥ 0.85) produces TRUE."""
        evidence = {
            "layer1": {"engine_scores": {"ast": 0.88}},
            "layer2": {"engine_scores": {"logic_flow": 0.90}},
        }
        decision = feds.evaluate(0.88, 0.90, 0.50, evidence)
        assert decision.verdict == "TRUE"

    def test_probable_returns_probable(self, feds: FEDS) -> None:
        """Mixed evidence produces PROBABLE."""
        evidence = {
            "layer1": {"engine_scores": {"ngram": 0.85}},
            "layer3": {"engine_scores": {"embedding": 0.80}},
        }
        decision = feds.evaluate(0.40, 0.60, 0.85, evidence)
        assert decision.verdict == "PROBABLE"

    def test_semantic_flag_returns_flag(self, feds: FEDS) -> None:
        """Semantic-only similarity produces FLAG."""
        evidence = {
            "layer3": {"engine_scores": {"embedding": 0.92}},
        }
        # L2 is low (0.20), so structural < 0.50
        decision = feds.evaluate(0.30, 0.20, 0.92, evidence)
        assert decision.verdict == "FLAG"

    def test_conflict_resolution_returns_review(self, feds: FEDS) -> None:
        """Contradictory evidence produces REVIEW."""
        evidence = {
            "layer1": {"engine_scores": {"ast": 0.88}},
            "layer3": {"engine_scores": {"embedding": 0.20}},
        }
        decision = feds.evaluate(0.88, 0.30, 0.20, evidence)
        assert decision.verdict == "REVIEW"

    def test_review_zone_returns_review(self, feds: FEDS) -> None:
        """Borderline signals produce REVIEW."""
        evidence = {}
        decision = feds.evaluate(0.55, 0.45, 0.35, evidence)
        assert decision.verdict == "REVIEW"

    def test_clean_returns_clean(self, feds: FEDS) -> None:
        """No evidence produces CLEAN."""
        evidence = {}
        decision = feds.evaluate(0.10, 0.15, 0.20, evidence)
        assert decision.verdict == "CLEAN"

    def test_confidence_calibration(self, feds: FEDS) -> None:
        """Confidence is calibrated based on verdict."""
        # TRUE should have high confidence
        evidence_true = {"layer1": {"has_exact_file_match": True}}
        decision_true = feds.evaluate(1.0, 0.95, 0.90, evidence_true)
        assert decision_true.confidence > 0.9

        # CLEAN should have low confidence
        evidence_clean = {}
        decision_clean = feds.evaluate(0.10, 0.15, 0.20, evidence_clean)
        assert decision_clean.confidence < 0.5

    def test_audit_record_included(self, feds: FEDS) -> None:
        """Audit record is included in decision."""
        evidence = {"layer1": {"has_exact_file_match": True}}
        decision = feds.evaluate(1.0, 0.95, 0.90, evidence)
        assert "policy_version" in decision.audit_record
        assert decision.audit_record["verdict"] == "TRUE"


class TestPolicyRule:
    """Tests for the PolicyRule class."""

    def test_simple_condition_matches(self) -> None:
        """Simple condition matching works."""
        rule = PolicyRule(
            id="test",
            priority=1,
            condition={"ast": ">= 0.85"},
            verdict="TRUE",
            confidence=0.95,
            reason="Test",
        )
        assert rule.matches({"ast": 0.90}) is True
        assert rule.matches({"ast": 0.80}) is False

    def test_and_condition(self) -> None:
        """AND condition works."""
        rule = PolicyRule(
            id="test",
            priority=1,
            condition={"and": [{"ast": ">= 0.80"}, {"ngram": ">= 0.70"}]},
            verdict="TRUE",
            confidence=0.95,
            reason="Test",
        )
        assert rule.matches({"ast": 0.90, "ngram": 0.80}) is True
        assert rule.matches({"ast": 0.90, "ngram": 0.60}) is False

    def test_or_condition(self) -> None:
        """OR condition works."""
        rule = PolicyRule(
            id="test",
            priority=1,
            condition={"or": [{"ast": ">= 0.90"}, {"ngram": ">= 0.90"}]},
            verdict="TRUE",
            confidence=0.95,
            reason="Test",
        )
        assert rule.matches({"ast": 0.95, "ngram": 0.50}) is True
        assert rule.matches({"ast": 0.50, "ngram": 0.50}) is False


class TestAntiPatterns:
    """Tests for anti-pattern rules."""

    def test_semantic_never_standalone_verdict(self) -> None:
        """Semantic evidence alone cannot trigger TRUE verdict."""
        engine = PolicyEngine()

        # High embedding, no structural evidence (graph_similarity = 0.20)
        evidence = {
            "layer2": {"engine_scores": {"graph": 0.20}},
            "layer3": {"engine_scores": {"embedding": 0.95}},
        }
        decision = engine.evaluate(0.20, 0.20, 0.95, evidence)
        assert decision.verdict != "TRUE"
        # Should be FLAG (semantic-only warning)
        assert decision.verdict == "FLAG"

    def test_no_weighted_averaging(self) -> None:
        """Decision is rule-based, not weighted average."""
        engine = PolicyEngine()

        # L1=0.40, L2=0.40, L3=0.40 should be CLEAN (below thresholds)
        evidence = {}
        decision = engine.evaluate(0.40, 0.40, 0.40, evidence)
        assert decision.verdict == "CLEAN"

    def test_evidence_conflict_detected(self) -> None:
        """Contradictory evidence patterns are detected."""
        engine = PolicyEngine()

        # High L1 but low L2/L3
        evidence = {
            "layer1": {"engine_scores": {"ast": 0.88}},
            "layer3": {"engine_scores": {"embedding": 0.20}},
        }
        decision = engine.evaluate(0.88, 0.20, 0.20, evidence)
        assert (
            "conflict_resolution" in decision.decision_path
            or decision.verdict == "REVIEW"
        )


class TestExampleCases:
    """Tests using the documented example cases."""

    @pytest.fixture
    def feds(self) -> FEDS:
        return FEDS()

    @pytest.mark.parametrize("case", EXAMPLE_CASES)
    def test_example_case(self, feds: FEDS, case: dict) -> None:
        """Test each documented example case."""
        l1 = case["input"]["l1"]
        l2 = case["input"]["l2"]
        l3 = case["input"]["l3"]

        # Build evidence based on case name
        if case["name"] == "Identical Files":
            evidence = {"layer1": {"has_exact_file_match": True}}
        elif case["name"] == "Heavily Plagiarized":
            evidence = {
                "layer1": {"engine_scores": {"ast": 0.88}},
                "layer2": {"engine_scores": {"logic_flow": 0.90}},
            }
        elif case["name"] == "Semantic-Only Similarity":
            evidence = {
                "layer3": {"engine_scores": {"embedding": 0.92}},
            }
        elif case["name"] == "Borderline Case":
            evidence = {}
        else:
            evidence = {}

        decision = feds.evaluate(l1, l2, l3, evidence)
        assert (
            decision.verdict == case["expected_verdict"]
        ), f"Failed for case: {case['name']}"
