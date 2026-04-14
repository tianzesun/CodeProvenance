"""
Enhanced Analysis API endpoints.

Provides REST API for submitting code for plagiarism analysis,
retrieving results, and managing webhook notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
import time
from datetime import datetime

from src.backend.config.database import get_db, set_tenant_context
from src.backend.models.database import Job, Submission, SimilarityResult
from src.backend.utils.database import JobService, SubmissionService, SimilarityResultService
from src.backend.api.schemas import job as job_schema
from src.backend.api.middleware.rate_limit import RateLimiter

router = APIRouter()

# Initialize rate limiter
rate_limiter = RateLimiter()


@router.post("/v1/analyze", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def analyze_submissions(
    request: Request,
    analysis_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Submit code for similarity analysis.
    
    This is the main endpoint for plagiarism detection. It accepts
    multiple code submissions and returns a job ID for tracking.
    
    **Request Body:**
    - `name`: Job name (required)
    - `submissions`: List of code submissions (required)
    - `threshold`: Similarity threshold 0.0-1.0 (default: 0.2)
    - `webhook_url`: URL for completion notification (optional)
    - `options`: Analysis options (optional)
    
    **Response:**
    - `job_id`: Unique identifier for the analysis job
    - `status`: Job status (pending, processing, completed)
    - `status_url`: URL to check job status
    - `estimated_completion`: Estimated completion time
    
    **Example Request:**
    ```json
    {
        "name": "CS101 Assignment 3",
        "submissions": [
            {
                "name": "student1_solution.py",
                "content": "def fibonacci(n): ..."
            },
            {
                "name": "student2_solution.py",
                "content": "def fib(n): ..."
            }
        ],
        "threshold": 0.2,
        "webhook_url": "https://example.com/webhook",
        "options": {
            "ai_detection": true,
            "normalize_whitespace": true,
            "strip_comments": false
        }
    }
    ```
    """
    start_time = time.time()
    
    # Extract tenant ID from API key
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    
    # Rate limit check
    rate_limiter.check_rate_limit(tenant_id, request)
    
    # Validate request
    if not analysis_data.get("submissions"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No submissions provided"
        )
    
    if len(analysis_data["submissions"]) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 submissions required for comparison"
        )
    
    # Set tenant context
    set_tenant_context(db, tenant_id)
    
    # Create analysis job
    job = JobService.create_job(
        db=db,
        tenant_id=tenant_id,
        name=analysis_data.get("name", "Unnamed Analysis"),
        threshold=analysis_data.get("threshold", 0.2),
        webhook_url=analysis_data.get("webhook_url"),
        options=analysis_data.get("options", {})
    )
    
    # Create submissions
    submission_ids = []
    for submission_data in analysis_data["submissions"]:
        submission = SubmissionService.create_submission(
            db=db,
            job_id=str(job.id),
            name=submission_data.get("name", "Untitled"),
            content=submission_data.get("content", ""),
            language=submission_data.get("language", "auto")
        )
        submission_ids.append(str(submission.id))
    
    # Calculate estimated completion time
    num_submissions = len(analysis_data["submissions"])
    estimated_seconds = num_submissions * 2  # Rough estimate: 2 seconds per submission
    estimated_completion = datetime.fromtimestamp(
        time.time() + estimated_seconds
    ).isoformat()
    
    # Queue background processing
    # background_tasks.add_task(process_analysis_job, str(job.id), tenant_id)
    
    # Log API call
    duration = time.time() - start_time
    # background_tasks.add_task(log_api_call, tenant_id, "/v1/analyze", duration, 201)
    
    return {
        "job_id": str(job.id),
        "status": "pending",
        "status_url": f"/api/v1/jobs/{job.id}",
        "estimated_completion": estimated_completion,
        "submission_count": num_submissions,
        "submission_ids": submission_ids,
        "message": f"Analysis job created with {num_submissions} submissions"
    }


@router.get("/v1/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_status(
    job_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get analysis job status and results.
    
    Returns the current status of an analysis job, including
    progress, results, and any errors that occurred.
    
    **Response:**
    - `job_id`: Job identifier
    - `name`: Job name
    - `status`: Current status (pending, processing, completed, failed)
    - `progress`: Percentage complete (0-100)
    - `submission_count`: Number of submissions
    - `completed_at`: Completion timestamp (if completed)
    - `error_message`: Error details (if failed)
    - `results`: List of similarity results (if completed)
    """
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    set_tenant_context(db, tenant_id)
    
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Get results if completed
    results = []
    if job.status == "completed":
        similarity_results = SimilarityResultService.get_results_by_job(
            db, str(job_id), threshold=None, limit=1000, offset=0
        )
        results = [
            {
                "id": str(r.id),
                "submission_a_id": str(r.submission_a_id),
                "submission_b_id": str(r.submission_b_id),
                "similarity_score": float(r.similarity_score),
                "confidence_lower": float(r.confidence_lower) if r.confidence_lower else None,
                "confidence_upper": float(r.confidence_upper) if r.confidence_upper else None,
                "detected_clones": r.detected_clones or []
            }
            for r in similarity_results
        ]
    
    return {
        "job_id": str(job.id),
        "name": job.name,
        "status": job.status,
        "progress": job.progress or 0,
        "submission_count": len(job.submissions) if hasattr(job, 'submissions') else 0,
        "threshold": float(job.threshold),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "results": results
    }


@router.get("/v1/jobs/{job_id}/results", response_model=List[Dict[str, Any]])
async def get_job_results(
    job_id: uuid.UUID,
    request: Request,
    threshold: Optional[float] = None,
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get detailed similarity results for an analysis job.
    
    Returns all pairwise similarity comparisons with scores,
    confidence intervals, and matching code blocks.
    
    **Query Parameters:**
    - `threshold`: Minimum similarity score (0.0-1.0)
    - `limit`: Maximum results to return (default: 1000)
    - `offset`: Pagination offset (default: 0)
    """
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    set_tenant_context(db, tenant_id)
    
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is not completed (status: {job.status})"
        )
    
    # Get results
    results = SimilarityResultService.get_results_by_job(
        db, str(job_id), threshold=threshold, limit=limit, offset=offset
    )
    
    # Format results
    formatted_results = []
    for r in results:
        formatted_results.append({
            "id": str(r.id),
            "submission_a": {
                "id": str(r.submission_a_id),
                "name": r.submission_a.name if hasattr(r, 'submission_a') else "Unknown"
            },
            "submission_b": {
                "id": str(r.submission_b_id),
                "name": r.submission_b.name if hasattr(r, 'submission_b') else "Unknown"
            },
            "similarity_score": float(r.similarity_score),
            "confidence_interval": {
                "lower": float(r.confidence_lower) if r.confidence_lower else 0.0,
                "upper": float(r.confidence_upper) if r.confidence_upper else 1.0,
                "confidence": 0.95
            },
            "detected_clones": r.detected_clones or [],
            "matching_blocks": r.matching_blocks or []
        })
    
    return formatted_results


@router.get("/v1/jobs/{job_id}/report", response_model=Dict[str, Any])
async def get_job_report(
    job_id: uuid.UUID,
    request: Request,
    format: str = "html",
    db: Session = Depends(get_db)
):
    """
    Generate a similarity analysis report.
    
    Generates a comprehensive report in the specified format
    (HTML, PDF, JSON) for the analysis job.
    
    **Query Parameters:**
    - `format`: Report format (html, pdf, json) - default: html
    
    **Response:**
    - `report_url`: URL to download the generated report
    - `format`: Report format
    - `generated_at`: Report generation timestamp
    """
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    set_tenant_context(db, tenant_id)
    
    job = JobService.get_job_by_id(db, str(job_id), tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is not completed (status: {job.status})"
        )
    
    # Generate report (placeholder - would integrate with report generator)
    report_url = f"/api/v1/jobs/{job_id}/report/download?format={format}"
    
    return {
        "job_id": str(job.id),
        "report_url": report_url,
        "format": format,
        "generated_at": datetime.now().isoformat(),
        "status": "ready"
    }


@router.get("/v1/usage", response_model=Dict[str, Any])
async def get_api_usage(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get API usage statistics for the current tenant.
    
    Returns usage metrics including jobs created, files analyzed,
    API calls made, and rate limit information.
    """
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    set_tenant_context(db, tenant_id)
    
    # Get usage metrics (placeholder)
    return {
        "tenant_id": tenant_id,
        "jobs_created": 0,
        "files_analyzed": 0,
        "api_calls": 0,
        "rate_limit": {
            "requests_per_minute": 60,
            "requests_remaining": 60,
            "reset_at": datetime.now().isoformat()
        }
    }