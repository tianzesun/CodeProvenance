"""Root endpoint for the API."""
from fastapi import APIRouter
from src.backend.engines.scoring.fusion_engine import load_engine_config

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "message": "Welcome to IntegrityDesk API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@router.get("/api/config/engine-status")
async def get_engine_config():
    """Return current active engine configuration, weights and baselines."""
    config = load_engine_config()
    return {
        "weights": config.get("weights", {}),
        "baselines": config.get("baseline_correction", {}).get("baselines", {}),
        "thresholds": config.get("thresholds", {}),
        "decision": config.get("decision", {}),
        "auto_calibrated": config.get("advanced", {}).get("auto_calibrate", False),
        "last_updated": config.get("advanced", {}).get("last_calibration_time", None)
    }


@router.get("/api/config/full")
async def get_full_config():
    """Return complete engine configuration for admin settings page."""
    config = load_engine_config()
    return config


@router.put("/api/config/update")
async def update_config(config: dict):
    """Update engine configuration (admin only)."""
    from src.backend.engines.scoring.fusion_engine import save_engine_config

    # Validate config structure
    required_sections = ["weights", "baseline_correction", "thresholds", "decision", "toggles", "performance", "advanced"]
    for section in required_sections:
        if section not in config:
            return {"error": f"Missing required section: {section}"}

    # Save updated configuration
    save_engine_config(config)

    return {"success": True, "message": "Configuration updated successfully"}