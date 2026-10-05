"""Root endpoint for the API."""

from __future__ import annotations

import logging
import math
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.backend.api.middleware.auth import require_admin
from src.backend.engines.scoring.fusion_engine import load_engine_config, save_engine_config

logger = logging.getLogger(__name__)

router = APIRouter()

_REQUIRED_SECTIONS = (
    "weights",
    "baseline_correction",
    "thresholds",
    "decision",
    "toggles",
    "performance",
    "advanced",
)
_RANGE_SECTIONS = ("weights", "thresholds")
_config_lock = threading.Lock()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def config_issues(config: dict[str, Any]) -> list[str]:
    """Return every problem with a full engine configuration (empty if valid).

    This route replaces the whole file with the request body, and used to accept
    anything that had the right top-level keys: weights that do not sum to 1,
    NaN, values outside 0-1, or sections that are not objects.
    """
    issues = [f"Missing required section: {s}" for s in _REQUIRED_SECTIONS if s not in config]
    issues += [
        f"Section must be an object: {s}"
        for s in _REQUIRED_SECTIONS
        if s in config and not isinstance(config[s], dict)
    ]
    weights = config.get("weights")
    if isinstance(weights, dict) and weights:
        if any(not _is_number(v) or not math.isfinite(v) for v in weights.values()):
            issues.append("weights must be finite numbers")
        elif abs(sum(weights.values()) - 1.0) > 0.001:
            issues.append(f"Weights must sum to 1.0, got {sum(weights.values()):.3f}")
    for section in _RANGE_SECTIONS:
        values = config.get(section)
        if isinstance(values, dict):
            for key, value in values.items():
                if _is_number(value) and not (math.isfinite(value) and 0.0 <= value <= 1.0):
                    issues.append(f"{section}.{key} must be between 0.0 and 1.0, got {value}")
    return issues


@router.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "message": "Welcome to IntegrityDesk API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Config handlers are plain ``def``: loading/saving the config reads and writes
# a file, which must not run on the event loop.


@router.get("/api/config/engine-status")
def get_engine_config():
    """Return current active engine configuration, weights and baselines."""
    config = load_engine_config()
    return {
        "weights": config.get("weights", {}),
        "baselines": config.get("baseline_correction", {}).get("baselines", {}),
        "thresholds": config.get("thresholds", {}),
        "decision": config.get("decision", {}),
        "auto_calibrated": config.get("advanced", {}).get("auto_calibrate", False),
        "last_updated": config.get("advanced", {}).get("last_calibration_time", None),
    }


@router.get("/api/config/full", dependencies=[Depends(require_admin)])
def get_full_config():
    """Return complete engine configuration for admin settings page."""
    return load_engine_config()


@router.put("/api/config/update", dependencies=[Depends(require_admin)])
def update_config(config: dict[str, Any]):
    """Update engine configuration (admin only)."""
    issues = config_issues(config)
    if issues:
        # A validation failure used to be returned as {"error": ...} with HTTP 200,
        # which clients read as success.
        raise HTTPException(status_code=400, detail="; ".join(issues))

    with _config_lock:
        save_engine_config(config)
    logger.info("Engine configuration replaced via /api/config/update")
    return {"success": True, "message": "Configuration updated successfully"}
