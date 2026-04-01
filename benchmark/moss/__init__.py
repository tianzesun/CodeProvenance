"""MOSS integration module.

Provides MOSS baseline benchmark runner for comparison against custom engines.

Usage:
    from benchmark.moss import MossRunner, MossScoreEngine
    
    runner = MossRunner(user_id="12345678")
    results = runner.evaluate(pairs)
    
    # Or as engine:
    engine = MossScoreEngine(user_id="12345678")
    score = engine.compare(code_a, code_b)
"""
from benchmark.moss.runner import (
    MossRunner,
    MossScoreEngine,
    MossResult,
)

__all__ = [
    "MossRunner",
    "MossScoreEngine",
    "MossResult",
]