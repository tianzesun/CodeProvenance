"""Evaluation Layer - Online metrics evaluation ONLY.

This layer evaluates scoring results in production.
DO NOT import engines, ML, or training data logic here.
"""
from src.evaluation.core.evaluator import Evaluator
from src.evaluation.core.metrics import compute_metrics
__all__ = ['Evaluator', 'compute_metrics']
