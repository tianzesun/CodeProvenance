"""Settings API routes for admin configuration."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from src.backend.engines.scoring.fusion_engine import load_engine_config, save_engine_config

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/engine-config")
async def get_engine_config():
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
    }


@router.put("/engine-config")
async def update_engine_config(config_update: Dict[str, Any]):
    """Update engine configuration (admin only)."""
    try:
        # Load current config
        current_config = load_engine_config()

        # Merge updates
        updated_config = {**current_config, **config_update}

        # Validate weights sum to 1.0
        if "weights" in updated_config and updated_config["weights"]:
            total = sum(updated_config["weights"].values())
            if abs(total - 1.0) > 0.001:
                raise HTTPException(
                    status_code=400,
                    detail=f"Weights must sum to 1.0, got {total:.3f}"
                )

        # Validate value ranges (0-1)
        validate_sections = ["weights", "thresholds"]
        for section in validate_sections:
            if section in updated_config:
                for key, value in updated_config[section].items():
                    if isinstance(value, (int, float)):
                        if not 0.0 <= value <= 1.0:
                            raise HTTPException(
                                status_code=400,
                                detail=f"{section}.{key} must be between 0.0 and 1.0, got {value}"
                            )

        # Save configuration
        save_engine_config(updated_config)

        return {
            "success": True,
            "message": "Engine configuration updated successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calibrate")
async def trigger_calibration():
    """Trigger automatic engine calibration."""
    try:
        from src.backend.engines.scoring.fusion_engine import FusionEngine

        result = FusionEngine.calibrate_optimal_weights()

        return {
            "success": True,
            "message": "Calibration completed successfully",
            "results": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibration failed: {str(e)}")


@router.get("/validation")
async def validate_current_config():
    """Validate current configuration for issues."""
    config = load_engine_config()
    issues = []

    # Check weights sum
    if "weights" in config:
        total = sum(config["weights"].values())
        if abs(total - 1.0) > 0.001:
            issues.append(f"Weights don't sum to 1.0 (current: {total:.3f})")

    # Check value ranges
    for section in ["weights", "thresholds"]:
        if section in config:
            for key, value in config[section].items():
                if isinstance(value, (int, float)):
                    if not 0.0 <= value <= 1.0:
                        issues.append(f"{section}.{key} out of range: {value}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "config_summary": {
            "weights_count": len(config.get("weights", {})),
            "thresholds_count": len(config.get("thresholds", {})),
            "toggles_enabled": sum(config.get("toggles", {}).values()),
        }
    }