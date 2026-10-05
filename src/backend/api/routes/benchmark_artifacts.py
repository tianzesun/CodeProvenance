from __future__ import annotations

import functools
import logging
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Path as PathParam, Query
from fastapi.responses import FileResponse, RedirectResponse

from src.backend.benchmark.results.results_loader import (
    BenchmarkResultsLoader,
    ResultsLoaderError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/benchmark/artifacts", tags=["benchmark-artifacts"])

_RUN_ID_RE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_RUN_ID_PATTERN = re.compile(_RUN_ID_RE)
#: Never served even if a run record points at them.
_BLOCKED_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".kdbx"})
_BLOCKED_NAMES = frozenset({"id_rsa", "id_ed25519", "credentials", "secrets.json"})
_FILE_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}


@functools.lru_cache(maxsize=1)
def discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


def artifact_root() -> Path:
    """Directory artifacts may be served from.

    The whole repository used to be allowed, so a run record pointing at ``.env``
    or a key file would have been downloadable. Set BENCHMARK_ARTIFACT_ROOT to
    the results directory to narrow it further.
    """
    configured = os.getenv("BENCHMARK_ARTIFACT_ROOT", "").strip()
    return Path(configured).resolve() if configured else discover_repo_root().resolve()


def is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def servable_path(raw: str | Path, root: Path | None = None) -> Path | None:
    """Resolve ``raw`` and return it only if it may be served, else None.

    Relative paths are taken relative to the artifact root (not the process
    working directory). The *resolved* path is what gets served, so a symlink
    swapped in after the check cannot redirect the download.
    """
    root = (root or artifact_root()).resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return None
    if any(part.startswith(".") for part in relative.parts):  # .env, .git, .venv ...
        return None
    if resolved.suffix.lower() in _BLOCKED_SUFFIXES or resolved.name.lower() in _BLOCKED_NAMES:
        return None
    return resolved


def _allowed_redirect_hosts() -> set[str]:
    raw = os.getenv("BENCHMARK_REDIRECT_HOSTS", "moss.stanford.edu")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def safe_redirect_url(url: str | None) -> str | None:
    """Return ``url`` only if it is http(s) to an allow-listed host (no open redirect)."""
    if not url:
        return None
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        return None
    return url.strip() if host in _allowed_redirect_hosts() else None


def _load_run(run_id: str):
    if not _RUN_ID_PATTERN.match(run_id):
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    try:
        return BenchmarkResultsLoader(repo_root=discover_repo_root()).load(run_id)
    except ResultsLoaderError:
        # str(exc) used to be returned to the client and can contain server paths.
        logger.info("Benchmark run could not be loaded", exc_info=True)
        raise HTTPException(status_code=404, detail="Benchmark run not found") from None


def _file_response(path: Path) -> FileResponse:
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(
        path=path,
        filename=path.name,  # sets Content-Disposition: attachment
        media_type=media_type or "application/octet-stream",
        headers=_FILE_HEADERS,
    )


@router.get("/{run_id}")
def get_primary_artifact(run_id: str = PathParam(..., max_length=128)):
    result = _load_run(run_id)

    if result.tool == "moss" and result.result_url:
        target = safe_redirect_url(result.result_url)
        if target is None:
            logger.warning("Refusing redirect to a non-allow-listed result URL")
            raise HTTPException(status_code=404, detail="No primary artifact available")
        return RedirectResponse(url=target, status_code=307)

    if not result.primary_artifact:
        raise HTTPException(status_code=404, detail="No primary artifact available")

    # Containment is checked BEFORE existence: the other order told a caller
    # whether any path on the host exists (404 vs 403).
    artifact_path = servable_path(result.primary_artifact)
    if artifact_path is None:
        raise HTTPException(status_code=403, detail="Artifact path is outside allowed root")
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    if artifact_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Primary artifact is a directory; request a specific file via /file endpoint",
        )
    return _file_response(artifact_path)


@router.get("/{run_id}/file")
def get_named_artifact_file(
    run_id: str = PathParam(..., max_length=128),
    path: str = Query(
        ..., max_length=4096, description="Artifact path returned from results endpoint"
    ),
):
    result = _load_run(run_id)

    # Only paths the run itself lists can be requested.
    allowed_paths = {str(p) for p in result.raw_artifacts}
    if path not in allowed_paths:
        raise HTTPException(status_code=404, detail="Artifact not found in run results")

    requested_path = servable_path(path)
    if requested_path is None:
        raise HTTPException(status_code=403, detail="Artifact path is outside allowed root")
    if not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file missing on disk")
    return _file_response(requested_path)
