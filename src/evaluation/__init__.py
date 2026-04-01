"""Evaluation Online - Production-safe metrics only.

This layer evaluates scoring results in production.
Latency-safe, no external systems.
"""
from src.evaluation.core.evaluator import Evaluator
from src.evaluation.core.metrics import compute_metrics
__all__ = ['Evaluator', 'compute_metrics']
