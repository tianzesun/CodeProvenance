"""MVP detection primitives for high-precision plagiarism review."""

from src.backend.engines.mvp.ast_subtree import ASTSubtreeHasher
from src.backend.engines.mvp.normalization import CodeNormalizer
from src.backend.engines.mvp.precision_ranking import PrecisionAt20Ranker
from src.backend.engines.mvp.pipeline import MVPDetectionPipeline
from src.backend.engines.mvp.same_bug import SameBugDetector
from src.backend.engines.mvp.starter_code import StarterCodeRemover

__all__ = [
    "ASTSubtreeHasher",
    "CodeNormalizer",
    "MVPDetectionPipeline",
    "PrecisionAt20Ranker",
    "SameBugDetector",
    "StarterCodeRemover",
]
