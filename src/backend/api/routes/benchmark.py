"""Benchmark API routes.

All heavyweight benchmark functionality extracted from server.py.  Shared
helpers and module-level state (REPORTS_DIR, BENCHMARK_DATA_DIR, _get_job,
_require_current_user, etc.) are imported lazily from server inside each
handler to avoid circular imports — the same pattern used by routes/analyze.py.
"""

from __future__ import annotations

import csv
import html
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from bisect import bisect_left
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limits and constants
# ---------------------------------------------------------------------------

_MAX_FPR_FILES = 200  # all-pairs comparison is O(n^2)
_MAX_FPR_FILE_BYTES = 1_000_000
_MAX_FPR_RUN_PAYLOAD_BYTES = 1_000_000
_MAX_BG_FILES = 500
_MAX_BG_FILE_BYTES = 5_000_000
_MAX_ACTIVE_BG_JOBS = 3
_BG_JOB_TTL_SECONDS = 3600
_LOW_SAMPLE_PAIRS = 30

_FPR_THRESHOLDS = (
    0.40, 0.45, 0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.64, 0.65,
    0.66, 0.67, 0.68, 0.69, 0.70, 0.71, 0.72, 0.73, 0.74, 0.75,
    0.76, 0.77, 0.78, 0.80, 0.82, 0.85, 0.88, 0.90, 0.95,
)  # fmt: skip

_LOCAL_EMBEDDING_RUNTIMES = ("local_unixcoder", "local", "unixcoder")
_ENV_LOCK = threading.Lock()
_FINISHED_JOB_STATES = {"done", "error"}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class FprValidationRunCreate(BaseModel):
    """Request body for saving an FPR validation run."""

    name: str | None = None
    result: dict[str, Any]
    notes: str | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _failure_ref(action: str) -> str:
    """Log the active exception and return a short reference id for the client."""
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s failed (ref=%s)", action, ref)
    return ref


def _server_error(action: str) -> HTTPException:
    """Generic 500 carrying a reference id; the details stay in the log.

    Call from inside an ``except`` block.
    """
    return HTTPException(
        status_code=500, detail=f"{action} failed. Reference: {_failure_ref(action)}"
    )


def _current_user(request: Request, *, admin_only: bool = False) -> dict[str, Any]:
    from src.backend.api.server import _require_current_user

    return _require_current_user(request, admin_only=admin_only)


def _tenant_id_or_400(user: dict[str, Any]) -> str:
    """Return the caller's tenant id.

    A missing tenant must be rejected: ``column == None`` compiles to
    ``IS NULL`` and would match (and let the caller read or delete) every
    legacy row that has no tenant.
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated with user")
    return tenant_id


def _validated_dataset_id(dataset: str | None) -> str:
    """Return a dataset id that is a single, safe path component.

    The id is joined onto the benchmark data directory, so anything that could
    climb out of it (``..``, separators, NUL) is rejected up front.
    """
    value = (dataset or "").strip()
    if not value:
        return ""
    if value in {".", ".."} or any(ch in value for ch in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="Invalid dataset id")
    return value


def _safe_filename_part(value: str) -> str:
    """Reduce an id to characters that are safe in a Content-Disposition name."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:64] or "download"


def _csv_safe(value: Any) -> str:
    """Neutralise spreadsheet formula injection in a CSV cell.

    File names come from uploads, so a name like ``=HYPERLINK(...)`` would run
    when an instructor opens the export in Excel.
    """
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


async def _json_object(request: Request) -> dict[str, Any]:
    """Parse the request body as a JSON object or raise 400."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=400, detail="Request body must be valid JSON"
        ) from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    return payload


def _accessible_job_or_404(
    request: Request, job_id: str, *, require_key: str | None = "pair_results"
) -> dict[str, Any]:
    """Load a job, enforcing authentication and the same access rules as /api/jobs.

    The download and radar routes previously returned any job's data to anyone
    who knew its id. Missing and inaccessible jobs both return 404.
    """
    from src.backend.api.server import _get_job, _job_is_accessible

    user = _current_user(request)
    job = _get_job(job_id)
    if not job or not _job_is_accessible(job, user):
        raise HTTPException(status_code=404, detail="Benchmark results not found")
    if require_key and require_key not in job:
        raise HTTPException(status_code=404, detail="Benchmark results not found")
    return job


async def _html_report_response(
    html_content: str, *, filename_base: str, fallback_title: str
) -> Response:
    """Render HTML to PDF (WeasyPrint) with graceful fallbacks.

    Falls back to the HTML itself when WeasyPrint is not installed, and to a
    minimal PDF when rendering fails.  Rendering runs in a worker thread
    because it is CPU-bound.
    """
    from src.backend.infrastructure.reporting.evidence_pdf_exporter import (
        _minimal_pdf_bytes,
    )

    try:
        import weasyprint
    except ImportError:
        return Response(
            content=html_content,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.html"},
        )
    try:
        pdf = await run_in_threadpool(
            lambda: weasyprint.HTML(string=html_content).write_pdf()
        )
    except Exception:
        logger.warning("PDF export fell back to minimal PDF: %s", filename_base, exc_info=True)
        pdf = _minimal_pdf_bytes(fallback_title)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"},
    )


# ---------------------------------------------------------------------------
# Demo dataset
# ---------------------------------------------------------------------------


@router.post("/api/admin/create-demo-dataset")
async def create_demo_dataset(request: Request):
    """Create a synthetic demo dataset for testing."""
    from src.backend.api.server import (
        BENCHMARK_DATA_DIR,
        _language_file_extension,
        apply_organization_transforms,
        apply_renaming_transforms,
        apply_semantic_transforms,
        apply_structural_transforms,
        apply_token_transforms,
        generate_synthetic_code,
    )

    # Writes into the shared benchmark data directory, so admin-only like the
    # route's /api/admin/ prefix says.
    current_user = _current_user(request, admin_only=True)
    data = await _json_object(request)

    dataset_name = str(data.get("name") or "").strip()[:100]
    description = str(data.get("description") or "").strip()[:1000]
    language = data.get("language", "python")
    similarity_type = str(data.get("similarityType") or "plagiarism")
    try:
        num_files = min(max(int(data.get("numFiles", 10)), 5), 100)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="numFiles must be an integer") from None
    if not dataset_name:
        raise HTTPException(status_code=400, detail="Dataset name is required")
    if language not in ("python", "java", "javascript", "cpp"):
        language = "python"

    # The name is user input and becomes part of a directory name: reduce it to
    # a slug so "../../x" cannot create directories outside the data dir.
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", dataset_name).strip("_")[:64] or "dataset"
    dataset_dir = BENCHMARK_DATA_DIR / f"demo_{slug}_{int(time.time())}"
    BENCHMARK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        dataset_dir.mkdir()
    except FileExistsError:
        raise HTTPException(
            status_code=409, detail="A dataset with this name was just created; retry"
        ) from None

    def transform(content: str) -> str:
        if similarity_type == "type1_exact":
            return content
        if similarity_type == "type2_renamed":
            return apply_renaming_transforms(content, language)
        if similarity_type == "type3_modified":
            return apply_structural_transforms(content, language)
        if similarity_type == "token_similarity":
            return apply_token_transforms(content, language)
        if similarity_type == "structural_similarity":
            return apply_organization_transforms(content, language)
        # type4_semantic and anything else. type4_semantic used to copy the
        # original unchanged, which made it identical to type1_exact.
        return apply_semantic_transforms(content, language)

    def write_dataset() -> None:
        original_dir = dataset_dir / "original"
        plagiarized_dir = dataset_dir / "plagiarized"
        original_dir.mkdir()
        plagiarized_dir.mkdir()
        extension = _language_file_extension(language)
        for i in range(num_files):
            filename = f"{i:02d}{extension}"
            content = generate_synthetic_code(i, language, similarity_type)
            (original_dir / filename).write_text(content, encoding="utf-8")
            (plagiarized_dir / filename).write_text(transform(content), encoding="utf-8")

    try:
        await run_in_threadpool(write_dataset)
        relative_path = str(dataset_dir.relative_to(BENCHMARK_DATA_DIR.parent))
        metadata = {
            "name": dataset_name,
            "description": description,
            "language": language,
            "files_created": num_files * 2,
            "original_files": num_files,
            "plagiarized_files": num_files,
            "similarity_type": similarity_type,
            "created_by": current_user.get("email"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_path": relative_path,
            "pairs": num_files,
        }
        (dataset_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(dataset_dir, ignore_errors=True)  # no half-built datasets
        raise _server_error("Demo dataset creation") from None

    return JSONResponse(
        status_code=201,
        content={
            "message": f"Demo dataset '{dataset_name}' created successfully",
            "dataset": metadata,
            "files_created": metadata["files_created"],
            # Relative only: the absolute server path is not the client's business.
            "dataset_path": relative_path,
        },
    )


# ---------------------------------------------------------------------------
# Benchmark tools
# ---------------------------------------------------------------------------


@router.get("/api/benchmark-tools")
async def get_benchmark_tools():
    """List available real benchmark tools."""
    from src.backend.api.server import REAL_BENCHMARK_TOOL_IDS, _list_benchmark_tools

    tools = [tool for tool in _list_benchmark_tools() if tool["id"] in REAL_BENCHMARK_TOOL_IDS]
    for tool in tools:
        tool["available"] = tool.get("runnable", False)
    return JSONResponse(content={"tools": tools})


# ---------------------------------------------------------------------------
# Real FPR computation
# ---------------------------------------------------------------------------


def _fpr_label(fpr: float) -> str:
    if fpr <= 0.015:
        return "Excellent – very safe"
    if fpr <= 0.03:
        return "Good – comfortable for most courses"
    if fpr <= 0.05:
        return "Acceptable – use with evidence review"
    if fpr <= 0.08:
        return "Borderline – caution recommended"
    return "High risk – too many false positives"


def _build_fpr_report(scores: list[float], num_submissions: int) -> dict[str, Any]:
    """Turn pairwise scores from a known-clean corpus into an FPR report."""
    num_pairs = len(scores)
    ordered = sorted(scores)

    fpr_table = []
    for t in _FPR_THRESHOLDS:
        above = num_pairs - bisect_left(ordered, t)  # scores >= t
        fpr = above / num_pairs if num_pairs else 0.0
        fpr_table.append(
            {
                "threshold": round(t, 2),
                "fpr": round(fpr, 4),
                "fpr_percent": round(fpr * 100, 2),
                "label": _fpr_label(fpr),
                "flagged_pairs": above,
            }
        )

    very_safe = next((row for row in fpr_table if row["fpr"] <= 0.015), None)
    balanced = next((row for row in fpr_table if row["fpr"] <= 0.03), None)
    high_recall = next((row for row in fpr_table if row["fpr"] <= 0.05), None)
    mean_clean = sum(scores) / num_pairs if num_pairs else 0.0
    max_clean = max(scores) if scores else 0.0

    recommendations = []
    if very_safe:
        recommendations.append(
            {
                "threshold": very_safe["threshold"],
                "fpr": very_safe["fpr_percent"],
                "type": "very_safe",
                "title": "Maximum Safety",
                "advice": (
                    f"At {very_safe['threshold'] * 100:.0f}% the FPR on your clean data is only "
                    f"{very_safe['fpr_percent']:.1f}%. This is the most conservative setting."
                ),
            }
        )
    if balanced:
        recommendations.append(
            {
                "threshold": balanced["threshold"],
                "fpr": balanced["fpr_percent"],
                "type": "balanced",
                "title": "Recommended Default",
                "advice": (
                    f"At {balanced['threshold'] * 100:.0f}% you get a good balance "
                    f"(FPR ≈ {balanced['fpr_percent']:.1f}%). Strong choice for most courses."
                ),
            }
        )
    if high_recall:
        recommendations.append(
            {
                "threshold": high_recall["threshold"],
                "fpr": high_recall["fpr_percent"],
                "type": "high_recall",
                "title": "Higher Detection (with review)",
                "advice": (
                    f"At {high_recall['threshold'] * 100:.0f}% you catch more cases "
                    f"(FPR ≈ {high_recall['fpr_percent']:.1f}%). Best used when every pair "
                    "is manually reviewed."
                ),
            }
        )

    if mean_clean > 0.25:
        overall_risk = (
            "Your clean corpus shows unusually high baseline similarity. "
            "Consider stronger starter-code / template filtering."
        )
    elif max_clean > 0.65:
        overall_risk = (
            "Some very similar clean pairs exist. Review the highest-scoring clean pairs."
        )
    else:
        overall_risk = (
            "Your clean data looks healthy. The system behaves as expected on non-plagiarized work."
        )

    suggested_actions = []
    if not very_safe or very_safe["fpr"] > 0.02:
        suggested_actions.append("Raise the default decision threshold by 5–8 percentage points.")
    if mean_clean > 0.20:
        suggested_actions.append("Enable or improve starter-code / boilerplate suppression.")
    if max_clean > 0.70:
        suggested_actions.append(
            "Manually review the top 5–10 clean pairs with the highest scores."
        )
    if not suggested_actions:
        suggested_actions.append(
            "Current settings appear well calibrated for your student population."
        )

    best = balanced or very_safe or fpr_table[-1]
    recommendation = (
        f"Recommended starting threshold: {best['threshold'] * 100:.0f}% "
        f"(FPR on your clean data ≈ {best['fpr_percent']:.1f}%). {overall_risk}"
    )

    bins = [0] * 10
    for s in scores:
        bins[max(0, min(int(s * 10), 9))] += 1
    histogram = [{"bin": f"{i / 10:.1f}-{(i + 1) / 10:.1f}", "count": bins[i]} for i in range(10)]

    return {
        "num_submissions": num_submissions,
        "num_pairs": num_pairs,
        "fpr_table": fpr_table,
        "score_histogram": histogram,
        "recommendation": recommendation,
        "mean_score": round(mean_clean, 4),
        "max_score": round(max_clean, 4),
        "recommendations": recommendations,
        "overall_assessment": overall_risk,
        "suggested_actions": suggested_actions,
        "recommended_threshold": best["threshold"],
        # ``fpr`` in the table is already a fraction. This used to be divided by
        # 100 again, so the stored value was 100x too small.
        "fpr_at_recommended_threshold": best["fpr"],
        "low_sample_warning": (
            f"Only {num_pairs} pairs were compared; FPR estimates need at least "
            f"{_LOW_SAMPLE_PAIRS} pairs to be meaningful."
            if num_pairs < _LOW_SAMPLE_PAIRS
            else None
        ),
    }


@router.post("/api/benchmark/real-fpr")
async def compute_real_fpr_on_clean_corpus(
    files: list[UploadFile] = File(...),
):
    """Compute real False Positive Rate on a set of known-clean submissions."""
    from src.backend.application.services.batch_detection_service import BatchDetectionService

    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 submissions are required to compute FPR.",
        )
    if len(files) > _MAX_FPR_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"At most {_MAX_FPR_FILES} submissions can be compared at once.",
        )

    submissions: dict[str, str] = {}
    for upload in files:
        name = upload.filename
        if not name:
            continue
        try:
            raw = await upload.read(_MAX_FPR_FILE_BYTES + 1)
        except Exception:
            logger.debug("Skipping unreadable submission", exc_info=True)
            continue
        if len(raw) > _MAX_FPR_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Each file must be at most {_MAX_FPR_FILE_BYTES // 1000} KB.",
            )
        content = raw.decode("utf-8", errors="ignore")
        if len(content.strip()) > 30:
            key, n = name, 1
            while key in submissions:  # same filename twice must not overwrite
                n += 1
                key = f"{name} ({n})"
            submissions[key] = content
    if len(submissions) < 2:
        raise HTTPException(status_code=400, detail="Could not load enough valid submissions.")

    def compute_scores() -> list[float]:
        service = BatchDetectionService(threshold=0.0)
        return [float(r.score) for r in service.compare_all_pairs(submissions)]

    try:
        scores = await run_in_threadpool(compute_scores)  # CPU-bound, off the event loop
    except Exception:
        raise _server_error("FPR computation") from None

    return JSONResponse(content=_build_fpr_report(scores, len(submissions)))


# ---------------------------------------------------------------------------
# FPR validation run history (database-backed)
# ---------------------------------------------------------------------------


@router.post("/api/fpr-validation-runs")
async def save_fpr_validation_run(request: Request, payload: FprValidationRunCreate):
    """Save a completed FPR validation run to the database."""
    from src.backend.api.server import SessionLocal
    from src.backend.models.database import FprValidationRun

    current_user = _current_user(request)
    tenant_id = _tenant_id_or_400(current_user)
    result_data = payload.result
    if len(json.dumps(result_data, default=str)) > _MAX_FPR_RUN_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Validation run is too large to store")

    name = payload.name or f"FPR Run - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
    try:
        run = FprValidationRun(
            tenant_id=tenant_id,
            user_id=current_user.get("id"),
            name=name,
            payload=result_data,
            num_submissions=result_data.get("num_submissions"),
            num_pairs=result_data.get("num_pairs"),
            mean_score=result_data.get("mean_score"),
            max_score=result_data.get("max_score"),
            recommended_threshold=result_data.get("recommended_threshold"),
            fpr_at_recommended_threshold=result_data.get("fpr_at_recommended_threshold"),
            notes=payload.notes,
            status="completed",
        )
        with SessionLocal() as db:
            db.add(run)
            db.commit()
            db.refresh(run)
        return {"id": run.id, "name": run.name, "created_at": run.created_at}
    except Exception:
        raise _server_error("Saving the FPR validation run") from None


@router.get("/api/fpr-validation-runs")
async def list_fpr_validation_runs(request: Request, limit: int = Query(50, ge=1, le=200)):
    """List historical FPR validation runs for the current tenant."""
    from src.backend.api.server import SessionLocal
    from src.backend.models.database import FprValidationRun

    tenant_id = _tenant_id_or_400(_current_user(request))
    try:
        with SessionLocal() as db:
            runs = (
                db.query(FprValidationRun)
                .filter(FprValidationRun.tenant_id == tenant_id)
                .order_by(FprValidationRun.created_at.desc())
                .limit(limit)
                .all()
            )
            return {
                "runs": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "created_at": r.created_at,
                        "num_submissions": r.num_submissions,
                        "num_pairs": r.num_pairs,
                        "recommended_threshold": r.recommended_threshold,
                        "fpr_at_recommended_threshold": r.fpr_at_recommended_threshold,
                        "is_certified": r.is_certified,
                        "status": r.status,
                    }
                    for r in runs
                ]
            }
    except Exception:
        raise _server_error("Listing FPR validation runs") from None


@router.get("/api/fpr-validation-runs/{run_id}")
async def get_fpr_validation_run(run_id: str, request: Request):
    """Retrieve a single saved FPR validation run."""
    from src.backend.api.server import SessionLocal
    from src.backend.models.database import FprValidationRun

    tenant_id = _tenant_id_or_400(_current_user(request))
    try:
        with SessionLocal() as db:
            run = (
                db.query(FprValidationRun)
                .filter(
                    FprValidationRun.id == run_id,
                    FprValidationRun.tenant_id == tenant_id,
                )
                .first()
            )
            if not run:
                raise HTTPException(status_code=404, detail="FPR validation run not found")
            return {
                "id": run.id,
                "name": run.name,
                "created_at": run.created_at,
                "notes": run.notes,
                "is_certified": run.is_certified,
                "certified_at": run.certified_at,
                "result": run.payload,
            }
    except HTTPException:
        raise
    except Exception:
        raise _server_error("Fetching the FPR validation run") from None


@router.delete("/api/fpr-validation-runs/{run_id}")
async def delete_fpr_validation_run(run_id: str, request: Request):
    """Delete a saved FPR validation run (certified runs are kept as evidence)."""
    from src.backend.api.server import SessionLocal
    from src.backend.models.database import FprValidationRun

    tenant_id = _tenant_id_or_400(_current_user(request))
    try:
        with SessionLocal() as db:
            run = (
                db.query(FprValidationRun)
                .filter(
                    FprValidationRun.id == run_id,
                    FprValidationRun.tenant_id == tenant_id,
                )
                .first()
            )
            if not run:
                raise HTTPException(status_code=404, detail="FPR validation run not found")
            if run.is_certified:
                raise HTTPException(
                    status_code=409, detail="Certified validation runs cannot be deleted"
                )
            db.delete(run)
            db.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        raise _server_error("Deleting the FPR validation run") from None


# ---------------------------------------------------------------------------
# Benchmark presets and history
# ---------------------------------------------------------------------------


@router.get("/api/benchmark-presets")
async def get_benchmark_presets() -> dict[str, Any]:
    """Return repeatable benchmark workflows for product optimization."""
    from src.backend.api.server import (
        BENCHMARK_WORKFLOW_PRESETS,
        BUILTIN_PAIR_DATASET_IDS,
        REAL_BENCHMARK_TOOL_IDS,
        _builtin_pair_dataset_path,
        _iter_benchmark_dataset_roots,
        _list_benchmark_tools,
    )

    available_tools = {
        tool["id"]: tool
        for tool in _list_benchmark_tools()
        if tool["id"] in REAL_BENCHMARK_TOOL_IDS
    }
    datasets = {item.name for item in _iter_benchmark_dataset_roots()}
    datasets.update(
        dataset_id
        for dataset_id in BUILTIN_PAIR_DATASET_IDS
        if _builtin_pair_dataset_path(dataset_id).exists()
    )
    presets = []
    for preset in BENCHMARK_WORKFLOW_PRESETS:
        runnable_tools = [
            tool_id
            for tool_id in preset["tools"]
            if available_tools.get(tool_id, {}).get("runnable")
        ]
        blocked_tools = [
            {
                "id": tool_id,
                "status": available_tools.get(tool_id, {}).get("status", "Not installed"),
            }
            for tool_id in preset["tools"]
            if tool_id not in runnable_tools
        ]
        presets.append(
            {
                **preset,
                "runnable_tools": runnable_tools,
                "blocked_tools": blocked_tools,
                "dataset_ready": preset["dataset"] in datasets,
            }
        )
    return {"presets": presets}


@router.get("/api/benchmark-history")
async def get_benchmark_history(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    """Return recent benchmark run summaries (file + DB)."""
    from src.backend.api.server import SessionLocal, _read_benchmark_history
    from src.backend.models.database import Job

    runs = _read_benchmark_history()[:limit]
    try:
        with SessionLocal() as db:
            db_benchmarks = (
                db.query(Job)
                .filter(Job.settings.op("->>")("type") == "benchmark")
                .order_by(Job.created_at.desc())
                .limit(limit)
                .all()
            )
            for j in db_benchmarks:
                s = (j.settings or {}).get("summary") or {}
                if s and not any(r.get("job_id") == j.id for r in runs):
                    runs.append(s)
    except Exception:
        logger.warning("Failed to load benchmark runs from DB", exc_info=True)
    return {"runs": runs[:limit]}


# ---------------------------------------------------------------------------
# Error analysis
# ---------------------------------------------------------------------------


@router.get("/api/error-analysis")
async def get_error_analysis() -> dict[str, Any]:
    """Compute real error analysis from stored benchmark runs and job results."""
    from src.backend.api.server import (
        BENCHMARK_RUNS_DIR,
        _build_error_analysis_from_benchmark,
        _build_error_analysis_from_jobs,
    )

    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:  # deleted between glob and stat
            return 0.0

    benchmark_runs = sorted(BENCHMARK_RUNS_DIR.glob("*.json"), key=mtime, reverse=True)
    labeled_run: dict[str, Any] | None = None
    for run_path in benchmark_runs[:10]:
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
            if run.get("has_ground_truth") and run.get("pair_results"):
                labeled_run = run
                break
        except Exception:
            logger.debug("Failed to load labeled run", exc_info=True)
    if labeled_run:
        return _build_error_analysis_from_benchmark(labeled_run)
    return _build_error_analysis_from_jobs()


# ---------------------------------------------------------------------------
# Benchmark datasets
# ---------------------------------------------------------------------------


@router.get("/api/benchmark-datasets")
async def get_benchmark_datasets() -> dict[str, Any]:
    """Get available benchmark datasets by scanning the data/datasets/ directory."""
    from src.backend.api.server import (
        BUILTIN_PAIR_DATASET_IDS,
        _build_benchmark_dataset_readiness,
        _build_benchmark_quality_certificate,
        _dataset_default_language,
        _dataset_has_pair_ground_truth,  # type: ignore[attr-defined]
        _infer_dataset_language,
        _infer_dataset_size_label,
        _iter_benchmark_dataset_roots,
        _load_builtin_pair_dataset_metadata,
        _load_dataset_metadata,
        _read_json_file,
        _resolve_benchmark_dataset_dir,
        _resolve_benchmark_dataset_root,
    )

    dataset_icons: dict[str, str] = {
        "demo": "🧪",
        "poj104": "📚",
        "codesearchnet": "🐍",
        "codexglue": "☕",
        "google": "🏆",
        "bigclone": "🔄",
        "kaggle": "📊",
        "synthetic": "⚙️",
        "ieee": "🎓",
        "oscar": "🎭",
        "xiangtan": "🏫",
    }
    dataset_colors: dict[str, str] = {
        "demo": "purple",
        "poj104": "blue",
        "codesearchnet": "green",
        "codexglue": "amber",
        "google": "emerald",
        "bigclone": "cyan",
        "kaggle": "indigo",
        "synthetic": "gray",
        "ieee": "rose",
        "oscar": "fuchsia",
        "xiangtan": "sky",
    }
    datasets: list[dict[str, Any]] = []
    for item in _iter_benchmark_dataset_roots():
        dataset_id = item.name
        metadata = _load_dataset_metadata(item)
        if metadata.get("exclude_from_benchmark"):
            continue
        readiness = _build_benchmark_dataset_readiness(dataset_id, item)
        if not readiness.get("runnable"):
            logger.debug("Hiding benchmark dataset %s: %s", dataset_id, readiness.get("reason"))
            continue
        is_demo = dataset_id.startswith("demo_")
        dataset_dir = _resolve_benchmark_dataset_dir(dataset_id) or item
        dataset_info: dict[str, Any] = {}
        if not is_demo and dataset_dir.name in {"train", "test", "validation"}:
            dataset_info = _read_json_file(dataset_dir / "dataset_info.json")
        icon = dataset_icons.get("demo" if is_demo else "synthetic", "📦")
        color = dataset_colors.get("demo" if is_demo else "gray", "slate")
        for key, dataset_icon in dataset_icons.items():
            if key in dataset_id.lower():
                icon = dataset_icon
                color = dataset_colors.get(key, "slate")
                break
        record: dict[str, Any] = {
            "id": dataset_id,
            "name": metadata.get("name", dataset_id.replace("_", " ").title()),
            "desc": metadata.get("description", f"Dataset: {dataset_id}"),
            "icon": icon,
            "color": color,
            "language": _infer_dataset_language(
                dataset_id, metadata, dataset_info, dataset_dir=dataset_dir
            ),
            "size": _infer_dataset_size_label(dataset_dir, metadata, dataset_info, is_demo),
            "created_by": metadata.get("created_by", "System"),
            "created_at": metadata.get("created", metadata.get("created_at", "")),
            "is_demo": is_demo,
            "has_ground_truth": bool(readiness.get("runnable")),
            "benchmark_availability": readiness,
        }
        benchmark_quality = _build_benchmark_quality_certificate(item)
        if benchmark_quality:
            record["benchmark_quality"] = benchmark_quality
        if is_demo:
            record["files_created"] = metadata.get("files_created", 0)
            record["similarity_type"] = metadata.get("similarity_type", "unknown")
        datasets.append(record)

    present_ids = {d["id"] for d in datasets}
    for dataset_id in sorted(BUILTIN_PAIR_DATASET_IDS - present_ids):
        metadata = _load_builtin_pair_dataset_metadata(dataset_id)
        if not metadata:
            continue
        dataset_root = _resolve_benchmark_dataset_root(dataset_id)
        readiness = _build_benchmark_dataset_readiness(dataset_id, dataset_root)
        benchmark_quality = _build_benchmark_quality_certificate(dataset_root)
        record = {
            "id": dataset_id,
            "name": metadata.get("name", dataset_id.replace("_", " ").title()),
            "desc": metadata.get("description", f"Dataset: {dataset_id}"),
            "icon": dataset_icons.get("synthetic", "📦"),
            "color": dataset_colors.get("synthetic", "slate"),
            "language": metadata.get("language", _dataset_default_language(dataset_id)),
            "size": metadata.get(
                "size",
                (
                    f"{benchmark_quality.get('pair_count', 0):,} labeled pairs"
                    if benchmark_quality
                    else "Built-in benchmark"
                ),
            ),
            "created_by": metadata.get("created_by", "System"),
            "created_at": metadata.get("created", metadata.get("created_at", "")),
            "is_demo": False,
            "has_ground_truth": _dataset_has_pair_ground_truth(dataset_id, dataset_root),
            "benchmark_availability": readiness,
        }
        if benchmark_quality:
            record["benchmark_quality"] = benchmark_quality
        datasets.append(record)

    return JSONResponse(content={"datasets": datasets})


# ---------------------------------------------------------------------------
# Main benchmark run
# ---------------------------------------------------------------------------


@contextmanager
def _embedding_runtime_guard(configured_runtime: str):
    """Disable the local embedding model when there is no GPU, then restore it.

    ``EMBEDDING_RUNTIME`` is process-wide. The old code restored it only when
    the comparison succeeded, so one failing benchmark left embeddings switched
    off for the whole server. It is now always restored, and a lock stops
    concurrent benchmarks from clobbering each other's value.

    Must be used from a worker thread, not held across an ``await``.
    """
    disable = False
    if configured_runtime in _LOCAL_EMBEDDING_RUNTIMES:
        try:
            import torch

            disable = not torch.cuda.is_available()
        except ImportError:
            disable = True
    if not disable:
        yield
        return
    with _ENV_LOCK:
        original = os.environ.get("EMBEDDING_RUNTIME")
        os.environ["EMBEDDING_RUNTIME"] = "none"
        try:
            yield
        finally:
            if original is None:
                os.environ.pop("EMBEDDING_RUNTIME", None)
            else:
                os.environ["EMBEDDING_RUNTIME"] = original


async def _run_benchmark_job(
    job_id: str,
    job_dir: Path,
    files: list[UploadFile],
    tools: list[str],
    dataset: str,
    benchmark_type: str,
    preset_id: str,
) -> JSONResponse:
    """Body of ``run_benchmark``; the caller owns cleanup of ``job_dir``."""
    from src.backend.api.server import (
        BENCHMARK_DATA_DIR,
        BENCHMARK_WORKFLOW_PRESETS,
        REAL_BENCHMARK_TOOL_IDS,
        _build_benchmark_quality_certificate,
        _build_regression_quality_gates,
        _compute_engine_contribution,
        _compute_evaluation_metrics,
        _dataset_has_pair_ground_truth,
        _get_ground_truth_basis,
        _get_ground_truth_labels,
        _get_setting_secret,
        _load_benchmark_dataset,
        _load_pair_labeled_benchmark_dataset,
        _normalize_benchmark_protocol,
        _persist_benchmark_response,
        _select_reliable_explicit_pairs,
        _store_benchmark_uploads,
        settings,
    )
    from src.backend.application.services.batch_detection_service import BatchDetectionService
    from src.backend.benchmark.runners.external_tool_runner import ExternalToolRunner

    selected_tools: list[str] = []
    for tool in tools:
        tool_id = str(tool).strip().lower()
        if tool_id in REAL_BENCHMARK_TOOL_IDS and tool_id not in selected_tools:
            selected_tools.append(tool_id)
    tools = selected_tools or ["integritydesk"]

    logger.info("[BENCHMARK %s] Starting benchmark job", job_id)
    logger.info("[BENCHMARK %s] Requested tools: %s", job_id, ", ".join(tools))
    logger.info("[BENCHMARK %s] Dataset: %s", job_id, dataset or "custom upload")

    normalized_protocol = _normalize_benchmark_protocol(benchmark_type)
    benchmark_type = normalized_protocol["benchmark_type"]
    protocol = normalized_protocol["protocol"]
    threshold_policy = normalized_protocol["threshold_policy"]
    optimization_objective = normalized_protocol["optimization_objective"]
    report_type = normalized_protocol["report_type"]

    if benchmark_type in {"pan_optimization", "regression_test"}:
        dataset_root = BENCHMARK_DATA_DIR / dataset if dataset else None
        has_labeled_ground_truth = bool(
            dataset
            and dataset != "custom"
            and dataset_root
            and _dataset_has_pair_ground_truth(dataset, dataset_root)
        )
        if not has_labeled_ground_truth:
            return JSONResponse(
                status_code=400,
                content={
                    "error": (
                        "PAN metrics require labeled ground truth. Select a labeled "
                        "demo/synthetic original-vs-plagiarized dataset or a PAN-style "
                        "dataset with labels."
                    )
                },
            )

    submissions: dict[str, str] = {}
    explicit_pairs: list[dict[str, Any]] = []
    pair_sampling_audit: dict[str, Any] = {}

    if dataset and dataset != "custom":
        submissions, explicit_pairs = _load_pair_labeled_benchmark_dataset(dataset, job_dir)
        if explicit_pairs:
            explicit_pairs, pair_sampling_audit = _select_reliable_explicit_pairs(
                dataset, explicit_pairs
            )
            selected_files = {str(p.get("file_a", "")) for p in explicit_pairs} | {
                str(p.get("file_b", "")) for p in explicit_pairs
            }
            submissions = {k: v for k, v in submissions.items() if k in selected_files}
        if not submissions:
            submissions = _load_benchmark_dataset(dataset, job_dir)
    else:
        submissions = await _store_benchmark_uploads(files, job_dir)

    logger.info("[BENCHMARK %s] Loaded %d submissions", job_id, len(submissions))

    if len(submissions) < 2:
        return JSONResponse(status_code=400, content={"error": "At least 2 code files required"})

    if explicit_pairs:
        all_pairs = [
            (str(p["file_a"]), str(p["file_b"]))
            for p in explicit_pairs
            if p.get("file_a") in submissions and p.get("file_b") in submissions
        ]
    else:
        file_list = list(submissions.keys())
        all_pairs = [
            (file_list[i], file_list[j])
            for i in range(len(file_list))
            for j in range(i + 1, len(file_list))
        ]

    tool_results: dict[str, Any] = {}
    tool_timings: dict[str, float] = {}

    if "integritydesk" in tools:
        tool_started = time.perf_counter()

        def run_integritydesk() -> list[Any]:
            with _embedding_runtime_guard(settings.EMBEDDING_RUNTIME):
                service = BatchDetectionService(threshold=0.3)
                if explicit_pairs:
                    return service.compare_pairs(submissions, explicit_pairs)
                return service.compare_all_pairs(submissions)

        try:
            results = await run_in_threadpool(run_integritydesk)
            tool_results["integritydesk"] = {
                "pairs": [
                    {
                        "file_a": r.file_a,
                        "file_b": r.file_b,
                        "score": round(r.score, 3),
                        "features": {k: round(v, 3) for k, v in r.features.items()},
                        "contributions": {k: round(v, 3) for k, v in r.contributions.items()},
                    }
                    for r in results
                ]
            }
        except Exception:
            # The raw exception text used to be returned to the client.
            ref = _failure_ref("IntegrityDesk benchmark")
            tool_results["integritydesk"] = {"error": f"Benchmark run failed. Reference: {ref}"}
        finally:
            tool_timings["integritydesk"] = time.perf_counter() - tool_started

    external_tool_runner = ExternalToolRunner(moss_user_id=_get_setting_secret("moss_user_id"))
    for tool in tools:
        if tool == "integritydesk":
            continue
        tool_started = time.perf_counter()
        try:
            score_data = await run_in_threadpool(
                external_tool_runner.run_tool, tool, submissions, all_pairs
            )
            tool_results[tool] = score_data if score_data else {"error": f"{tool} not available"}
        except Exception:
            ref = _failure_ref(f"{tool} benchmark")
            tool_results[tool] = {"error": f"Benchmark run failed. Reference: {ref}"}
        finally:
            tool_timings[tool] = time.perf_counter() - tool_started

    explicit_pair_labels = {
        frozenset((str(p.get("file_a", "")), str(p.get("file_b", "")))): int(p.get("label", 0))
        for p in explicit_pairs
    }

    # Index each tool's pairs once. Matching by scanning every tool pair for
    # every candidate pair was O(pairs^2): ~400M comparisons for 200 files.
    tool_pair_index: dict[str, dict[frozenset[str], dict[str, Any]]] = {
        tool_name: {
            frozenset((p["file_a"], p["file_b"])): p for p in tool_data["pairs"]
        }
        for tool_name, tool_data in tool_results.items()
        if "pairs" in tool_data
    }

    pair_results = []
    for fa, fb in all_pairs:
        entry: dict[str, Any] = {
            "file_a": fa,
            "file_b": fb,
            "label": f"{Path(fa).stem} vs {Path(fb).stem}",
            "tool_results": [],
        }
        label_key = frozenset((fa, fb))
        if label_key in explicit_pair_labels:
            entry["ground_truth_label"] = explicit_pair_labels[label_key]
        for tool_name, index in tool_pair_index.items():
            p = index.get(label_key)
            if p is not None:
                entry["tool_results"].append(
                    {
                        "tool": tool_name,
                        "score": p["score"],
                        "features": p.get("features", {}),
                        "contributions": p.get("contributions", {}),
                    }
                )
        pair_results.append(entry)

    ground_truth_labels = _get_ground_truth_labels(dataset, pair_results)
    evaluation_results: dict[str, Any] = {}
    if ground_truth_labels:
        for tool_name, tool_data in tool_results.items():
            if "pairs" not in tool_data:
                continue
            scores: list[float] = []
            labels: list[int] = []
            # Score and label are appended together, so the two lists can no
            # longer drift out of alignment when labels are shorter than pairs.
            for idx, entry in enumerate(pair_results[: len(ground_truth_labels)]):
                for tr in entry["tool_results"]:
                    if tr["tool"] == tool_name:
                        scores.append(tr["score"])
                        labels.append(ground_truth_labels[idx])
                        break
            if scores and labels:
                evaluation_results[tool_name] = _compute_evaluation_metrics(
                    scores,
                    labels,
                    tool_name,
                    dataset or "custom",
                    tool_timings.get(tool_name, 0.0),
                    _compute_engine_contribution(tool_data.get("pairs", [])),
                    threshold_strategy=(
                        "fixed_threshold"
                        if benchmark_type == "regression_test"
                        else "calibration_holdout"
                    ),
                )

    id_pairs = tool_results.get("integritydesk", {}).get("pairs", [])
    id_avg = sum(p["score"] for p in id_pairs) / max(1, len(id_pairs))
    comp_scores_all = [
        p["score"]
        for t, d in tool_results.items()
        if t != "integritydesk" and "pairs" in d
        for p in d["pairs"]
    ]
    comp_avg = sum(comp_scores_all) / len(comp_scores_all) if comp_scores_all else 0
    benchmark_quality = (
        _build_benchmark_quality_certificate(BENCHMARK_DATA_DIR / dataset)
        if dataset and dataset != "custom"
        else None
    )

    response: dict[str, Any] = {
        "job_id": job_id,
        "preset_id": preset_id,
        "preset_name": next((p["name"] for p in BENCHMARK_WORKFLOW_PRESETS if p["id"] == preset_id), ""),
        "requested_tools": tools,
        "tool_scores": {
            k: {
                "pairs": len(v.get("pairs", [])),
                "error": v.get("error"),
                "score_source": (
                    "built_in_integritydesk"
                    if k == "integritydesk"
                    else ("real_cli" if "error" not in v else "unavailable")
                ),
                "runtime_seconds": round(tool_timings.get(k, 0.0), 4),
                "avg_runtime_seconds": round(
                    tool_timings.get(k, 0.0) / max(1, len(v.get("pairs", []))), 6
                ),
            }
            for k, v in tool_results.items()
        },
        "pair_results": pair_results,
        "summary": {
            "pairs_tested": len(pair_results),
            "tools_compared": len([t for t in tool_results if "error" not in tool_results[t]]),
            "accuracy": {
                "integritydesk": round(id_avg, 4),
                "best_competitor": round(comp_avg, 4),
            },
            "accuracy_basis": "mean_similarity_score_not_classification_accuracy",
            "score_summary": {
                "integritydesk_mean_similarity": round(id_avg, 4),
                "competitor_mean_similarity": round(comp_avg, 4),
            },
            "dataset_name": dataset or "custom",
            "dataset_size": len(submissions),
            "positive_pairs": int(sum(1 for lbl in ground_truth_labels if lbl >= 2)),
            "negative_pairs": int(sum(1 for lbl in ground_truth_labels if lbl < 2)),
            "optimization_trials": 17,
            "cross_validation_folds": 1,
            "optimization_method": (
                "Threshold sweep over 17 cutoffs, maximizing F1; "
                "PlagDet reported as primary PAN score"
            ),
        },
        "benchmark_type": benchmark_type,
        "protocol": protocol,
        "threshold_policy": threshold_policy,
        "optimization_objective": optimization_objective,
        "report_type": report_type,
        "benchmark_goal": (
            "admin_pan_optimization"
            if benchmark_type == "pan_optimization"
            else (
                "locked_regression_test"
                if benchmark_type == "regression_test"
                else "professor_tool_comparison"
            )
        ),
        "has_ground_truth": bool(ground_truth_labels),
    }
    if pair_sampling_audit:
        response["pair_sampling_audit"] = pair_sampling_audit
    if benchmark_quality:
        response["benchmark_quality"] = benchmark_quality
    if evaluation_results:
        response["evaluation"] = evaluation_results
        response["ground_truth_basis"] = _get_ground_truth_basis(dataset)
        response["benchmark_trust"] = (
            evaluation_results.get("integritydesk") or next(iter(evaluation_results.values()), {})
        ).get("benchmark_trust", {})
        if benchmark_type == "regression_test":
            response["quality_gates"] = _build_regression_quality_gates(
                evaluation_results.get("integritydesk") or {}
            )
    response = _persist_benchmark_response(response)
    return JSONResponse(content=response)


@router.post("/api/benchmark")
async def run_benchmark(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    tools: list[str] = Form(default=[]),
    dataset: str = Form(default=""),
    benchmark_type: str = Form(default="tool_comparison"),
    preset_id: str = Form(default=""),
):
    """Run a full benchmark comparison."""
    from src.backend.api.server import UPLOADS_DIR

    dataset = _validated_dataset_id(dataset)
    job_id = str(uuid.uuid4())
    job_dir = UPLOADS_DIR / f"bench_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        return await _run_benchmark_job(
            job_id, job_dir, files, tools, dataset, benchmark_type, preset_id
        )
    finally:
        # Previously only the happy path and two early returns cleaned up, so
        # any exception left the uploaded student code on disk.
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/api/benchmark/stream")
async def stream_benchmark(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    tools: list[str] = Form(default=[]),
    dataset: str = Form(default=""),
    benchmark_type: str = Form(default="tool_comparison"),
    preset_id: str = Form(default=""),
):
    """Delegate to the real benchmark endpoint (streaming was replaced with direct JSON)."""
    return await run_benchmark(
        request=request,
        files=files,
        tools=tools,
        dataset=dataset,
        benchmark_type=benchmark_type,
        preset_id=preset_id,
    )


# ---------------------------------------------------------------------------
# Background benchmark jobs
# ---------------------------------------------------------------------------

# The job store (BENCHMARK_JOBS / BENCHMARK_JOBS_LOCK) lives in server and is
# shared with server._run_benchmark_background; it is imported lazily to avoid
# a circular import at module load time.


def _benchmark_job_set(job_id: str, updates: dict[str, Any]) -> None:
    """Thread-safe update of a background benchmark job's state dict.

    The previous version referenced BENCHMARK_JOBS and BENCHMARK_JOBS_LOCK as
    module globals that were never defined here, so any call raised NameError.
    """
    from src.backend.api.server import BENCHMARK_JOBS, BENCHMARK_JOBS_LOCK

    with BENCHMARK_JOBS_LOCK:
        BENCHMARK_JOBS.setdefault(job_id, {}).update(updates)


@router.post("/api/benchmark/start")
async def start_benchmark_job(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    tools: list[str] = Form(default=[]),
    dataset: str = Form(default=""),
    benchmark_type: str = Form(default="tool_comparison"),
    preset_id: str = Form(default=""),
):
    """Start a benchmark in the background and return a job_id immediately."""
    from src.backend.api.server import (
        BENCHMARK_JOBS,
        BENCHMARK_JOBS_LOCK,
        _run_benchmark_background,
    )

    user = _current_user(request)
    dataset = _validated_dataset_id(dataset)
    if len(files) > _MAX_BG_FILES:
        raise HTTPException(status_code=400, detail=f"At most {_MAX_BG_FILES} files allowed")

    file_bytes: list[tuple[str, bytes]] = []
    for f in files:
        if f.filename:
            content = await f.read(_MAX_BG_FILE_BYTES + 1)
            if len(content) > _MAX_BG_FILE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Each file must be at most {_MAX_BG_FILE_BYTES // 1_000_000} MB",
                )
            file_bytes.append((f.filename, content))

    job_id = str(uuid.uuid4())
    now = time.time()
    with BENCHMARK_JOBS_LOCK:
        # The store never shrank, and any caller could start unlimited threads.
        for jid in [
            jid
            for jid, j in BENCHMARK_JOBS.items()
            if j.get("status") in _FINISHED_JOB_STATES
            and j.get("created_at") is not None
            and now - j["created_at"] > _BG_JOB_TTL_SECONDS
        ]:
            del BENCHMARK_JOBS[jid]
        active = sum(1 for j in BENCHMARK_JOBS.values() if j.get("status") not in _FINISHED_JOB_STATES)
        if active >= _MAX_ACTIVE_BG_JOBS:
            raise HTTPException(
                status_code=429,
                detail="Too many benchmarks are running. Try again when one finishes.",
            )
        BENCHMARK_JOBS[job_id] = {
            "status": "queued",
            "progress": [],
            "owner_id": str(user.get("id")),
            "created_at": now,
        }

    threading.Thread(
        target=_run_benchmark_background,
        args=(job_id, list(tools), dataset, benchmark_type, preset_id, file_bytes),
        daemon=True,
    ).start()
    return JSONResponse(content={"job_id": job_id, "status": "queued"})


@router.get("/api/benchmark/status/{job_id}")
async def get_benchmark_job_status(job_id: str, request: Request):
    """Poll the status and progress of a background benchmark job."""
    from src.backend.api.server import BENCHMARK_JOBS, BENCHMARK_JOBS_LOCK

    user = _current_user(request)
    with BENCHMARK_JOBS_LOCK:
        job = BENCHMARK_JOBS.get(job_id)
    # Jobs record their owner at start; another user's job looks like a missing one.
    if not job or (job.get("owner_id") and job["owner_id"] != str(user.get("id"))):
        raise HTTPException(status_code=404, detail="Benchmark job not found")
    return JSONResponse(
        content={
            "job_id": job_id,
            "status": job.get("status", "unknown"),
            "progress": job.get("progress", []),
            "result": job.get("result") if job.get("status") == "done" else None,
            "error": job.get("error") if job.get("status") == "error" else None,
        }
    )


@router.post("/api/benchmark/apply-optimization")
async def apply_benchmark_optimization(request: Request) -> dict[str, Any]:
    """Apply proposed benchmark optimization changes to engine_weights.yaml."""
    from src.backend.api.server import _apply_engine_optimization_changes
    from src.backend.engines.scoring.fusion_engine import load_engine_config, save_engine_config

    # engine_weights.yaml is global to every tenant, so this is admin-only.
    user = _current_user(request, admin_only=True)
    payload = await _json_object(request)
    changes = payload.get("config_changes")
    if not isinstance(changes, list) or not changes:
        raise HTTPException(status_code=400, detail="No optimization changes provided")
    current_config = load_engine_config()
    applied = _apply_engine_optimization_changes(current_config, changes)
    save_engine_config(applied["config"])
    logger.warning(
        "Engine optimization applied by admin %s (%d changes)",
        user.get("id"),
        len(applied["applied_changes"]),
    )
    return {
        "success": True,
        "message": "Proposed optimization applied to engine_weights.yaml",
        "config_file": "src/backend/engines/engine_weights.yaml",
        "applied_changes": applied["applied_changes"],
    }


# ---------------------------------------------------------------------------
# Benchmark report downloads
# ---------------------------------------------------------------------------


@router.get("/benchmark/{job_id}/download-csv")
async def download_benchmark_csv(job_id: str, request: Request):
    """Download benchmark results as CSV."""
    job = _accessible_job_or_404(request, job_id)
    pair_results = job["pair_results"]

    # Columns come from every tool seen, not just the first pair's: a pair
    # missing a tool used to shift its scores into the wrong column.
    tool_order: list[str] = []
    for pair in pair_results:
        for tr in pair.get("tool_results", []):
            if tr["tool"] not in tool_order:
                tool_order.append(tr["tool"])

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Pair 1", "Pair 2", "Label", *[f"{t} Score" for t in tool_order]])
    for pair in pair_results:
        scores = {tr["tool"]: tr.get("score") for tr in pair.get("tool_results", [])}
        row = [
            _csv_safe(pair.get("file_a")),
            _csv_safe(pair.get("file_b")),
            _csv_safe(pair.get("label")),
        ]
        for tool in tool_order:
            score = scores.get(tool)
            row.append(f"{score:.3f}" if isinstance(score, (int, float)) else "")
        writer.writerow(row)
    return Response(
        content=si.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=benchmark_results_{_safe_filename_part(job_id)}.csv"
            )
        },
    )


@router.get("/benchmark/{job_id}/download-pdf")
async def download_benchmark_pdf(job_id: str, request: Request):
    """Download benchmark results as PDF (falls back to HTML if WeasyPrint unavailable)."""
    job = _accessible_job_or_404(request, job_id, require_key=None)

    # File names are untrusted uploads; they were interpolated into the HTML
    # unescaped (stored XSS in the HTML fallback, markup injection in the PDF).
    rows = "".join(
        f"<tr><td>{html.escape(str(pair.get('file_a', '')))}</td>"
        f"<td>{html.escape(str(pair.get('file_b', '')))}</td>"
        f"<td>{html.escape(str(tr.get('tool', '')))}</td>"
        f"<td>{float(tr.get('score', 0.0)):.3f}</td></tr>\n"
        for pair in job.get("pair_results", [])
        for tr in pair.get("tool_results", [])
    )
    safe_id = html.escape(job_id)
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Benchmark Results {safe_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f5f5f5; font-weight: 600; }}
        h1 {{ font-size: 18px; margin-bottom: 10px; }}
        .meta {{ color: #666; font-size: 12px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Benchmark Results</h1>
    <div class="meta">Job ID: {safe_id}<br>Generated: {datetime.now(timezone.utc).isoformat()}</div>
    <table>
        <thead>
            <tr><th>Pair 1</th><th>Pair 2</th><th>Tool</th><th>Score</th></tr>
        </thead>
        <tbody>
{rows}        </tbody>
    </table>
</body>
</html>"""
    return await _html_report_response(
        html_content,
        filename_base=f"benchmark_{_safe_filename_part(job_id)}",
        fallback_title=f"Benchmark {job_id}",
    )


@router.post("/api/benchmark/export-pdf")
async def export_benchmark_pdf(request: Request):
    """Export a benchmark evaluation scorecard as PDF."""
    from src.backend.api.server import (
        _build_benchmark_report_lines,
        _build_detailed_evaluation_scorecard,
        _generate_detailed_scorecard_pdf,
        _simple_text_pdf_bytes,
    )

    payload = await _json_object(request)
    dataset_name = str(
        payload.get("datasetName")
        or (payload.get("summary") or {}).get("dataset_name")
        or "Benchmark"
    )

    if payload.get("format") == "detailed_scorecard":
        scorecard = _build_detailed_evaluation_scorecard(payload)
        pdf = await run_in_threadpool(_generate_detailed_scorecard_pdf, scorecard)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=benchmark_evaluation_scorecard.pdf"
            },
        )

    generated_at = payload.get("runAt") or datetime.now(timezone.utc).isoformat()
    benchmark_type_val = payload.get("benchmark_type") or payload.get("benchmarkMode")
    evaluation = payload.get("evaluation") or {}

    if benchmark_type_val == "pan_optimization" and evaluation:
        metric_source = evaluation.get("integritydesk") or next(
            (m for m in evaluation.values() if m and not m.get("error")), {}
        )

        def metric_value(name: str, fallback: float = 0.0) -> float:
            """Read a numeric metric from the PAN result."""
            value = metric_source.get(name, fallback) if metric_source else fallback
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback

        metrics = [
            (
                "PlagDet",
                metric_value("plagdet"),
                "Primary PAN score; combines detection quality with granularity penalty.",
                "Optimize threshold and fusion weights against PlagDet directly.",
            ),
            (
                "Precision",
                metric_value("precision"),
                "Low precision means clean pairs are being flagged as plagiarism.",
                "Raise decision threshold and require stronger multi-engine agreement.",
            ),
            (
                "Recall",
                metric_value("recall"),
                "Low recall means known plagiarism pairs are being missed.",
                "Widen candidate retrieval and strengthen renamed/structural clone handling.",
            ),
            (
                "F1 Score",
                metric_value("f1_score", metric_value("best_f1")),
                "Balances precision and recall for the selected operating threshold.",
                "Run threshold sweeps and keep the point that maximizes F1 and PlagDet.",
            ),
            (
                "Granularity",
                metric_value("granularity", 1.0),
                "Values above 1 mean detections are split into too many fragments.",
                "Merge adjacent or overlapping evidence for the same pair.",
            ),
            (
                "AUC-PR",
                metric_value("auc_pr", metric_value("pr_auc")),
                "Measures whether true plagiarism ranks above negative pairs.",
                "Tune fusion weights with PR-AUC as an objective and add harder negatives.",
            ),
            (
                "False Positive Rate",
                metric_value("false_positive_rate"),
                "High FPR creates noisy admin feedback and weakens reviewer trust.",
                "Add boilerplate/template suppression and stricter negative filters.",
            ),
            (
                "Top-10 Retrieval",
                metric_value("top_10_retrieval"),
                "Measures how cleanly true positives appear in the first ranked candidates.",
                "Tune retrieval with precision@10 and rerank using token/AST/winnowing evidence.",
            ),
            (
                "Avg Runtime",
                metric_value("avg_runtime_seconds"),
                "Slow runtime makes iterative optimization and larger datasets expensive.",
                "Cache parsing and run heavy engines only on shortlisted candidates.",
            ),
        ]
        rows = ""
        for name, value, why, action in metrics:
            if name == "Avg Runtime":
                display = f"{value:.3f}s"
            elif name == "Granularity":
                display = f"{value:.3f}"
            else:
                display = f"{value * 100:.1f}%"
            rows += (
                f"<tr><td>{html.escape(name)}</td><td><strong>{html.escape(display)}</strong>"
                f"</td><td>{html.escape(why)}</td><td>{html.escape(action)}</td></tr>\n"
            )
        title = f"{html.escape(dataset_name)} PAN Optimization Report"
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 24px; color: #0f172a; }}
        h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .meta {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 9px 10px; text-align: left; vertical-align: top; }}
        th {{ background: #f8fafc; font-size: 12px; text-transform: uppercase; }}
        td {{ font-size: 12px; line-height: 1.5; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="meta">Generated: {html.escape(str(generated_at))}</div>
    <table>
        <thead>
            <tr><th>Metric</th><th>Score</th><th>Why It Matters</th><th>Next Action</th></tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
</body>
</html>"""
        return await _html_report_response(
            html_content,
            filename_base="pan_optimization_report",
            fallback_title=f"{dataset_name} PAN Optimization Report",
        )

    # Legacy format
    report_lines = _build_benchmark_report_lines(payload)
    pdf = _simple_text_pdf_bytes(f"{dataset_name} Benchmark Report", report_lines)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=benchmark_evaluation_scorecard.pdf"},
    )


# ---------------------------------------------------------------------------
# Radar chart data
# ---------------------------------------------------------------------------


@router.get("/benchmark/{job_id}/radar")
async def get_tool_radar_data(job_id: str, request: Request):
    """Return radar-chart data for benchmark tool comparison.

    The first four axes are derived from the score distribution. ``speed`` and
    ``scalability`` are fixed placeholders (0.65 / 0.70) because no
    runtime data is read here; they are listed under ``synthetic_axes`` so the
    UI can label or hide them instead of presenting them as measurements.
    """
    job = _accessible_job_or_404(request, job_id)
    pair_results = job["pair_results"]
    tools = sorted({tr["tool"] for pair in pair_results for tr in pair.get("tool_results", [])})
    axes = [
        {"id": "classic_plagiarism", "name": "Copy+Rename", "axis": 0},
        {"id": "near_miss", "name": "Refactored", "axis": 1},
        {"id": "obfuscated", "name": "Obfuscated", "axis": 2},
        {"id": "semantic", "name": "LLM Rewritten", "axis": 3},
        {"id": "speed", "name": "Performance", "axis": 4},
        {"id": "scalability", "name": "Scalability", "axis": 5},
    ]
    tool_scores: dict[str, list[float]] = {}
    for tool in tools:
        scores = [0.0, 0.0, 0.0, 0.0, 0.65, 0.70]
        all_scores = [
            tr["score"]
            for pair in pair_results
            for tr in pair.get("tool_results", [])
            if tr["tool"] == tool
        ]
        if all_scores:
            mid_band = [s for s in all_scores if 0.3 < s < 0.7]
            scores[0] = max(all_scores)
            scores[1] = sorted(all_scores)[len(all_scores) // 2]
            scores[2] = min(all_scores)
            scores[3] = sum(mid_band) / max(1, len(mid_band))
        tool_scores[tool] = scores
    return JSONResponse(
        content={
            "axes": axes,
            "tool_scores": tool_scores,
            "metadata": {
                "job_id": job_id,
                "pairs_analyzed": len(pair_results),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "synthetic_axes": ["speed", "scalability"],
            },
        }
    )


# ---------------------------------------------------------------------------
# Benchmark audit
# ---------------------------------------------------------------------------


@router.get("/api/benchmark-audit/{dataset_id}")
async def get_benchmark_audit(dataset_id: str) -> dict[str, Any]:
    """Return a benchmark audit for labeled datasets with explicit pair metadata."""
    from src.backend.api.server import (
        BENCHMARK_DATA_DIR,
        BUILTIN_PAIR_DATASET_IDS,
        _audit_benchmark_pairs,
        _benchmark_split_guard,
        _build_benchmark_quality_certificate,
        _read_generated_pair_items,
    )

    dataset_id = _validated_dataset_id(dataset_id)
    if not dataset_id:
        raise HTTPException(status_code=404, detail="Benchmark dataset not found")
    dataset_root = BENCHMARK_DATA_DIR / dataset_id
    if not dataset_root.exists() and dataset_id not in BUILTIN_PAIR_DATASET_IDS:
        raise HTTPException(status_code=404, detail="Benchmark dataset not found")
    raw_pairs = _read_generated_pair_items(dataset_root)
    if not raw_pairs:
        raise HTTPException(
            status_code=400,
            detail="Benchmark audit requires explicit pair-labeled dataset metadata",
        )
    return {
        "dataset_id": dataset_id,
        "audit": _audit_benchmark_pairs(raw_pairs),
        "quality_certificate": _build_benchmark_quality_certificate(dataset_root),
        "split_guard": {
            "tuning": _benchmark_split_guard("validation", "tuning"),
            "locked_test": _benchmark_split_guard("test", "tuning"),
        },
    }
