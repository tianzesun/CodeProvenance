"""Clone taxonomy module for code similarity detection.

Provides clone type classification and technique detection:
- CloneTypeClassifier: Classifies code pairs by clone type
- TechniqueDetector: Detects code transformation techniques
"""
from src.backend.benchmark.forensics.clone_taxonomy.type_classifier import (
    CloneTypeClassifier,
    CloneType,
    CloneTypeReport,
)
from src.backend.benchmark.forensics.clone_taxonomy.technique_detector import (
    TechniqueDetector,
    TechniqueType,
    TechniqueReport,
)

__all__ = [
    # Clone type classification
    "CloneTypeClassifier",
    "CloneType",
    "CloneTypeReport",
    # Technique detection
    "TechniqueDetector",
    "TechniqueType",
    "TechniqueReport",
]