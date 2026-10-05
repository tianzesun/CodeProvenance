"""Detection Policy - runs the Evidence Hierarchy Engine over the layer outputs.

Hierarchical decisions with an audit trail: identity hard-stops, structural evidence dominates
semantic evidence, no averaging across evidence types.

What was wrong before (and is fixed here):
- Identical files were never recognised: ``DetectionPolicy`` called the engine with EMPTY strings
  and set ``engine_scores["exact_match"] = True``, which the engine ignored. ``has_exact_file_match``
  now drives the identity rule.
- The reported ``thresholds`` (and the YAML) were NOT what decided anything: the engine had its own
  hard-coded numbers, so an auditor read thresholds that were never applied. The engine now takes
  them from :class:`~ehe.EHEThresholds`, they come from ``detection_policy.yaml`` and the report shows
  exactly the values used.
- The layer-2 value included style closeness and line-count similarity, which are high for ANY two
  files of similar size/format; only graph and control-flow evidence are used now.
- Verdicts could not be FLAG (semantic-only), ``additive_score`` was never set, the confidence
  was dropped, and a stray dict expression built evidence that nothing used.
- Constructing a policy with a ``thresholds`` object mutated the caller's object.

Course-type "weights" (``cs_code_ast_weight`` ...) never influenced a verdict; they only scaled the
displayed layer-1 value, and still only do that (see ``DetectionPolicy.display_weights``).
"""

from __future__ import annotations

import copy
import logging
from dataclasses import fields
from pathlib import Path
from typing import Any

import yaml

from src.backend.engines.detection.ehe import (
    EHEDecision,
    EHEThresholds,
    EvidenceHierarchyEngine,
    Verdict,
)
from src.backend.engines.detection.evidence_report import EvidenceReport
from src.backend.engines.detection.layer1_deterministic import Layer1Result
from src.backend.engines.detection.layer2_statistical import Layer2Result
from src.backend.engines.detection.layer3_semantic import Layer3Result

try:
    from src.backend.engines.detection.layer4_explainability import ExplanationReport
except ImportError:  # pragma: no cover
    ExplanationReport = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

DETECTION_POLICY_CONFIG_PATH = Path(__file__).parent / "detection_policy.yaml"

#: Backwards-compatible name: these are the thresholds the engine actually uses.
DecisionThresholds = EHEThresholds

#: Legacy v1/v2 YAML keys that map onto an engine threshold of the same meaning.
_LEGACY_KEYS = {"hard_match_threshold": "structural_hard_match", "flag_l3_threshold": "semantic_flag"}
_LEGACY_DISPLAY = {"cs_code_ast_weight": 1.2, "essay_semantic_weight": 1.5, "math_structure_weight": 1.3}


def _load_policy_config(path: Path | None = None) -> dict[str, Any]:
    """Load the detection policy YAML ({} when absent; a broken file is logged with its error)."""
    path = Path(path) if path else DETECTION_POLICY_CONFIG_PATH
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise TypeError("policy config must be a mapping")
        return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load detection policy config %s (%s); using defaults", path, exc)
        return {}


#: Built-in per-domain threshold overrides (the YAML ``domains:`` section replaces them per domain).
DOMAIN_PRESETS: dict[str, dict[str, float]] = {
    # Essays: semantic evidence plays a larger role, structure a smaller one
    "essay": {"semantic_flag": 0.75, "semantic_dominance": 0.90, "structural_strong": 0.70},
    # Math: structure-based evidence is more reliable
    "math": {"structural_strong": 0.70, "statistical_strong": 0.65},
}  # "code" / "cs_code": the defaults


def _set_fields(thresholds: EHEThresholds, section: dict[str, Any]) -> None:
    known = {f.name for f in fields(EHEThresholds)}
    for key, value in section.items():
        if key not in known:
            logger.warning("Unknown detection threshold %r in policy config ignored", key)
            continue
        setattr(thresholds, key, dict(value) if key == "baselines" else value)


def default_thresholds(domain: str = "code") -> EHEThresholds:
    """Default engine thresholds, adjusted for the domain (no YAML)."""
    base = EHEThresholds()
    _set_fields(base, DOMAIN_PRESETS.get(domain, {}))
    return base


def _apply_overrides(thresholds: EHEThresholds, config: dict[str, Any]) -> EHEThresholds:
    """Apply the YAML ``ehe`` / legacy ``thresholds`` / ``baselines`` sections (returns a copy)."""
    result = copy.deepcopy(thresholds)

    section = dict(config.get("ehe") or {})
    legacy = dict(config.get("thresholds") or {})
    for old, new in _LEGACY_KEYS.items():
        if old in legacy:
            section.setdefault(new, legacy[old])
    if "review_enabled" in legacy:
        section.setdefault("review_enabled", legacy["review_enabled"])
    ignored = sorted(k for k in legacy if k not in _LEGACY_KEYS and k != "review_enabled" and k not in _LEGACY_DISPLAY)
    if ignored:
        logger.warning("Ignoring legacy detection_policy.yaml thresholds that the engine does not use: %s", ignored)

    _set_fields(result, section)

    baselines = config.get("baselines") or {}
    if "embedding" in baselines:
        result.semantic_baseline = float(baselines["embedding"])
    for engine in ("ast", "ngram", "winnowing", "graph", "logic_flow"):
        if engine in baselines:
            result.baselines[engine] = float(baselines[engine])
    return result.validated()


# ═══════════════════════════════════════════════════════════════════════════
# Layer values (display + policy-engine input): the strongest EVIDENCE of each layer
# ═══════════════════════════════════════════════════════════════════════════
def _compute_layer1_value(l1: Layer1Result, domain: str = "code", display_weights: dict[str, float] | None = None) -> float:
    """Layer 1 value = the strongest deterministic signal (max, no dilution)."""
    if l1.identical_to_template:
        return 0.0
    if l1.has_exact_file_match:
        return 1.0
    if l1.exact_match_score >= 0.90:
        return l1.exact_match_score

    candidates = [
        l1.ast_subtree_overlap,
        l1.ast_node_match,
        l1.structural_similarity,
        l1.token_overlap,
        l1.winnowing_overlap,
        l1.ngram_overlap,
    ]
    weights = {**_LEGACY_DISPLAY, **(display_weights or {})}
    if domain == "cs_code":  # DISPLAY ONLY: this scaling never changes a verdict
        candidates[0] = min(1.0, l1.ast_subtree_overlap * weights["cs_code_ast_weight"])
        candidates[1] = min(1.0, l1.ast_node_match * weights["cs_code_ast_weight"])
    elif domain == "math":
        candidates[2] = min(1.0, l1.structural_similarity * weights["math_structure_weight"])
    return max(candidates)


def _compute_layer2_value(l2: Layer2Result) -> float:
    """Layer 2 value = strongest statistical EVIDENCE: graph, logic flow, control/data flow.

    Style closeness and line-count/size similarity are deliberately excluded: they are high for any
    two files of similar size and formatting, which made this value (and every rule keyed on it)
    fire on unrelated code.
    """
    return max(l2.graph_similarity, l2.logic_flow_similarity, l2.control_flow_match, l2.data_flow_match)


def _compute_layer3_value(l3: Layer3Result) -> float:
    """Layer 3 value = strongest semantic signal, capped at 0.95 (already baseline-corrected)."""
    candidates = [
        l3.embedding_similarity,
        l3.transformer_score,
        l3.concept_overlap_score,
        l3.semantic_similarity_score,
    ]
    return min(0.95, max(candidates))


def _explain_decision(decision: EHEDecision, l1_val: float, l2_val: float, l3_val: float, t: EHEThresholds) -> str:
    """Explanation naming the rule that fired and the thresholds actually applied."""
    sig = decision.evidence.get("structural", {}) if decision.evidence else {}
    structural = ", ".join(f"{k}={v:.0%}" for k, v in sig.items() if not k.endswith("_corrected")) or "none"
    rule = decision.rule
    if rule == "identity_override":
        return "Identity override: the files are identical."
    if rule == "strong_structural":
        return (
            f"Hard structural match: strongest structural engine {decision.raw_scores.get('structural', 0):.0%} "
            f">= {t.structural_hard_match:.0%} ({structural})."
        )
    if rule == "strong_structural_corroborated":
        return (
            f"Strong structural match ({decision.raw_scores.get('structural', 0):.0%} >= {t.structural_strong:.0%}) "
            f"corroborated by at least {t.min_agreeing_engines} structural engines ({structural})."
        )
    if rule == "strong_structural_single_engine":
        return (
            f"One structural engine is strong ({decision.raw_scores.get('structural', 0):.0%} >= "
            f"{t.structural_strong:.0%}) but fewer than {t.min_agreeing_engines} engines agree ({structural}): "
            "probable, needs manual review."
        )
    if rule == "semantic_dominance_with_structural_support":
        return (
            f"Very strong semantic similarity ({decision.raw_scores.get('semantic', 0):.0%}) with structural support "
            f"({decision.raw_scores.get('structural', 0):.0%}): probable, needs manual review."
        )
    if rule == "medium_structural":
        return (
            f"Moderate structural match ({decision.raw_scores.get('structural', 0):.0%} >= {t.structural_medium:.0%}) "
            f"supported by graph similarity ({decision.raw_scores.get('statistical', 0):.0%} >= {t.statistical_strong:.0%}): "
            "probable, needs manual review."
        )
    if rule == "semantic_only_warning":
        return (
            f"Semantic flag: semantic similarity {decision.raw_scores.get('semantic', 0):.0%} >= {t.semantic_flag:.0%} "
            "without structural support. Manual review REQUIRED; high false-positive risk."
        )
    if rule == "evidence_conflict":
        return (
            f"Evidence conflict: structural {decision.raw_scores.get('structural', 0):.0%} and semantic "
            f"{decision.raw_scores.get('semantic', 0):.0%} differ by more than {t.conflict_gap:.0%}. Human review required."
        )
    if rule == "borderline_signals":
        return (
            f"Borderline signals (L1={l1_val:.0%}, L2={l2_val:.0%}) above the noise floor of unrelated files: "
            "too weak for automated action, too strong to ignore. Manual inspection recommended."
        )
    return f"No significant similarity detected (L1={l1_val:.0%}, L2={l2_val:.0%}, L3={l3_val:.0%})."


class DetectionPolicy:
    """Rule-based detection policy using the Evidence Hierarchy Engine."""

    def __init__(
        self,
        thresholds: EHEThresholds | None = None,
        domain: str = "code",
        config_path: Path | None = None,
    ):
        self.domain = domain
        self._config = _load_policy_config(config_path)
        self._explicit_thresholds = copy.deepcopy(thresholds) if thresholds is not None else None  # (the caller's object is no longer mutated)
        self.display_weights = {**_LEGACY_DISPLAY, **{k: float(v) for k, v in (self._config.get("display_weights") or {}).items()}}
        self._engines: dict[str, tuple[EHEThresholds, EvidenceHierarchyEngine]] = {}
        self.thresholds, self.ehe = self._engine_for(domain)

    def _engine_for(self, domain: str) -> tuple[EHEThresholds, EvidenceHierarchyEngine]:
        if domain not in self._engines:
            # layering: defaults -> YAML ``ehe`` (global) -> domain override (YAML ``domains`` or the
            # built-in preset). Explicit caller thresholds are final: no YAML, no domain preset.
            try:
                if self._explicit_thresholds is not None:
                    thresholds = self._explicit_thresholds.validated()  # final: neither YAML nor presets
                else:
                    thresholds = _apply_overrides(EHEThresholds(), self._config)
                    domains = self._config.get("domains") or {}
                    _set_fields(thresholds, dict(domains.get(domain) or DOMAIN_PRESETS.get(domain, {})))
                    thresholds = thresholds.validated()
            except ValueError as exc:
                logger.error("Invalid detection policy configuration (%s); using default thresholds", exc)
                thresholds = (self._explicit_thresholds or default_thresholds(domain)).validated()
            self._engines[domain] = (thresholds, EvidenceHierarchyEngine(thresholds))
        return self._engines[domain]

    def evaluate(
        self,
        l1_result: Layer1Result,
        l2_result: Layer2Result,
        l3_result: Layer3Result,
        course_type: str | None = None,
        explanation_report: ExplanationReport | None = None,
    ) -> EvidenceReport:
        """Run the decision engine over the layer outputs.

        Args:
            l1_result, l2_result, l3_result: Outputs of the three layers.
            course_type: Optional domain hint ('cs_code', 'essay', 'math', ...). It selects the
                threshold preset (unless explicit thresholds were given).
            explanation_report: Optional Layer 4 report appended to the explanation.
        """
        domain = course_type or self.domain
        thresholds, engine = self._engine_for(domain)

        l1_val = _compute_layer1_value(l1_result, domain, self.display_weights)
        l2_val = _compute_layer2_value(l2_result)
        l3_val = _compute_layer3_value(l3_result)

        if l1_result.identical_to_template:
            decision = EHEDecision(
                verdict=Verdict.CLEAN,
                confidence=thresholds.confidence_clean,
                triggered_layer="template",
                decision_path=["template_only"],
                raw_scores={},
                rule="template_only",
            )
            explanation = "Both files are identical to the instructor's starter code: no evidence of copying."
        else:
            # Missing engines stay None (unavailable); style similarity is informational only.
            engine_scores: dict[str, float | None] = {
                "ast": l1_result.engine_scores.get("ast"),
                "ngram": l1_result.engine_scores.get("ngram"),
                "winnowing": l1_result.engine_scores.get("winnowing"),
                "logic_flow": l2_result.engine_scores.get("logic_flow"),
                "graph": l2_result.engine_scores.get("graph") if "graph" in l2_result.available_engines else None,
                "stylometry": 1.0 - l2_result.stylometric_distance,
                "embedding": l3_result.engine_scores.get("embedding"),
            }
            decision = engine.decide(
                code_a="", code_b="", engine_scores=engine_scores, identity_match=bool(l1_result.has_exact_file_match)
            )
            explanation = _explain_decision(decision, l1_val, l2_val, l3_val, thresholds)

        if explanation_report:
            explanation += "\n\n" + explanation_report.summary()

        verdict = decision.verdict
        return EvidenceReport(
            verdict=verdict,
            decision_path=" → ".join(decision.decision_path),
            decision_rule=decision.rule,
            confidence=decision.confidence,
            layer1_value=round(l1_val, 4),
            layer2_value=round(l2_val, 4),
            layer3_value=round(l3_val, 4),
            explanation=explanation,
            layer1_evidence=l1_result,
            layer2_evidence=l2_result,
            layer3_evidence=l3_result,
            explanation_evidence=explanation_report,
            thresholds=thresholds.to_dict(),
            # compatibility score for the existing UI; never used to decide
            additive_score=0.0 if verdict == Verdict.CLEAN else round(max(l1_val, l2_val, l3_val), 4),
        )

    def get_thresholds(self) -> dict[str, Any]:
        """The decision thresholds in force (for display/settings)."""
        return self.thresholds.to_dict()

    @classmethod
    def available_domains(cls) -> dict[str, str]:
        """Available domain presets."""
        return {
            "code": "General code plagiarism detection (balanced)",
            "cs_code": "CS programming assignments (structural evidence dominant)",
            "essay": "Essay/report similarity (semantic-weighted, lower semantic flag threshold)",
            "math": "Mathematics proofs (structure-weighted)",
        }
