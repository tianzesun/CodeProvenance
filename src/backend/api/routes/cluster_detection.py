"""API router for Cluster Detection endpoints."""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.evaluation.cluster_detection import (
    ClusterDetector,
    SimilarityEdge,
    SubmissionNode,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cluster-detection", tags=["cluster-detection"])

DEFAULT_THRESHOLD = 0.65
_MAX_SUBMISSIONS = 5_000
_MAX_EDGES = 100_000
_MAX_CONTENT_CHARS = 1_000_000


class SubmissionNodeSchema(BaseModel):
    """Schema for submission node input."""

    submission_id: str = Field(..., min_length=1, max_length=256)
    code_hash: str = Field(default="", max_length=128)
    language: str = Field(default="unknown", max_length=64)
    content: str = Field(default="", max_length=_MAX_CONTENT_CHARS)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimilarityEdgeSchema(BaseModel):
    """Schema for similarity edge input."""

    submission_a: str = Field(..., min_length=1, max_length=256)
    submission_b: str = Field(..., min_length=1, max_length=256)
    similarity: float = Field(..., ge=0.0, le=1.0)
    engine: str = Field(default="unknown", max_length=64)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ClusterDetectionRequest(BaseModel):
    """Request body for cluster detection."""

    submissions: list[SubmissionNodeSchema] = Field(..., max_length=_MAX_SUBMISSIONS)
    edges: list[SimilarityEdgeSchema] = Field(..., max_length=_MAX_EDGES)
    # ``None`` used to reach ClusterDetector(threshold=None) and fail inside it.
    threshold: float | None = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)


def _failure(action: str) -> HTTPException:
    """Log the active exception; return a generic 500 with a reference id."""
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s failed (ref=%s)", action, ref)
    return HTTPException(status_code=500, detail=f"{action} failed. Reference: {ref}")


def edges_from_matrix(
    ids: set[str], matrix: dict[str, dict[str, float]]
) -> list[SimilarityEdge]:
    """Build one edge per unordered pair from a (possibly one-sided) matrix.

    The old code kept only entries where ``a < b`` as strings, so a matrix
    filled in the lower triangle (``{"b": {"a": 0.9}}``) silently produced no
    edges and no clusters. Each unordered pair is now kept once, using the
    higher score when both triangles are present.
    """
    best: dict[tuple[str, str], float] = {}
    for a, row in matrix.items():
        for b, score in row.items():
            if a == b:
                continue
            if a not in ids or b not in ids:
                raise HTTPException(
                    status_code=422,
                    detail="similarity_matrix references an id that is not in submissions",
                )
            if isinstance(score, bool) or not math.isfinite(score) or not 0.0 <= score <= 1.0:
                raise HTTPException(
                    status_code=422, detail="Similarity scores must be between 0.0 and 1.0"
                )
            key = (a, b) if a < b else (b, a)
            if score > best.get(key, -1.0):
                best[key] = score
    return [
        SimilarityEdge(submission_a=a, submission_b=b, similarity=s, engine="combined")
        for (a, b), s in best.items()
    ]


# Plain ``def`` handlers: clustering is CPU-bound, so FastAPI runs them in a
# worker thread instead of blocking the event loop.


@router.post("/detect")
def detect_clusters(request: ClusterDetectionRequest) -> dict[str, Any]:
    """
    Detect plagiarism clusters from similarity data.

    Returns:
        ClusterDetectionResult with detected clusters.
    """
    known = {s.submission_id for s in request.submissions}
    for e in request.edges:
        if e.submission_a not in known or e.submission_b not in known:
            raise HTTPException(
                status_code=422, detail="An edge references a submission that was not provided"
            )

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
        threshold = DEFAULT_THRESHOLD if request.threshold is None else request.threshold
        return ClusterDetector(threshold=threshold).detect(submissions, edges).to_dict()
    except Exception:
        raise _failure("Cluster detection") from None


@router.get("/stats")
async def get_cluster_stats(
    threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0, description="Similarity threshold"),
) -> dict[str, Any]:
    """
    Get cluster detection statistics.

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
def analyze_clusters(
    submissions: list[str],
    similarity_matrix: dict[str, dict[str, float]],
    threshold: float = Query(DEFAULT_THRESHOLD, ge=0.0, le=1.0, description="Similarity threshold"),
) -> dict[str, Any]:
    """
    Analyze clusters from a similarity matrix.

    Args:
        submissions: List of submission IDs.
        similarity_matrix: Matrix of pairwise similarities (either triangle, or both).
        threshold: Similarity threshold for clustering.

    Returns:
        Cluster detection results.
    """
    if len(submissions) > _MAX_SUBMISSIONS:
        raise HTTPException(
            status_code=413, detail=f"At most {_MAX_SUBMISSIONS} submissions are allowed"
        )
    if sum(len(row) for row in similarity_matrix.values()) > _MAX_EDGES * 2:
        raise HTTPException(status_code=413, detail="similarity_matrix is too large")
    ids = set(submissions)
    edges = edges_from_matrix(ids, similarity_matrix)
    try:
        nodes = [
            SubmissionNode(submission_id=sid, code_hash="", language="unknown", content="")
            for sid in submissions
        ]
        return ClusterDetector(threshold=threshold).detect(nodes, edges).to_dict()
    except Exception:
        raise _failure("Cluster analysis") from None
