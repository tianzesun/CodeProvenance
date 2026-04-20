"""
Engine Configuration API endpoints.

Allows viewing and modifying similarity engine weights and thresholds at runtime.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging

from src.backend.config.database import get_db
from src.backend.engines.weight_config import EngineWeightConfig

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/v1/engines/weights", response_model=Dict[str, Any])
async def get_engine_weights():
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
        "last_updated": config._last_load_time
    }


@router.put("/v1/engines/weights", response_model=Dict[str, Any])
async def update_engine_weights(weights: Dict[str, float]):
    """
    Update engine weights at runtime. Changes are persisted immediately.
    
    Args:
        weights: Dictionary mapping engine names to new weight values (0.0 - 1.0)
        
    Returns:
        Updated normalized weights
    """
    try:
        config = EngineWeightConfig.get_instance()
        config.update_weights(weights)
        
        logger.info("Engine weights updated via API")
        
        return {
            "status": "success",
            "message": "Engine weights updated successfully",
            "updated_weights": config.weights
        }
        
    except Exception as e:
        logger.error("Failed to update engine weights: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update weights: {str(e)}"
        )


@router.post("/v1/engines/weights/reload", response_model=Dict[str, Any])
async def reload_engine_config():
    """
    Force reload engine configuration from disk.
    
    Returns:
        Reload status
    """
    config = EngineWeightConfig.get_instance()
    reloaded = config.reload_if_changed()
    
    return {
        "status": "success",
        "reloaded": reloaded,
        "message": "Configuration reloaded" if reloaded else "No changes detected",
        "weights": config.weights
    }
