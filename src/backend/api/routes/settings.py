"""Settings API routes for admin configuration."""

from __future__ import annotations

import logging
import math
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.backend.api.middleware.auth import require_admin
from src.backend.engines.scoring.fusion_engine import (
    load_engine_config,
    save_engine_config,
)
from src.backend.engines.scoring.profile_manager import (
    apply_course_profile,
    export_course_profile_yaml,
    get_active_profile_id,
    get_course_profile,
    list_course_profile_summaries,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

#: Top-level config sections a client may write. Anything else is rejected, so
#: arbitrary keys cannot be injected into the engine config file.
_ALLOWED_SECTIONS = frozenset(
    {
        "weights",
        "baseline_correction",
        "arbitration",
        "ast_boost",
        "decision",
        "thresholds",
        "toggles",
        "performance",
        "advanced",
        "course_profile",
    }
)
_RANGE_SECTIONS = ("weights", "thresholds")
_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

# Read-modify-write of the config file, and calibration, must not interleave.
_config_lock = threading.Lock()
_calibration_lock = threading.Lock()


def _failure(action: str) -> HTTPException:
    """Log the active exception; return a generic 500 with a reference id."""
    ref = uuid.uuid4().hex[:12]
    logger.exception("%s failed (ref=%s)", action, ref)
    return HTTPException(status_code=500, detail=f"{action} failed. Reference: {ref}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def collect_config_issues(config: dict[str, Any]) -> list[str]:
    """Return every problem with the weights and 0-1 range sections.

    Shared by the PUT validation and GET /validation so the two cannot disagree.
    Non-finite numbers are rejected explicitly: ``NaN`` slips past both the sum
    check and ``0 <= x <= 1``-style checks that only flag a *true* comparison.
    """
    issues: list[str] = []

    weights = config.get("weights")
    if isinstance(weights, dict) and weights:
        bad = [k for k, v in weights.items() if not _is_number(v) or not math.isfinite(v)]
        if bad:
            issues.append(f"weights must be finite numbers: {', '.join(map(str, bad))}")
        else:
            total = sum(weights.values())
            if abs(total - 1.0) > 0.001:
                issues.append(f"Weights must sum to 1.0, got {total:.3f}")

    for section in _RANGE_SECTIONS:
        values = config.get(section)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if _is_number(value) and not (math.isfinite(value) and 0.0 <= value <= 1.0):
                issues.append(f"{section}.{key} must be between 0.0 and 1.0, got {value}")
    return issues


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Merge ``update`` into ``base`` recursively, returning a new dict.

    A shallow merge replaced a whole section, so a PUT of one toggle erased
    every other toggle in that section.
    """
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_update(config_update: dict[str, Any]) -> dict[str, Any]:
    """Validate section names and map the GET-shaped ``baselines`` key.

    GET returns baselines under a top-level ``baselines`` key but the file keeps
    them at ``baseline_correction.baselines``; writing the GET shape back used
    to create a dead top-level ``baselines`` entry.
    """
    update = dict(config_update)
    if "baselines" in update:
        baselines = update.pop("baselines")
        if not isinstance(baselines, dict):
            raise HTTPException(status_code=400, detail="baselines must be an object")
        section = update.setdefault("baseline_correction", {})
        if not isinstance(section, dict):
            raise HTTPException(status_code=400, detail="baseline_correction must be an object")
        section["baselines"] = baselines
    unknown = sorted(set(update) - _ALLOWED_SECTIONS)
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unknown configuration section(s): {', '.join(unknown)}"
        )
    return update


@router.get("/engine-config")
def get_engine_config():
    """Get current engine configuration for settings page."""
    config = load_engine_config()
    return {
        "weights": config.get("weights", {}),
        "baselines": config.get("baseline_correction", {}).get("baselines", {}),
        "arbitration": config.get("arbitration", {}),
        "ast_boost": config.get("ast_boost", {}),
        "decision": config.get("decision", {}),
        "thresholds": config.get("thresholds", {}),
        "toggles": config.get("toggles", {}),
        "performance": config.get("performance", {}),
        "advanced": config.get("advanced", {}),
        "course_profile": config.get("course_profile", {}),
    }


@router.put("/engine-config", dependencies=[Depends(require_admin)])
def update_engine_config(config_update: dict[str, Any]):
    """Update engine configuration (admin only)."""
    update = normalize_update(config_update)
    try:
        with _config_lock:
            updated_config = deep_merge(load_engine_config(), update)
            issues = collect_config_issues(updated_config)
            if issues:
                # Raised inside the try, so it must be re-raised below: it used
                # to be swallowed by `except Exception` and replaced with a
                # useless "Invalid engine configuration." message.
                raise HTTPException(status_code=400, detail="; ".join(issues))
            save_engine_config(updated_config)
    except HTTPException:
        raise
    except Exception:
        raise _failure("Engine configuration update") from None

    return {"success": True, "message": "Engine configuration updated successfully"}


@router.post("/calibrate", dependencies=[Depends(require_admin)])
def trigger_calibration():
    """Trigger automatic engine calibration."""
    from src.backend.engines.scoring.fusion_engine import FusionEngine

    # Calibration is long-running; refuse a second concurrent run.
    if not _calibration_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Calibration is already running.")
    try:
        result = FusionEngine.calibrate_optimal_weights()
    except Exception:
        raise _failure("Calibration") from None
    finally:
        _calibration_lock.release()

    return {
        "success": True,
        "message": "Calibration completed successfully",
        "results": result,
    }


@router.get("/validation")
def validate_current_config():
    """Validate current configuration for issues."""
    config = load_engine_config()
    issues = collect_config_issues(config)

    toggles = config.get("toggles", {})
    return {
        "valid": not issues,
        "issues": issues,
        "config_summary": {
            "weights_count": len(config.get("weights", {})),
            "thresholds_count": len(config.get("thresholds", {})),
            "toggles_enabled": sum(1 for v in toggles.values() if v is True),
        },
    }


@router.get("/profiles")
def list_course_profiles():
    """List available course profiles and the active selection."""
    return {
        "active_profile_id": get_active_profile_id(),
        "profiles": list_course_profile_summaries(),
    }


@router.get("/profiles/{profile_id}")
def get_course_profile_details(profile_id: str):
    """Get one course profile with friendly and backend weight views."""
    try:
        profile = get_course_profile(profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Course profile not found") from None
    return profile.to_dict()


@router.post("/profiles/{profile_id}/apply", dependencies=[Depends(require_admin)])
def apply_course_profile_endpoint(profile_id: str):
    """Apply a bundled course profile to the active engine configuration."""
    try:
        with _config_lock:
            result = apply_course_profile(profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Course profile not found") from None
    return {
        "success": True,
        "message": f"Applied course profile: {profile_id}",
        **result,
    }


@router.post("/profiles/{profile_id}/export", dependencies=[Depends(require_admin)])
def export_course_profile(profile_id: str):
    """Export a bundled course profile as a standalone YAML file."""
    # profile_id becomes part of a file name; keep it to a plain token.
    if not _PROFILE_ID_RE.match(profile_id):
        raise HTTPException(status_code=404, detail="Course profile not found")
    output_path = Path("reports/profiles") / f"{profile_id}.yaml"
    try:
        export_course_profile_yaml(profile_id, output_path)
    except KeyError:
        raise HTTPException(status_code=404, detail="Course profile not found") from None
    return {
        "success": True,
        "profile_id": profile_id,
        # The relative path, not the resolved absolute server path.
        "output_path": str(output_path),
    }
