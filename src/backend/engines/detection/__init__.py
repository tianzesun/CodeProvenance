"""Layered detection pipeline: Deterministic -> Statistical -> Semantic -> Explainability.

Replaces weighted fusion with an interpretable, rule-based decision policy. Each layer has a clear
meaning and produces auditable evidence.

Pipeline:
  Layer 1 (Deterministic):  Token, AST, winnowing - high-precision hard match
  Layer 2 (Statistical):    Graph and control-flow sequences - paraphrase detection
  Layer 3 (Semantic):       Embedding, transformer - meaning-level similarity (never decisive alone)
  Layer 4 (Explainability): Function/block/structure/control-flow evidence - audit trail
Decision engines:
  EvidenceHierarchyEngine / DetectionPolicy  hierarchy with explicit thresholds (detection_policy.yaml)
  PolicyEngine / FEDS                        declarative rules (policy.yaml)
"""

from src.backend.engines.detection.detection_policy import DecisionThresholds, DetectionPolicy
from src.backend.engines.detection.ehe import EHEThresholds, EvidenceHierarchyEngine
from src.backend.engines.detection.evidence_report import EvidenceReport, Verdict
from src.backend.engines.detection.feds_specification import FEDS
from src.backend.engines.detection.layer1_deterministic import Layer1Deterministic
from src.backend.engines.detection.layer2_statistical import Layer2Statistical
from src.backend.engines.detection.layer3_semantic import Layer3Semantic
from src.backend.engines.detection.layer4_explainability import Layer4Explainability
from src.backend.engines.detection.policy_engine import PolicyEngine

__all__ = [
    "DecisionThresholds",
    "DetectionPolicy",
    "EHEThresholds",
    "EvidenceHierarchyEngine",
    "EvidenceReport",
    "FEDS",
    "Layer1Deterministic",
    "Layer2Statistical",
    "Layer3Semantic",
    "Layer4Explainability",
    "PolicyEngine",
    "Verdict",
]
