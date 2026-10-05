"""Evidence Hierarchy Engine (EHE) - core decision module.

Hierarchical evidence, NOT score fusion:
1. Identity evidence overrides everything (hard stop)
2. Structural evidence dominates semantic evidence
3. Lower layers cannot overturn higher layers
4. The decision is rule-based, not a weighted average

Layers: 0 Identity, 1 Structural, 2 Statistical, 3 Semantic, 4 Explainable (trace).

What changed from the first version (all of it behaviour you can configure through
:class:`EHEThresholds`):
- Semantic similarity can no longer produce PROBABLE on its own. "Semantic dominance" now needs
  structural support, as the policy documents say; semantic-only evidence is a FLAG.
- The 0.95 "very strong signal" branch bypassed the baseline correction, so a raw UniXcoder 0.95
  (unrelated files sit at ~0.70) scored 0.95 instead of ~0.83. Correction is now uniform.
- The statistical layer no longer treats STYLE similarity as evidence of copying (it made any two
  similarly formatted files "statistical >= 0.70" and so PROBABLE); style stays in the trace.
- The 0.75 structural tier needs ``min_agreeing_engines`` structural engines (default 2); one
  engine alone yields PROBABLE. Set it to 1 for the old behaviour.
- The borderline REVIEW tier looks at BASELINE-CORRECTED structural scores (raw n-gram/winnowing
  scores of any two solutions to the same task are well above zero).
- A missing engine score is "unavailable", not 0.0, so a missing embedding cannot create an
  "evidence conflict".
- All layers are always computed (the early return for hard matches skipped them), and the
  decision carries the full evidence either way.
- The identity layer is driven by the caller (``identity_match``); ``DetectionPolicy`` used to
  pass empty strings, so identical files were never recognised as identical.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, fields, replace
from enum import Enum
from typing import Any

from ._text import first_score, normalize_text, score

logger = logging.getLogger(__name__)


class Verdict(str, Enum):
    """Final decision verdicts (the single Verdict enum used across the package).

    TRUE      definite plagiarism - actionable evidence chain
    PROBABLE  likely plagiarism - needs manual review
    REVIEW    borderline - human inspection required
    FLAG      semantic-only signal - review required, high false-positive risk
    CLEAN     no evidence of plagiarism
    """

    TRUE = "TRUE"
    PROBABLE = "PROBABLE"
    REVIEW = "REVIEW"
    FLAG = "FLAG"
    CLEAN = "CLEAN"


@dataclass
class EHEThresholds:
    """Every threshold the engine actually uses (and nothing else), with its meaning."""

    # structural layer: max over ast / logic_flow / ngram / winnowing (raw scores)
    structural_hard_match: float = 0.90  # single engine at/above this -> TRUE
    structural_strong: float = 0.75  # at/above this -> TRUE if enough engines agree, else PROBABLE
    structural_agree_min: float = 0.60  # an engine "agrees" at/above this
    min_agreeing_engines: int = 2
    structural_medium: float = 0.50  # structural + statistical support -> PROBABLE
    statistical_strong: float = 0.70  # graph similarity that supports a medium structural match
    # semantic layer (baseline-corrected)
    semantic_dominance: float = 0.95  # with structural support -> PROBABLE
    semantic_flag: float = 0.85  # semantic-only -> FLAG
    semantic_baseline: float = 0.70  # UniXcoder similarity of two unrelated files in one language
    semantic_cap: float = 0.99
    # conflict and borderline tiers
    conflict_gap: float = 0.50  # |structural - semantic| above this -> REVIEW
    borderline: float = 0.30  # baseline-corrected structural/statistical -> REVIEW
    review_enabled: bool = True
    # noise floor of unrelated files in the same language, per engine
    baselines: dict[str, float] = field(
        default_factory=lambda: {"ast": 0.25, "logic_flow": 0.20, "ngram": 0.10, "winnowing": 0.16, "graph": 0.20}
    )
    # confidences reported with each rule
    confidence_identity: float = 0.99
    confidence_hard: float = 0.95
    confidence_strong: float = 0.90
    confidence_probable: float = 0.75
    confidence_semantic_support: float = 0.85
    confidence_flag: float = 0.60
    confidence_conflict: float = 0.50
    confidence_borderline: float = 0.40
    confidence_clean: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validated(self) -> EHEThresholds:
        """Copy with every value range-checked (raises ValueError)."""
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "baselines":
                if not isinstance(value, dict) or any(score(v, -1) < 0 or score(v, -1) >= 1 for v in value.values()):
                    raise ValueError("baselines must map engine names to values in [0, 1)")
            elif f.name == "min_agreeing_engines":
                if int(value) < 1:
                    raise ValueError("min_agreeing_engines must be at least 1")
            elif f.name == "review_enabled":
                continue
            elif not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{f.name} must be a number in [0, 1], got {value!r}")
        if self.structural_agree_min > self.structural_strong:
            raise ValueError("structural_agree_min must not exceed structural_strong")
        if self.semantic_baseline >= 1.0:
            raise ValueError("semantic_baseline must be below 1")
        return replace(self, baselines=dict(self.baselines))


@dataclass
class LayerResult:
    """Result from a single evidence layer."""

    score: float = 0.0
    signals: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    triggered: bool = False
    available: bool = True  # False when the layer had no usable input


@dataclass
class EHEDecision:
    """Final decision from the Evidence Hierarchy Engine."""

    verdict: Verdict
    confidence: float
    triggered_layer: str
    evidence: dict[str, Any] = field(default_factory=dict)
    decision_path: list[str] = field(default_factory=list)
    raw_scores: dict[str, float] = field(default_factory=dict)
    rule: str = ""  # id of the rule that fired


def _correct(raw: float | None, baseline: float) -> float | None:
    """Baseline-corrected score in [0, 1]; None stays None (unavailable)."""
    if raw is None:
        return None
    return max(0.0, raw - baseline) / max(0.01, 1.0 - baseline)


class IdentityLayer:
    """Layer 0: identity detection (hard override)."""

    @staticmethod
    def evaluate(code_a: str, code_b: str) -> LayerResult:
        """Identical after line-ending / trailing-whitespace normalisation."""
        a, b = normalize_text(code_a), normalize_text(code_b)
        if not a or not b:
            return LayerResult(available=False)
        if a == b:
            raw_equal = code_a == code_b
            return LayerResult(
                score=1.0, triggered=True, evidence={"match_type": "exact" if raw_equal else "whitespace_only"}
            )
        return LayerResult()


class StructuralLayer:
    """Layer 1: structural evidence (AST, control flow, n-grams, winnowing); max principle."""

    def __init__(self, thresholds: EHEThresholds | None = None) -> None:
        self.t = thresholds or EHEThresholds()

    def evaluate(
        self,
        ast_score: float | None,
        flow_score: float | None,
        ngram_score: float | None,
        winnowing_score: float | None,
    ) -> LayerResult:
        raw = {"ast": ast_score, "logic_flow": flow_score, "ngram": ngram_score, "winnowing": winnowing_score}
        present = {k: v for k, v in raw.items() if v is not None}
        if not present:
            return LayerResult(available=False)
        corrected = {k: _correct(v, self.t.baselines.get(k, 0.0)) for k, v in present.items()}
        best = max(present.values())
        return LayerResult(
            score=best,
            signals={**{k: v for k, v in present.items()}, **{f"{k}_corrected": round(v, 4) for k, v in corrected.items()}},
            evidence={
                "agreeing_engines": sorted(k for k, v in present.items() if v >= self.t.structural_agree_min),
                "corrected_max": max(corrected.values()),
            },
            triggered=best > 0.0,
        )


class StatisticalLayer:
    """Layer 2: statistical evidence. Graph similarity decides; style is informational only."""

    def __init__(self, thresholds: EHEThresholds | None = None) -> None:
        self.t = thresholds or EHEThresholds()

    def evaluate(self, graph_score: float | None, stylometry_score: float | None = None) -> LayerResult:
        signals: dict[str, float] = {}
        if graph_score is not None:
            signals["graph"] = graph_score
        if stylometry_score is not None:
            signals["stylometry_informational"] = stylometry_score  # never part of the decision
        if graph_score is None:
            return LayerResult(signals=signals, available=False)
        corrected = _correct(graph_score, self.t.baselines.get("graph", 0.0))
        signals["graph_corrected"] = round(corrected, 4)
        return LayerResult(score=graph_score, signals=signals, evidence={"corrected": corrected}, triggered=graph_score > 0.0)


class SemanticLayer:
    """Layer 3: semantic evidence (embedding), baseline-corrected and capped; weak signal."""

    def __init__(self, thresholds: EHEThresholds | None = None) -> None:
        self.t = thresholds or EHEThresholds()

    def evaluate(self, embedding_score: float | None) -> LayerResult:
        if embedding_score is None:
            return LayerResult(available=False)
        corrected = min(_correct(embedding_score, self.t.semantic_baseline), self.t.semantic_cap)
        return LayerResult(
            score=corrected,
            signals={"embedding": embedding_score, "embedding_corrected": corrected},
            triggered=corrected > 0.0,
        )


class EvidenceHierarchyEngine:
    """Main decision orchestrator with strict priority ordering."""

    def __init__(self, thresholds: EHEThresholds | None = None) -> None:
        self.thresholds = (thresholds or EHEThresholds()).validated()
        self.identity = IdentityLayer()
        self.structural = StructuralLayer(self.thresholds)
        self.statistical = StatisticalLayer(self.thresholds)
        self.semantic = SemanticLayer(self.thresholds)

    def decide(
        self,
        code_a: str,
        code_b: str,
        engine_scores: dict[str, Any],
        identity_match: bool | None = None,
    ) -> EHEDecision:
        """Execute the hierarchical decision pipeline.

        Args:
            code_a, code_b: file contents (used for the identity check unless ``identity_match``
                is given; pass ``""`` when only scores are available).
            engine_scores: engine name -> score in [0, 1]. A missing/None score is "unavailable".
                Recognised: ast, logic_flow, ngram, winnowing, graph, stylometry, embedding.
            identity_match: caller-computed identity decision (e.g. ``Layer1Result.has_exact_file_match``);
                overrides the comparison of ``code_a`` and ``code_b``.
        """
        path: list[str] = []
        identity = self.identity.evaluate(code_a, code_b)
        if identity_match is not None:
            identity = LayerResult(score=1.0, triggered=True, evidence={"match_type": "caller"}) if identity_match else LayerResult()
        if identity.triggered:
            path.append("identity_override")
            return self._decision(
                Verdict.TRUE, self.thresholds.confidence_identity, "identity", "identity_override",
                {"identity": identity.evidence}, path, {"identity": 1.0},
            )

        s = engine_scores or {}
        structural = self.structural.evaluate(
            first_score(s, "ast"), first_score(s, "logic_flow"), first_score(s, "ngram"), first_score(s, "winnowing")
        )
        path.append("structural")
        statistical = self.statistical.evaluate(first_score(s, "graph"), first_score(s, "stylometry"))
        path.append("statistical")
        semantic = self.semantic.evaluate(first_score(s, "embedding"))
        path.append("semantic")
        return self._apply_decision_rules(structural, statistical, semantic, path)

    # ------------------------------------------------------------------ rules

    def _decision(
        self,
        verdict: Verdict,
        confidence: float,
        layer: str,
        rule: str,
        evidence: dict[str, Any],
        path: list[str],
        raw: dict[str, float],
    ) -> EHEDecision:
        return EHEDecision(
            verdict=verdict,
            confidence=confidence,
            triggered_layer=layer,
            evidence=evidence,
            decision_path=path + ([rule] if rule not in path else []),
            raw_scores=raw,
            rule=rule,
        )

    def _apply_decision_rules(
        self, structural: LayerResult, statistical: LayerResult, semantic: LayerResult, path: list[str]
    ) -> EHEDecision:
        t = self.thresholds
        evidence = {"structural": structural.signals, "statistical": statistical.signals, "semantic": semantic.signals}
        raw = {"structural": structural.score, "statistical": statistical.score, "semantic": semantic.score}
        agreeing = structural.evidence.get("agreeing_engines", [])
        corrected_structural = structural.evidence.get("corrected_max", 0.0)
        s_score, g_score, e_score = structural.score, statistical.score, semantic.score

        def out(verdict: Verdict, confidence: float, layer: str, rule: str) -> EHEDecision:
            return self._decision(verdict, confidence, layer, rule, evidence, path, raw)

        # Rule 1: hard structural match (a single strong engine is enough; this is the old 0.90 rule)
        if structural.available and s_score >= t.structural_hard_match:
            return out(Verdict.TRUE, t.confidence_hard, "structural", "strong_structural")

        # Rule 2: strong structural match, corroborated by another structural engine
        if structural.available and s_score >= t.structural_strong:
            if len(agreeing) >= t.min_agreeing_engines:
                return out(Verdict.TRUE, t.confidence_strong, "structural", "strong_structural_corroborated")
            return out(Verdict.PROBABLE, t.confidence_probable, "structural", "strong_structural_single_engine")

        # Rule 3: semantic dominance - only WITH structural support (it used to fire without any)
        if semantic.available and e_score >= t.semantic_dominance and structural.available and s_score >= t.structural_medium:
            return out(Verdict.PROBABLE, t.confidence_semantic_support, "semantic", "semantic_dominance_with_structural_support")

        # Rule 4: medium structural + supporting statistical (graph) evidence
        if structural.available and s_score >= t.structural_medium and statistical.available and g_score >= t.statistical_strong:
            return out(Verdict.PROBABLE, t.confidence_probable, "structural_statistical", "medium_structural")

        # Rule 5: semantic-only warning (never TRUE or PROBABLE)
        if semantic.available and e_score >= t.semantic_flag and (not structural.available or s_score < t.structural_medium):
            return out(Verdict.FLAG, t.confidence_flag, "semantic", "semantic_only_warning")

        if t.review_enabled:
            # Rule 6: evidence conflict - only when BOTH sides were actually measured
            if structural.available and semantic.available and abs(s_score - e_score) > t.conflict_gap:
                return out(Verdict.REVIEW, t.confidence_conflict, "conflict", "evidence_conflict")

            # Rule 7: borderline - baseline-corrected, so ordinary same-task overlap does not count
            graph_corrected = statistical.evidence.get("corrected", 0.0) if statistical.available else 0.0
            if max(corrected_structural, graph_corrected) >= t.borderline:
                return out(Verdict.REVIEW, t.confidence_borderline, "borderline", "borderline_signals")

        # Rule 8: clean
        return out(Verdict.CLEAN, t.confidence_clean, "none", "clean")
