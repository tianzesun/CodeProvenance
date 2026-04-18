"""Settings API routes for admin configuration."""

from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from src.backend.engines.scoring.profile_manager import (
    apply_course_profile,
    export_course_profile_yaml,
    get_active_profile_id,
    get_course_profile,
    list_course_profile_summaries,
)
from src.backend.engines.scoring.fusion_engine import (
    load_engine_config,
    save_engine_config,
)

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
        "course_profile": config.get("course_profile", {}),
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
                    status_code=400, detail=f"Weights must sum to 1.0, got {total:.3f}"
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
                                detail=f"{section}.{key} must be between 0.0 and 1.0, got {value}",
                            )

        # Save configuration
        save_engine_config(updated_config)

        return {"success": True, "message": "Engine configuration updated successfully"}

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
            "results": result,
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
        },
    }


@router.get("/profiles")
async def list_course_profiles():
    """List available course profiles and the active selection."""
    return {
        "active_profile_id": get_active_profile_id(),
        "profiles": list_course_profile_summaries(),
    }


@router.get("/profiles/{profile_id}")
async def get_course_profile_details(profile_id: str):
    """Get one course profile with friendly and backend weight views."""
    try:
        profile = get_course_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return profile.to_dict()


@router.post("/profiles/{profile_id}/apply")
async def apply_course_profile_endpoint(profile_id: str):
    """Apply a bundled course profile to the active engine configuration."""
    try:
        result = apply_course_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "success": True,
        "message": f"Applied course profile: {profile_id}",
        **result,
    }


@router.post("/profiles/{profile_id}/export")
async def export_course_profile(profile_id: str):
    """Export a bundled course profile as a standalone YAML file."""
    try:
        output_path = Path("reports/profiles") / f"{profile_id}.yaml"
        exported_path = export_course_profile_yaml(profile_id, output_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "success": True,
        "profile_id": profile_id,
        "output_path": str(exported_path),
    }
