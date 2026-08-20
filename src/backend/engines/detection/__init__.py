"""Three-layer detection pipeline: Deterministic → Statistical → Semantic.

Replaces weighted fusion with an interpretable rule-based decision policy.
Each layer has a clear semantic meaning and produces auditable evidence.

Pipeline:
  Layer 1 (Deterministic):  Token, AST, winnowing — high-precision hard match
  Layer 2 (Statistical):    Graph, stylometry, logic flow — paraphrase detection
  Layer 3 (Semantic):       Embedding, transformer — meaning-level similarity
  Layer 4 (Explainability): Function/block/AST/control-flow evidence — audit trail
"""

from src.backend.engines.detection.layer1_deterministic import Layer1Deterministic
from src.backend.engines.detection.layer2_statistical import Layer2Statistical
from src.backend.engines.detection.layer3_semantic import Layer3Semantic
from src.backend.engines.detection.layer4_explainability import Layer4Explainability
from src.backend.engines.detection.detection_policy import DetectionPolicy
from src.backend.engines.detection.evidence_report import EvidenceReport, Verdict

__all__ = [
    "Layer1Deterministic",
    "Layer2Statistical",
    "Layer3Semantic",
    "Layer4Explainability",
    "DetectionPolicy",
    "EvidenceReport",
    "Verdict",
]
