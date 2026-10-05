"""
Visualization API endpoint for frontend explainable reports.

Returns structured JSON for AST visualization, GST block matches,
heatmaps, and auto-generated explanations.
"""

import functools
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.backend.engines.explainable_report_generator import ReportGenerator
from src.backend.engines.similarity.base_similarity import (
    SimilarityEngine,
    register_builtin_algorithms,
)

router = APIRouter()
report_generator = ReportGenerator()

# AST/GST comparison is superlinear in file size, so unbounded input is a cheap
# way to tie up a worker.
_MAX_CODE_CHARS = 200_000


class VisualizeRequest(BaseModel):
    """Request body: the two code files to compare."""

    # Missing/empty values are rejected with 400 below, as before.
    code_a: str = Field(default="", max_length=_MAX_CODE_CHARS)
    code_b: str = Field(default="", max_length=_MAX_CODE_CHARS)


_engine_lock = threading.Lock()


@functools.lru_cache(maxsize=1)
def _get_engine() -> SimilarityEngine:
    """Build and register the similarity engine once, not on every request."""
    engine = SimilarityEngine()
    register_builtin_algorithms(engine)
    return engine


def build_heatmap(length: int, ranges: list[tuple[int, int, float]]) -> list[float]:
    """Per-line intensity: the strongest match covering each line (0.0 if none)."""
    heat = [0.0] * length
    for start, end, strength in ranges:
        for i in range(max(0, start), min(length, end)):
            if strength > heat[i]:
                heat[i] = strength
    return heat


# Plain ``def``: the comparison is CPU-bound, so FastAPI runs it in a worker
# thread instead of blocking the event loop. The unused ``db`` dependency was
# also removed — it checked a database connection out of the pool on every
# request without ever using it.
@router.post("/v1/visualize", response_model=dict[str, Any])
def visualize_pair(data: VisualizeRequest):
    """
    Generate structured visualization data for a pair of code files.

    Returns data for frontend visualization:
    - AST matches (structure alignment)
    - GST block matches (copied regions)
    - Heatmap data (similarity intensity per line)
    - Auto-generated explanation text

    **Request Body:**
    - `code_a`: First code content
    - `code_b`: Second code content
    """
    code_a, code_b = data.code_a, data.code_b

    if not code_a or not code_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both code_a and code_b are required",
        )

    # Calculate all engine scores and the explainable report. The shared engine
    # and generator were only ever called from one thread before; their
    # thread-safety is not known, so calls are serialised.
    with _engine_lock:
        result = _get_engine().compare({"raw": code_a}, {"raw": code_b})
        scores = result.get("individual_scores", {})
        final_score = result.get("overall_score", 0.0)
        report = report_generator.generate_report(code_a, code_b, scores, final_score)

    # Heatmap data from the GST block matches
    gst_blocks = report.gst_blocks
    heatmap_a = build_heatmap(
        len(code_a.splitlines()),
        [(b["a_start"], b["a_end"], b["match_percent"] / 100.0) for b in gst_blocks],
    )
    heatmap_b = build_heatmap(
        len(code_b.splitlines()),
        [(b["b_start"], b["b_end"], b["match_percent"] / 100.0) for b in gst_blocks],
    )

    # Confidence label
    confidence = (
        "high" if final_score >= 0.8 else "medium" if final_score >= 0.5 else "low"
    )

    ast_matches = [
        {"a_node": a, "b_node": b, "confidence": 0.9} for a, b in report.ast_matches
    ]

    gst_matches = [
        {
            "a_range": [block["a_start"], block["a_end"]],
            "b_range": [block["b_start"], block["b_end"]],
            "code_a": block.get("a_snippet", ""),
            "code_b": block.get("b_snippet", ""),
            "match_strength": block["match_percent"] / 100.0,
        }
        for block in gst_blocks
    ]

    return {
        "score": round(final_score, 3),
        "confidence": confidence,
        "confidence_value": round(report.confidence, 3),
        "detected_strategies": report.detected_strategies,
        "ast_matches": ast_matches,
        "gst_matches": gst_matches,
        "heatmap": {
            "a": [round(s, 2) for s in heatmap_a],
            "b": [round(s, 2) for s in heatmap_b],
        },
        "explanation": report.transformation_analysis
        + [f"Final verdict: {report.final_verdict}"],
        "engine_scores": {k: round(v, 3) for k, v in scores.items()},
    }
