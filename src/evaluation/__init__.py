"""Evaluation Layer - Split into production vs offline."""
from src.evaluation.core.evaluator import Evaluator
from src.evaluation.core.metrics import compute_metrics
__all__ = ['Evaluator', 'compute_metrics']
