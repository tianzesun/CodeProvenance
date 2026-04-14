"""
Token-Level Heatmap Module

Provides token-level precision highlighting for code similarity detection.

Architecture:
    ASTTokenExtractor → CharacterOffsetMapper → TokenHeatmapEngine → ReactInlineRenderer

Usage:
    engine = TokenHeatmapEngine()
    spans = engine.build_heatmap(matches)
"""

from .models import (
    TokenSpan,
    HeatmapResult,
    HeatIntensity,
)
from .extractor import ASTTokenExtractor
from .mapper import CharacterOffsetMapper
from .intensity import HeatIntensityCalculator
from .engine import TokenHeatmapEngine

__all__ = [
    "TokenSpan",
    "HeatmapResult",
    "HeatIntensity",
    "ASTTokenExtractor",
    "CharacterOffsetMapper",
    "HeatIntensityCalculator",
    "TokenHeatmapEngine",
]