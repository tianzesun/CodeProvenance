"""
Pydantic schemas for similarity results API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class MatchingBlock(BaseModel):
    file_a: str
    file_b: str
    lines_a: str  # e.g., "10-50"
    lines_b: str  # e.g., "12-52"
    similarity: float = Field(..., ge=0.0, le=1.0)
    block_type: Optional[str] = None  # e.g., "function", "class", "code_block"
    function_name: Optional[str] = None
    token_overlap: Optional[float] = None
    ast_similarity: Optional[float] = None


class ExcludedMatch(BaseModel):
    reason: str  # e.g., "template_match", "boilerplate"
    description: str
    template_file: Optional[str] = None
    file_a: Optional[str] = None
    file_b: Optional[str] = None


class SimilarityResultBase(BaseModel):
    submission_a_id: uuid.UUID
    submission_b_id: uuid.UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    confidence_lower: float = Field(..., ge=0.0, le=1.0)
    confidence_upper: float = Field(..., ge=0.0, le=1.0)
    confidence_level: float = Field(0.95, ge=0.0, le=1.0)
    matching_blocks: List[MatchingBlock] = Field(default_factory=list)
    excluded_matches: List[ExcludedMatch] = Field(default_factory=list)
    algorithm_scores: Optional[Dict[str, float]] = None


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
    results: List[SimilarityResultResponse]
    metadata: Dict[str, Any] = Field(default_factory=dict)
