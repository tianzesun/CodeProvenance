"""Competitor benchmark framework.

Provides adapters for external plagiarism detection tools (MOSS, JPlag, Dolos,
Copyleaks, Turnitin) and a runner + report generator for head-to-head comparison
on shared datasets with Precision, Recall, F1, ROC-AUC, per-clone-type breakdown,
bootstrap confidence intervals, and McNemar significance tests.
"""
from __future__ import annotations

from .adapters import (
    ExternalToolAdapter,
    MOSSAdapter,
    JPlagAdapter,
    DolosAdapter,
    TurnitinAdapter,
    CodequiryAdapter,
    SourcererCCAdapter,
    DeckardAdapter,
    TransformerSemanticBaselineAdapter,
    LLMSimilarityBaselineAdapter,
    NiCadAdapter,
    PMDCPDAdapter,
    STRANGEAdapter,
    VendetectAdapter,
    ALL_COMPETITOR_ADAPTERS,
)
from .runner import CompetitorBenchmarkRunner
from .report import CompetitorComparisonReport

__all__ = [
    "ExternalToolAdapter",
    "MOSSAdapter",
    "JPlagAdapter",
    "DolosAdapter",
    "TurnitinAdapter",
    "CodequiryAdapter",
    "SourcererCCAdapter",
    "DeckardAdapter",
    "TransformerSemanticBaselineAdapter",
    "LLMSimilarityBaselineAdapter",
    "NiCadAdapter",
    "PMDCPDAdapter",
    "STRANGEAdapter",
    "VendetectAdapter",
    "ALL_COMPETITOR_ADAPTERS",
    "CompetitorBenchmarkRunner",
    "CompetitorComparisonReport",
]
