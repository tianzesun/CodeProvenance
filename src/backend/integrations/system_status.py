"""Live service-health overview for the Settings → System tab.

Each check returns a small dict with a three-state ``status`` (``up``,
``down`` or ``unconfigured``) plus a human-readable ``label``/``detail`` pair
and, when a live round-trip was made, ``latency_ms`` and ``verified=True``.
Every helper degrades to a ``down``/``unconfigured`` payload instead of
raising, so one unreachable service can never break the whole overview.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url

from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings
from src.backend.integrations import llm_provider
from src.backend.integrations.provider_catalog import (
    get_provider_spec,
    list_provider_models,
)

logger = logging.getLogger(__name__)

#: Per-probe network timeout, in seconds. The overview fans all probes out
#: concurrently, so the endpoint answers in roughly the slowest probe.
PROBE_TIMEOUT_SECONDS = 5.0

#: runtimes that mean "embeddings are intentionally off".
_DISABLED_EMBEDDING_RUNTIMES = frozenset({"none", "off", "disabled", "false", "0"})


def _service(
    status: str,
    label: str,
    detail: str = "",
    latency_ms: int = 0,
    verified: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Build one service status payload.

    Args:
        status: ``up``, ``down`` or ``unconfigured``.
        label: Short human-readable service name.
        detail: One-line specifics (model, address, failure reason).
        latency_ms: Measured round-trip time of the live probe, if any.
        verified: Whether a live round-trip succeeded (as opposed to
            config inspection alone).
        extra: Additional service-specific fields.

    Returns:
        A JSON-serializable status dict.
    """
    payload: dict[str, Any] = {
        "status": status,
        "label": label,
        "detail": detail,
        "latency_ms": latency_ms,
        "verified": verified,
    }
    payload.update(extra)
    return payload


def _describe_database_url(raw_url: str) -> str:
    """Describe a database URL without leaking credentials.

    Args:
        raw_url: SQLAlchemy database URL (may contain a password).

    Returns:
        A short ``dialect · host/database`` style description, or ``""``
        when the URL cannot be parsed.
    """
    try:
        url = make_url(raw_url)
    except Exception:
        return ""
    dialect = (url.get_backend_name() or "").upper() or "Database"
    host = url.host or ""
    name = url.database or ""
    target = f"{host}/{name}" if host and name else (host or name)
    return f"{dialect} · {target}" if target else dialect


async def check_database() -> dict[str, Any]:
    """Probe the application database with a trivial query.

    Returns:
        ``up`` with dialect/host detail when ``SELECT 1`` succeeds,
        otherwise ``down`` with the failure reason.
    """
    started = time.monotonic()
    try:
        masked = _describe_database_url(settings.DATABASE_URL.get_secret_value())

        def _ping() -> None:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))

        await asyncio.to_thread(_ping)
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info("Database status probe failed: %s", exc)
        return _service(
            "down", "Database", f"Unreachable: {exc}", latency_ms=elapsed_ms
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return _service(
        "up", "Database", masked or "Connected", latency_ms=elapsed_ms, verified=True
    )


def _embedding_server_root() -> str:
    """Resolve the embedding server root from settings.

    The configured base URL points at the OpenAI-compatible ``/v1`` prefix
    while ``/health`` lives at the server root, so a trailing ``/v1`` is
    stripped before probing.

    Returns:
        The server root URL, or ``""`` when no embedding server is configured.
    """
    base = (settings.EMBEDDING_SERVER_URL or "").strip()
    if not base and settings.EMBEDDING_SERVER_HOST:
        base = (
            f"http://{settings.EMBEDDING_SERVER_HOST}:"
            f"{settings.EMBEDDING_SERVER_PORT}/v1"
        )
    root = base.rstrip("/")
    if root.lower().endswith("/v1"):
        root = root[: -len("/v1")].rstrip("/")
    return root


async def check_embedding(
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Probe the embedding service.

    A configured embedding server gets a live ``GET /health`` round-trip
    (which also reports the loaded model). A local runtime cannot be probed
    without loading the model into this process, so it reports its resolved
    configuration unverified instead.

    Args:
        transport: Optional mock transport for tests.

    Returns:
        The embedding service status payload.
    """
    started = time.monotonic()
    root = _embedding_server_root()
    if root:
        try:
            async with httpx.AsyncClient(
                timeout=PROBE_TIMEOUT_SECONDS, transport=transport
            ) as client:
                response = await client.get(f"{root}/health")
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.info("Embedding status probe failed for %s: %s", root, exc)
            return _service(
                "down",
                "Embedding server",
                f"{root} unreachable: {exc}",
                latency_ms=elapsed_ms,
            )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        model = str(data.get("model") or settings.EMBEDDING_MODEL or "")
        loaded = data.get("model_loaded")
        detail = model
        if loaded is True:
            detail = f"{model} · model loaded" if model else "model loaded"
        elif loaded is False:
            detail = f"{model} · model NOT loaded" if model else "model NOT loaded"
        return _service(
            "up",
            "Embedding server",
            detail or root,
            latency_ms=elapsed_ms,
            verified=True,
            base_url=root,
        )
    runtime = (settings.EMBEDDING_RUNTIME or "").strip().lower()
    if runtime in _DISABLED_EMBEDDING_RUNTIMES:
        return _service("unconfigured", "Embeddings", "Embedding runtime is disabled")
    model = (settings.EMBEDDING_MODEL or "").strip()
    device = (settings.EMBEDDING_DEVICE or "auto").strip()
    detail = f"Local {runtime or 'default'} runtime"
    if model:
        detail += f" · {model}"
    detail += f" · device {device} (loads on first use)"
    return _service("up", "Embeddings", detail)


async def check_llm_provider(
    provider_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Check one LLM provider with a cheap model-listing round-trip.

    Listing models proves connectivity (and key validity for keyed vendors)
    without spending tokens on a completion.

    Args:
        provider_key: Canonical provider key or alias.
        transport: Optional mock transport for tests.

    Returns:
        The provider status payload, including resolved model and base URL.
    """
    started = time.monotonic()
    try:
        spec = get_provider_spec(provider_key)
    except ValueError as exc:
        return _service("down", str(provider_key), str(exc))
    config = llm_provider.resolve_provider_config(spec.key)
    try:
        listing = await list_provider_models(
            spec.key,
            config.api_key or None,
            config.base_url,
            limit=1,
            timeout=PROBE_TIMEOUT_SECONDS,
            transport=transport,
        )
    except ValueError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return _service(
            "down",
            spec.label,
            str(exc),
            latency_ms=elapsed_ms,
            base_url=config.base_url,
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    entry = _service(
        "down",
        spec.label,
        "",
        latency_ms=elapsed_ms,
        provider=spec.key,
        base_url=config.base_url,
        model=config.model or "(auto)",
        requires_key=spec.requires_key,
        models_available=int(listing.get("available_count") or 0),
    )
    if listing.get("source") == "live":
        entry.update(
            status="up",
            verified=True,
            detail=(
                f"{entry['models_available']} models listed · " f"{entry['model']}"
            ),
        )
        return entry
    if spec.requires_key and not config.api_key:
        entry.update(status="unconfigured", detail="No API key stored")
        return entry
    if not config.model and not spec.recommended:
        entry.update(status="unconfigured", detail="No model selected")
        return entry
    entry.update(detail=str(listing.get("message") or "Unreachable"))
    return entry


async def check_llm(
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Check the default (and fallback, when set) LLM providers.

    Args:
        transport: Optional mock transport for tests.

    Returns:
        An aggregate payload with per-provider entries. The aggregate is
        ``down`` when any provider is down, ``unconfigured`` when any is
        unconfigured, and ``up`` otherwise.
    """
    default = (settings.LLM_PROVIDER or "openai").strip() or "openai"
    fallback = (settings.LLM_FALLBACK_PROVIDER or "").strip()
    keys = [key for key in dict.fromkeys([default, fallback]) if key]
    providers = [await check_llm_provider(key, transport) for key in keys]
    if any(entry["status"] == "down" for entry in providers):
        status = "down"
    elif any(entry["status"] == "unconfigured" for entry in providers):
        status = "unconfigured"
    else:
        status = "up"
    names = ", ".join(entry["label"] for entry in providers)
    return _service(
        status,
        "LLM",
        names,
        verified=all(entry.get("verified", False) for entry in providers),
        default_provider=default,
        providers=providers,
    )


def _nvidia_smi_summary() -> str:
    """Summarize GPUs visible to the OS driver, independent of PyTorch.

    Returns:
        A one-line summary (GPU names + driver version), or why the query
        itself failed. An OS-visible GPU that torch cannot see points at a
        CPU-only torch build or a container started without GPU passthrough.
    """
    import shutil
    import subprocess

    exe = shutil.which("nvidia-smi")
    if not exe:
        return "nvidia-smi not found (no NVIDIA driver visible here)"
    try:
        proc = subprocess.run(
            [
                exe,
                "--query-gpu=name,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return f"nvidia-smi failed: {exc}"
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        return f"nvidia-smi error: {err[0][:100] if err else 'unknown'}"
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        return "nvidia-smi reports no GPUs"
    names = sorted({line.split(",")[0].strip() for line in lines})
    driver = lines[0].split(",")[-1].strip()
    gpu_word = "GPU" if len(lines) == 1 else "GPUs"
    return f"OS sees {len(lines)} {gpu_word} ({', '.join(names)}) · driver {driver}"


def check_gpu() -> dict[str, Any]:
    """Report CUDA GPU availability from the API process.

    Returns:
        ``up`` with device name/count (and free memory when reported),
        otherwise ``down`` with the reason (no CUDA, CPU-only box, or
        PyTorch missing).
    """
    started = time.monotonic()
    try:
        import torch
    except ImportError:
        return _service("down", "GPU", "PyTorch is not installed")
    try:
        if not torch.cuda.is_available():
            build = getattr(getattr(torch, "version", None), "cuda", None)
            build_note = (
                "CPU-only torch build — reinstall a CUDA wheel"
                if build is None
                else f"torch CUDA {build} build, but no device visible"
            )
            return _service(
                "down",
                "GPU",
                f"No CUDA device (torch {torch.__version__}; {build_note}; "
                f"{_nvidia_smi_summary()})",
            )
        count = torch.cuda.device_count()
        name = torch.cuda.get_device_name(0)
        detail = f"{name} × {count}"
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info(0)
            detail += f" · {free_bytes / 1e9:.1f}/{total_bytes / 1e9:.1f} GB free"
        except Exception as exc:
            logger.debug("GPU memory query failed: %s", exc)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return _service("up", "GPU", detail, latency_ms=elapsed_ms, verified=True)
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info("GPU status probe failed: %s", exc)
        return _service(
            "down", "GPU", f"CUDA query failed: {exc}", latency_ms=elapsed_ms
        )


def check_storage(reports_dir: str | None) -> dict[str, Any]:
    """Report free disk space where reports are written.

    Args:
        reports_dir: Directory reports are written to, or ``None`` to skip.

    Returns:
        ``up`` with free/total space, ``down`` when critically low
        (<512 MB) or unreadable.
    """
    if not reports_dir:
        return _service("unconfigured", "Storage", "Report directory not monitored")
    try:
        usage = shutil.disk_usage(reports_dir)
    except Exception as exc:
        return _service("down", "Storage", f"Unreadable: {exc}")
    free_gb = usage.free / 1e9
    total_gb = usage.total / 1e9
    detail = f"{free_gb:.1f} GB free of {total_gb:.1f} GB"
    if usage.free < 512 * 1024 * 1024:
        return _service("down", "Storage", f"Critically low disk space: {detail}")
    return _service("up", "Storage", detail, verified=True)


async def collect_system_status(
    reports_dir: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Fan out every service probe concurrently and aggregate the overview.

    No probe is allowed to raise: each helper already degrades to a
    ``down``/``unconfigured`` payload internally.

    Args:
        reports_dir: Directory reports are written to (disk-space probe).
        transport: Optional mock transport for the HTTP-based probes.

    Returns:
        A payload with ``checked_at``, an overall ``status`` (worst of:
        ``down`` beats ``unconfigured`` beats ``up``) and per-service entries.
    """
    database, embedding, llm, gpu, storage = await asyncio.gather(
        check_database(),
        check_embedding(transport),
        check_llm(transport),
        asyncio.to_thread(check_gpu),
        asyncio.to_thread(check_storage, reports_dir),
    )
    services = {
        "database": database,
        "embedding": embedding,
        "llm": llm,
        "gpu": gpu,
        "storage": storage,
    }
    statuses = [entry["status"] for entry in services.values()]
    if "down" in statuses:
        overall = "down"
    elif "unconfigured" in statuses:
        overall = "unconfigured"
    else:
        overall = "up"
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": overall,
        "services": services,
    }
