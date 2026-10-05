"""LTI 1.3 routes: OIDC login, launch, deep linking, PDP callback and JWKS."""

from __future__ import annotations

import asyncio
import functools
import html
import json
import logging
import os
import threading
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.backend.application.services.lti_service import LTIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lti", tags=["LTI"])

LTI_CONFIG_PATH = os.getenv("LTI_CONFIG_PATH", "config/lti_config.json")

#: JWK members that are private key material and must never be published.
_PRIVATE_JWK_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth", "k"})
_JWKS_CACHE_SECONDS = 300
_MAX_SUBMISSION_ID_CHARS = 256

# Fabricated originality results are only ever returned when this is switched on
# explicitly (local development).
_ALLOW_MOCK_RESULTS = os.getenv("LTI_ALLOW_MOCK_RESULTS", "").strip().lower() in {
    "1",
    "true",
    "yes",
}


@functools.lru_cache(maxsize=1)
def _build_service() -> LTIService:
    return LTIService(LTI_CONFIG_PATH)


def get_lti_service() -> LTIService:
    """Return the shared LTI service, created on first use.

    It used to be built at import time, so a missing or malformed LTI config
    stopped the *whole application* from starting even when LTI is unused.
    """
    try:
        return _build_service()
    except Exception:
        logger.exception("LTI service could not be initialised")
        raise HTTPException(status_code=503, detail="LTI is not configured.") from None


def _public_url(request: Request, route_name: str) -> str:
    """Absolute URL for a named route.

    Behind a TLS-terminating proxy ``request.url_for`` yields ``http://`` and
    the platform rejects the redirect URI. Set LTI_PUBLIC_BASE_URL to the
    externally visible origin to avoid that.
    """
    base = os.getenv("LTI_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}{request.app.url_path_for(route_name)}"
    return str(request.url_for(route_name))


@router.get("/login", name="lti_login")
@router.post("/login")
async def lti_login(request: Request):
    """OIDC Login Initiation."""
    return get_lti_service().login(request, _public_url(request, "lti_launch"))


@router.post("/launch", name="lti_launch")
async def lti_launch(request: Request):
    """LTI 1.3 Launch endpoint (Handles PDP and Deep Linking)."""
    service = get_lti_service()
    try:
        launch_data = service.get_launch_data(request)
        message_launch = service.get_message_launch(request)

        # 1. Handle Deep Linking Request (Content Selection)
        if message_launch.is_deep_link_launch():
            # The form used a hard-coded /api/v1 path that only worked for one
            # mounting; resolve the real route instead.
            action = html.escape(request.app.url_path_for("lti_deep_link_select"))
            return HTMLResponse(
                f"""
                <h1>IntegrityDesk - Select Content</h1>
                <form action="{action}" method="post">
                    <input type="hidden" name="id" value="pdp_assignment_1">
                    <button type="submit">Enable IntegrityDesk Forensic Scan for this Assignment</button>
                </form>
            """
            )

        # 2. Handle Standard PDP Launch (Instructor/Student View)
        query = urlencode(
            {
                "lti_user": launch_data.get("user_id") or "",
                "course": launch_data.get("course_id") or "",
            }
        )
        return RedirectResponse(url=f"/dashboard?{query}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("LTI launch failed: %s", type(exc).__name__, exc_info=True)
        raise HTTPException(
            status_code=400, detail="LTI launch failed. Check LTI configuration."
        ) from None


@router.post("/deep-link-select", name="lti_deep_link_select")
async def lti_deep_link_select(request: Request):
    """Handle content selection for Deep Linking."""
    selection = [
        {
            "url": _public_url(request, "lti_launch"),
            "title": "IntegrityDesk Forensic Scan",
        }
    ]
    return get_lti_service().handle_deep_linking(request, selection)


@router.post("/pdp/callback/{submission_id}")
async def lti_pdp_callback(request: Request, submission_id: str):
    """
    Plagiarism Detection Platform Callback.
    Canvas calls this to get the originality report for a submission.
    """
    if len(submission_id) > _MAX_SUBMISSION_ID_CHARS:
        raise HTTPException(status_code=400, detail="Invalid submission id")
    if not _ALLOW_MOCK_RESULTS:
        # This used to return {"score": 0.85, "ai_probability": 0.92} for EVERY
        # submission, i.e. invented accusations delivered to the LMS. Fail
        # closed until real results are wired in.
        raise HTTPException(
            status_code=501, detail="Originality report lookup is not implemented."
        )
    logger.warning("Returning MOCK originality results for %s (dev only)", submission_id)
    mock_results = {"score": 0.85, "ai_probability": 0.92}
    return get_lti_service().handle_plagiarism_callback(request, submission_id, mock_results)


# --- JWKS ------------------------------------------------------------------

_jwks_lock = threading.Lock()
_jwks_cache: dict[str, Any] = {"mtime": None, "jwks": {"keys": []}}


def sanitize_jwks(jwks: Any) -> dict[str, list[dict[str, Any]]]:
    """Return only the public members of each key.

    The endpoint is unauthenticated and publishes whatever the config holds
    under ``jwks``; if that ever includes a private JWK (``d``, ``p``, ``q``...)
    it would be leaked to the internet.
    """
    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    return {
        "keys": [
            {k: v for k, v in key.items() if k not in _PRIVATE_JWK_MEMBERS}
            for key in keys
            if isinstance(key, dict)
        ]
    }


def _load_public_jwks() -> dict[str, list[dict[str, Any]]]:
    """Read the JWKS from the config file, re-reading only when it changes."""
    try:
        mtime = os.stat(LTI_CONFIG_PATH).st_mtime
    except OSError:
        return {"keys": []}
    with _jwks_lock:
        if _jwks_cache["mtime"] == mtime:
            return _jwks_cache["jwks"]
        with open(LTI_CONFIG_PATH, encoding="utf-8") as fh:
            config = json.load(fh)
        jwks = sanitize_jwks(config.get("jwks", {"keys": []}))
        _jwks_cache.update(mtime=mtime, jwks=jwks)
        return jwks


@router.get("/jwks")
async def get_jwks():
    """Return the Public Key Set (JWKS)."""
    try:
        jwks = await asyncio.to_thread(_load_public_jwks)
    except Exception:
        logger.exception("Could not load JWKS from LTI config")
        raise HTTPException(status_code=503, detail="JWKS unavailable.") from None
    # Platforms poll this often; let them (and any CDN) cache it.
    return JSONResponse(
        content=jwks,
        headers={"Cache-Control": f"public, max-age={_JWKS_CACHE_SECONDS}"},
    )
