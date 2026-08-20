"""
Token-Level Heatmap Module

Provides token-level precision highlighting for code similarity detection.

Architecture:
    ASTTokenExtractor → CharacterOffsetMapper → TokenHeatmapEngine → ReactInlineRenderer

Usage:
    engine = TokenHeatmapEngine()
    spans = engine.build_heatmap(matches)
"""

from .engine import TokenHeatmapEngine
from .extractor import ASTTokenExtractor
from .intensity import HeatIntensityCalculator
from .mapper import CharacterOffsetMapper
from .models import (
    HeatIntensity,
    HeatmapResult,
    TokenSpan,
)

__all__ = [
    "ASTTokenExtractor",
    "CharacterOffsetMapper",
    "HeatIntensity",
    "HeatIntensityCalculator",
    "HeatmapResult",
    "TokenHeatmapEngine",
    "TokenSpan",
]
