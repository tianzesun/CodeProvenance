"""ML-based code similarity detection."""

from benchmark.ml.tfidf_detector import (
    CodeFeatures,
    CodeTokenizer,
    TFIDFSimilarityDetector,
    TFIDFVector,
    detect_similarity,
)

__all__ = [
    "CodeFeatures",
    "CodeTokenizer",
    "TFIDFSimilarityDetector",
    "TFIDFVector",
    "detect_similarity",
]
