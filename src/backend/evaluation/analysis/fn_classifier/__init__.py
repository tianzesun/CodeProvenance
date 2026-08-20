"""
FN (False Negative) Classifier - System for analyzing and categorizing missed detections.

FNs are the most valuable training data source.
This system classifies FNs into categories for targeted model improvement.
"""

from src.backend.evaluation_dataset.fn_classifier.classifier import FNClassifier
from src.backend.evaluation_dataset.fn_classifier.taxonomy import (
    FNAnalysis,
    FNCategory,
    FNResult,
)

__all__ = ["FNAnalysis", "FNCategory", "FNClassifier", "FNResult"]
