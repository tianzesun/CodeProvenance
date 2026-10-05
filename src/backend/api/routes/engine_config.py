"""
Engine Configuration API endpoints.

Allows viewing and modifying similarity engine weights and thresholds at runtime.
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.backend.api.middleware.auth import require_admin
from src.backend.engines.weight_config import EngineWeightConfig

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_ENGINES = 64
# update_weights() persists to disk; serialise concurrent writers.
_update_lock = threading.Lock()


def validate_weight_update(
    weights: dict[str, float], known_engines: set[str] | None = None
) -> list[str]:
    """Return the problems with a proposed weight update (empty if valid).

    The docstring promised 0.0-1.0 values but nothing enforced it, and ``NaN``
    or negative weights reached the persisted config.
    """
    problems: list[str] = []
    if not weights:
        return ["No weights provided"]
    if len(weights) > _MAX_ENGINES:
        return [f"At most {_MAX_ENGINES} weights may be supplied"]
    if known_engines:
        unknown = sorted(set(weights) - known_engines)
        if unknown:
            problems.append(f"Unknown engine(s): {', '.join(unknown)}")
    for name, value in weights.items():
        if isinstance(value, bool) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            problems.append(f"Weight for '{name}' must be between 0.0 and 1.0")
    return problems


@router.get("/v1/engines/weights", response_model=dict[str, Any])
def get_engine_weights():
    """
    Get current engine weights and threshold configuration.

    Returns:
        Complete engine configuration including weights, thresholds, and verification settings
    """
    config = EngineWeightConfig.get_instance()

    return {
        "weights": config.weights,
        "enabled_engines": config.get_enabled_engines(),
        "deep_verify_thresholds": config.deep_verify_thresholds,
        "precision_guard": config.precision_guard,
        "baselines": config.baselines,
        "decision_thresholds": config.decision_thresholds,
        "classification_thresholds": config.classification_thresholds,
        "last_updated": config._last_load_time,
    }


@router.put(
    "/v1/engines/weights",
    response_model=dict[str, Any],
    dependencies=[Depends(require_admin)],
)
def update_engine_weights(weights: dict[str, float]):
    """
    Update engine weights at runtime. Changes are persisted immediately.

    Args:
        weights: Dictionary mapping engine names to new weight values (0.0 - 1.0)

    Returns:
        Updated normalized weights
    """
    config = EngineWeightConfig.get_instance()
    problems = validate_weight_update(weights, set(config.weights or {}))
    if problems:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(problems))

    try:
        with _update_lock:
            config.update_weights(weights)
            updated = config.weights
    except (ValueError, KeyError):
        # The config object rejected the values themselves.
        logger.warning("Engine weight update rejected", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update engine weights. Check the supplied values.",
        ) from None
    except Exception:
        # Anything else (e.g. the file could not be written) is not a client error.
        ref = uuid.uuid4().hex[:12]
        logger.exception("Failed to update engine weights (ref=%s)", ref)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update engine weights. Reference: {ref}",
        ) from None

    logger.info("Engine weights updated via API")
    return {
        "status": "success",
        "message": "Engine weights updated successfully",
        "updated_weights": updated,
    }


@router.post(
    "/v1/engines/weights/reload",
    response_model=dict[str, Any],
    dependencies=[Depends(require_admin)],
)
def reload_engine_config():
    """
    Force reload engine configuration from disk.

    Returns:
        Reload status
    """
    config = EngineWeightConfig.get_instance()
    with _update_lock:
        reloaded = config.reload_if_changed()

    return {
        "status": "success",
        "reloaded": reloaded,
        "message": "Configuration reloaded" if reloaded else "No changes detected",
        "weights": config.weights,
    }
