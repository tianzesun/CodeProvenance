"""Canonical evaluation result contract.

The INVARIANT (every system MUST output this schema) now lives in
``src.backend.contracts.evaluation_result`` so there is a single source of
truth for the schemas. This module keeps the historic
``src.backend.benchmark.contracts.evaluation_result`` import path working for
existing adapters, runners and pipeline code.
"""

from __future__ import annotations

from src.backend.contracts.evaluation_result import EnrichedPair, EvaluationResult

__all__ = ["EnrichedPair", "EvaluationResult"]
