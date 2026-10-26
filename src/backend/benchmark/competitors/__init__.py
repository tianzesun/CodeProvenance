"""Competitor benchmark framework.

Provides adapters for external plagiarism detection tools (MOSS, JPlag, Dolos,
Copyleaks, Turnitin) and a runner + report generator for head-to-head comparison
on shared datasets with Precision, Recall, F1, ROC-AUC, per-clone-type breakdown,
bootstrap confidence intervals, and McNemar significance tests.
"""
from __future__ import annotations

from .adapters import (
    ALL_COMPETITOR_ADAPTERS,
    CodequiryAdapter,
    DeckardAdapter,
    DolosAdapter,
    ExternalToolAdapter,
    JPlagAdapter,
    LLMSimilarityBaselineAdapter,
    MOSSAdapter,
    NiCadAdapter,
    PMDCPDAdapter,
    SourcererCCAdapter,
    STRANGEAdapter,
    TransformerSemanticBaselineAdapter,
    TurnitinAdapter,
    VendetectAdapter,
)
from .report import CompetitorComparisonReport
from .runner import CompetitorBenchmarkRunner

__all__ = [
    "ALL_COMPETITOR_ADAPTERS",
    "CodequiryAdapter",
    "CompetitorBenchmarkRunner",
    "CompetitorComparisonReport",
    "DeckardAdapter",
    "DolosAdapter",
    "ExternalToolAdapter",
    "JPlagAdapter",
    "LLMSimilarityBaselineAdapter",
    "MOSSAdapter",
    "NiCadAdapter",
    "PMDCPDAdapter",
    "STRANGEAdapter",
    "SourcererCCAdapter",
    "TransformerSemanticBaselineAdapter",
    "TurnitinAdapter",
    "VendetectAdapter",
]
