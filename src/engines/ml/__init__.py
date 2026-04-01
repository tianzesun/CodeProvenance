"""ML-based code similarity detection."""
from benchmark.ml.tfidf_detector import (
    TFIDFSimilarityDetector,
    CodeTokenizer,
    TFIDFVector,
    detect_similarity,
    CodeFeatures,
)

__all__ = [
    'TFIDFSimilarityDetector',
    'CodeTokenizer',
    'TFIDFVector',
    'detect_similarity',
    'CodeFeatures',
]