"""API router for Cluster Detection endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.backend.evaluation.cluster_detection import (
    ClusterDetector,
    SimilarityEdge,
    SubmissionNode,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cluster-detection", tags=["cluster-detection"])


class SubmissionNodeSchema(BaseModel):
    """Schema for submission node input."""

    submission_id: str
    code_hash: str = ""
    language: str = "unknown"
    content: str = ""
    metadata: dict[str, Any] = {}


class SimilarityEdgeSchema(BaseModel):
    """Schema for similarity edge input."""

    submission_a: str
    submission_b: str
    similarity: float
    engine: str = "unknown"
    confidence: float = 1.0
    evidence: list[dict[str, Any]] = []


class ClusterDetectionRequest(BaseModel):
    """Request body for cluster detection."""

    submissions: list[SubmissionNodeSchema]
    edges: list[SimilarityEdgeSchema]
    threshold: float | None = 0.65


@router.post("/detect")
async def detect_clusters(
    request: ClusterDetectionRequest,
) -> dict[str, Any]:
    """
    Detect plagiarism clusters from similarity data.

    Args:
        request: Cluster detection request with submissions and edges.

    Returns:
        ClusterDetectionResult with detected clusters.
    """
    try:
        submissions = [
            SubmissionNode(
                submission_id=s.submission_id,
                code_hash=s.code_hash,
                language=s.language,
                content=s.content,
                metadata=s.metadata,
            )
            for s in request.submissions
        ]

        edges = [
            SimilarityEdge(
                submission_a=e.submission_a,
                submission_b=e.submission_b,
                similarity=e.similarity,
                engine=e.engine,
                confidence=e.confidence,
                evidence=e.evidence,
            )
            for e in request.edges
        ]

        detector = ClusterDetector(threshold=request.threshold)
        result = detector.detect(submissions, edges)

        return result.to_dict()

    except Exception as e:
        logger.error(f"Cluster detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_cluster_stats(
    threshold: float = Query(0.65, description="Similarity threshold"),
) -> dict[str, Any]:
    """
    Get cluster detection statistics.

    Args:
        threshold: Similarity threshold used for clustering.

    Returns:
        Statistics about cluster detection configuration.
    """
    return {
        "threshold": threshold,
        "min_cluster_size": 2,
        "algorithm": "Union-Find with path compression",
        "description": "Groups submissions with similarity >= threshold into clusters",
    }


@router.post("/analyze")
async def analyze_clusters(
    submissions: list[str],
    similarity_matrix: dict[str, dict[str, float]],
    threshold: float = Query(0.65, description="Similarity threshold"),
) -> dict[str, Any]:
    """
    Analyze clusters from a similarity matrix.

    Args:
        submissions: List of submission IDs.
        similarity_matrix: Matrix of pairwise similarities.
        threshold: Similarity threshold for clustering.

    Returns:
        Cluster detection results.
    """
    try:
        # Build submission nodes
        nodes = [
            SubmissionNode(
                submission_id=sid,
                code_hash="",
                language="unknown",
                content="",
            )
            for sid in submissions
        ]

        # Build edges from matrix
        edges = []
        for a, similarities in similarity_matrix.items():
            for b, score in similarities.items():
                if a < b:  # Avoid duplicates
                    edges.append(
                        SimilarityEdge(
                            submission_a=a,
                            submission_b=b,
                            similarity=score,
                            engine="combined",
                        )
                    )

        detector = ClusterDetector(threshold=threshold)
        result = detector.detect(nodes, edges)

        return result.to_dict()

    except Exception as e:
        logger.error(f"Cluster analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
