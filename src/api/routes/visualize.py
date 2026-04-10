"""
Visualization API endpoint for frontend explainable reports.

Returns structured JSON for AST visualization, GST block matches,
heatmaps, and auto-generated explanations.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Dict, Any
import ast

from src.config.database import get_db
from src.engines.report_generator import ReportGenerator
from src.engines.similarity.ast_similarity import ASTSimilarity
from src.engines.similarity.token_similarity import TokenSimilarity
from src.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms


router = APIRouter()
report_generator = ReportGenerator()
ast_engine = ASTSimilarity()
token_engine = TokenSimilarity()


@router.post("/v1/visualize", response_model=Dict[str, Any])
async def visualize_pair(
    request: Request,
    data: Dict[str, Any],
    db = Depends(get_db)
):
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
    code_a = data.get("code_a", "")
    code_b = data.get("code_b", "")
    
    if not code_a or not code_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both code_a and code_b are required"
        )
    
    # Calculate all engine scores
    engine = SimilarityEngine()
    register_builtin_algorithms(engine)
    result = engine.compare({"raw": code_a}, {"raw": code_b})
    
    scores = result.get("individual_scores", {})
    final_score = result.get("overall_score", 0.0)
    
    # Generate explainable report
    report = report_generator.generate_report(code_a, code_b, scores, final_score)
    
    # Generate heatmap data
    lines_a = code_a.splitlines()
    lines_b = code_b.splitlines()
    
    heatmap_a = [0.0] * len(lines_a)
    heatmap_b = [0.0] * len(lines_b)
    
    # Apply GST block matches to heatmap
    for block in report.gst_blocks:
        a_start, a_end = block["a_start"], block["a_end"]
        b_start, b_end = block["b_start"], block["b_end"]
        
        for i in range(max(0, a_start), min(len(heatmap_a), a_end)):
            heatmap_a[i] = max(heatmap_a[i], block["match_percent"] / 100.0)
        
        for i in range(max(0, b_start), min(len(heatmap_b), b_end)):
            heatmap_b[i] = max(heatmap_b[i], block["match_percent"] / 100.0)
    
    # Confidence label
    confidence = "high" if final_score >= 0.8 else "medium" if final_score >= 0.5 else "low"
    
    # Format AST matches
    ast_matches = [
        {"a_node": a, "b_node": b, "confidence": 0.9}
        for a, b in report.ast_matches
    ]
    
    # Format GST matches
    gst_matches = []
    for block in report.gst_blocks:
        gst_matches.append({
            "a_range": [block["a_start"], block["a_end"]],
            "b_range": [block["b_start"], block["b_end"]],
            "code_a": block.get("a_snippet", ""),
            "code_b": block.get("b_snippet", ""),
            "match_strength": block["match_percent"] / 100.0
        })
    
    return {
        "score": round(final_score, 3),
        "confidence": confidence,
        "confidence_value": round(report.confidence, 3),
        "detected_strategies": report.detected_strategies,
        
        "ast_matches": ast_matches,
        "gst_matches": gst_matches,
        
        "heatmap": {
            "a": [round(s, 2) for s in heatmap_a],
            "b": [round(s, 2) for s in heatmap_b]
        },
        
        "explanation": report.transformation_analysis + [
            f"Final verdict: {report.final_verdict}"
        ],
        
        "engine_scores": {k: round(v, 3) for k, v in scores.items()}
    }
