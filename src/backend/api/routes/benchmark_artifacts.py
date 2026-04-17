from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from src.backend.benchmark.results.results_loader import (
    BenchmarkResultsLoader,
    ResultsLoaderError,
)

router = APIRouter(prefix="/api/benchmark/artifacts", tags=["benchmark-artifacts"])


def discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


def is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


@router.get("/{run_id}")
def get_primary_artifact(run_id: str):
    loader = BenchmarkResultsLoader(repo_root=discover_repo_root())

    try:
        result = loader.load(run_id)
    except ResultsLoaderError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if result.tool == "moss" and result.result_url:
        return RedirectResponse(url=result.result_url, status_code=307)

    if not result.primary_artifact:
        raise HTTPException(status_code=404, detail="No primary artifact available")

    artifact_path = Path(result.primary_artifact)
    repo_root = discover_repo_root()

    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")

    if not is_subpath(artifact_path, repo_root):
        raise HTTPException(status_code=403, detail="Artifact path is outside allowed root")

    if artifact_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Primary artifact is a directory; request a specific file via /file endpoint",
        )

    media_type, _ = mimetypes.guess_type(str(artifact_path))
    return FileResponse(
        path=artifact_path,
        filename=artifact_path.name,
        media_type=media_type or "application/octet-stream",
    )


@router.get("/{run_id}/file")
def get_named_artifact_file(
    run_id: str,
    path: str = Query(..., description="Absolute artifact path returned from results endpoint"),
):
    loader = BenchmarkResultsLoader(repo_root=discover_repo_root())

    try:
        result = loader.load(run_id)
    except ResultsLoaderError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    allowed_paths = {p for p in result.raw_artifacts}
    requested_path = Path(path)
    repo_root = discover_repo_root()

    if str(requested_path) not in allowed_paths:
        raise HTTPException(status_code=404, detail="Artifact not found in run results")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file missing on disk")

    if not is_subpath(requested_path, repo_root):
        raise HTTPException(status_code=403, detail="Artifact path is outside allowed root")

    media_type, _ = mimetypes.guess_type(str(requested_path))
    return FileResponse(
        path=requested_path,
        filename=requested_path.name,
        media_type=media_type or "application/octet-stream",
    )
