"""
Pydantic schemas for similarity results API requests and responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    # Optional: stored results can have no interval (the routes already treat a
    # NULL bound as "missing"), and a required field made every such row fail
    # response validation. SimilarityResultCreate requires both again.
    confidence_lower: float | None = Field(None, ge=0.0, le=1.0)
    confidence_upper: float | None = Field(None, ge=0.0, le=1.0)
    confidence_level: float = Field(0.95, ge=0.0, le=1.0)
    matching_blocks: list[MatchingBlock] = Field(default_factory=list)
    excluded_matches: list[ExcludedMatch] = Field(default_factory=list)
    algorithm_scores: dict[str, float] | None = None
    verdict: str | None = Field(
        None,
        max_length=32,
        description="Rule-based verdict: TRUE, PROBABLE, REVIEW, FLAG, CLEAN",
    )


class SimilarityResultCreate(SimilarityResultBase):
    job_id: uuid.UUID
    confidence_lower: float = Field(..., ge=0.0, le=1.0)
    confidence_upper: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _consistent(self) -> "SimilarityResultCreate":
        if self.submission_a_id == self.submission_b_id:
            raise ValueError("a result compares two different submissions")
        if self.confidence_lower > self.confidence_upper:
            raise ValueError("confidence_lower must not exceed confidence_upper")
        return self


class SimilarityResultResponse(SimilarityResultBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None  # NULL until the row is first updated


#: routes/results.py references ``result_schema.ResultResponse``, which did not
#: exist, so importing that route module raised AttributeError.
ResultResponse = SimilarityResultResponse


class ResultsResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    threshold_used: float = Field(..., ge=0.0, le=1.0)
    total_submissions: int = Field(..., ge=0)
    total_pairs: int = Field(..., ge=0)
    high_similarity_pairs: int = Field(..., ge=0)
    execution_time_ms: int = Field(..., ge=0)
    results: list[SimilarityResultResponse]
    metadata: dict[str, Any] = Field(default_factory=dict)
