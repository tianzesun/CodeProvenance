"""
Pydantic schemas for similarity results API requests and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MatchingBlock(BaseModel):
    file_a: str
    file_b: str
    lines_a: str  # e.g., "10-50"
    lines_b: str  # e.g., "12-52"
    similarity: float = Field(..., ge=0.0, le=1.0)
    block_type: str | None = None  # e.g., "function", "class", "code_block"
    function_name: str | None = None
    token_overlap: float | None = None
    ast_similarity: float | None = None


class ExcludedMatch(BaseModel):
    reason: str  # e.g., "template_match", "boilerplate"
    description: str
    template_file: str | None = None
    file_a: str | None = None
    file_b: str | None = None


class SimilarityResultBase(BaseModel):
    submission_a_id: uuid.UUID
    submission_b_id: uuid.UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    confidence_lower: float = Field(..., ge=0.0, le=1.0)
    confidence_upper: float = Field(..., ge=0.0, le=1.0)
    confidence_level: float = Field(0.95, ge=0.0, le=1.0)
    matching_blocks: list[MatchingBlock] = Field(default_factory=list)
    excluded_matches: list[ExcludedMatch] = Field(default_factory=list)
    algorithm_scores: dict[str, float] | None = None
    verdict: str | None = Field(
        None, description="Rule-based verdict: TRUE, PROBABLE, REVIEW, FLAG, CLEAN"
    )


class SimilarityResultCreate(SimilarityResultBase):
    job_id: uuid.UUID


class SimilarityResultResponse(SimilarityResultBase):
    id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ResultsResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    threshold_used: float
    total_submissions: int
    total_pairs: int
    high_similarity_pairs: int
    execution_time_ms: int
    results: list[SimilarityResultResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)
