"""Tell people when an analysis finishes: a signed webhook and, optionally, an email.

Both go out after the job's final status is recorded and use the job's
workspace settings (``WEBHOOK_URL``, email delivery), so they are sent from
inside that workspace's ``workspace_overrides`` scope. Neither carries student
names, file names or code: only the job, its counts and a link.

A failed delivery is logged and never affects the job.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10
FINISHED_STATUSES = frozenset({"completed", "failed"})


def build_payload(job: dict[str, Any], frontend_url: str) -> dict[str, Any]:
    """The webhook body for a finished job (no student identifiers)."""
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    status = str(job.get("status") or "")
    job_id = str(job.get("id") or "")
    return {
        "event": f"analysis.{status}",
        "job_id": job_id,
        "status": status,
        "course": job.get("course_name") or "",
        "assignment": job.get("assignment_name") or "",
        "submissions": int(job.get("file_count") or len(job.get("submissions") or {})),
        "pairs_compared": int(summary.get("total_pairs") or 0),
        "pairs_flagged": int(summary.get("suspicious_pairs") or 0),
        "results_url": f"{frontend_url.rstrip('/')}/results/{job_id}",
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def _resolves_to_public_hosts(url: str) -> bool:
    """Whether every address the URL's host resolves to is public (SSRF guard at send time)."""
    host = urlsplit(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


def sign(body: bytes, timestamp: str, secret: str) -> str:
    """``sha256=<hex>`` HMAC of ``<timestamp>.<body>`` (receivers check it with the shared secret)."""
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + digest.hexdigest()


def post_webhook(url: str, payload: dict[str, Any]) -> bool:
    """POST a signed JSON payload to a validated public https URL; True on 2xx."""
    from src.backend.api.routes.jobs import validate_webhook_url

    try:
        url = validate_webhook_url(url) or ""
    except Exception:
        logger.warning("Analysis webhook skipped: the URL is not a public https URL")
        return False
    if not url or not _resolves_to_public_hosts(url):
        logger.warning(
            "Analysis webhook skipped: the host does not resolve to a public address"
        )
        return False
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "IntegrityDesk-webhook/1.0",
        "X-IntegrityDesk-Event": str(payload.get("event") or ""),
        "X-IntegrityDesk-Timestamp": timestamp,
    }
    secret = os.getenv("WEBHOOK_SECRET_KEY", "")
    if secret:
        headers["X-IntegrityDesk-Signature"] = sign(body, timestamp, secret)
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(
            request, timeout=WEBHOOK_TIMEOUT_SECONDS
        ) as response:
            ok = 200 <= int(getattr(response, "status", 200)) < 300
    except Exception as exc:
        logger.warning("Analysis webhook delivery failed: %s", type(exc).__name__)
        return False
    if not ok:
        logger.warning("Analysis webhook rejected by the receiver")
    return ok


def _owner_email(job: dict[str, Any]) -> str | None:
    owner = job.get("owner_user_id")
    if not owner:
        return None
    try:
        from src.backend.config.database import SessionLocal
        from src.backend.models.database import User

        with SessionLocal() as db:
            user = db.get(User, str(owner))
            return user.email if user and user.is_active else None
    except Exception:
        logger.warning("Could not look up who to email about job %s", job.get("id"))
        return None


def notify_job_finished(job: dict[str, Any], *, email_owner: bool) -> dict[str, bool]:
    """Send the webhook (if the workspace has one) and the owner email (if enabled).

    Call inside the job's workspace scope. Returns what was delivered.
    """
    from src.backend.config.settings import settings

    sent = {"webhook": False, "email": False}
    if job.get("guest") or str(job.get("status") or "") not in FINISHED_STATUSES:
        return sent
    payload = build_payload(job, settings.FRONTEND_URL)

    raw_url = settings.WEBHOOK_URL
    url = (
        raw_url.get_secret_value() if hasattr(raw_url, "get_secret_value") else raw_url
    )
    if (url or "").strip():
        sent["webhook"] = post_webhook(url.strip(), payload)

    if email_owner:
        to = _owner_email(job)
        if to:
            import asyncio

            from src.backend.infrastructure.email_service import EmailService

            title = " · ".join(
                p for p in (payload["course"], payload["assignment"]) if p
            )
            try:
                sent["email"] = asyncio.run(
                    EmailService.send_analysis_finished_email(
                        to,
                        title=title or "your analysis",
                        succeeded=payload["status"] == "completed",
                        submissions=payload["submissions"],
                        flagged_pairs=payload["pairs_flagged"],
                        results_url=payload["results_url"],
                    )
                )
            except Exception:
                logger.warning("Could not email the owner of job %s", job.get("id"))
    return sent
