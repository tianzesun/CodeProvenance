"""Course profile management for the plagiarism fusion engine.

This module defines the course-profile layer that sits above the raw engine
weights file. It provides a stable place for faculty presets, future Optuna
exports, and dashboard profile switching without rewriting the core fusion code.
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from src.backend.engines.scoring.fusion_engine import (
    load_engine_config,
    save_engine_config,
)

logger = logging.getLogger(__name__)

PROFILE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "course_profiles.yaml"

_cache_lock = threading.Lock()
_payload_cache: tuple[Path, float, dict[str, Any]] | None = None


@dataclass(frozen=True)
class CourseProfile:
    """Serializable course detection profile."""

    profile_id: str
    name: str
    description: str
    course_tags: list[str]
    friendly_weights: dict[str, float]
    backend_weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return asdict(self)


def load_course_profiles() -> dict[str, CourseProfile]:
    """Load all course profiles from the bundled YAML file."""
    payload = _load_profiles_payload()
    profiles: dict[str, CourseProfile] = {}
    for index, item in enumerate(payload.get("profiles") or []):
        # One malformed profile (missing key, all-zero weights) used to make EVERY profile
        # unloadable; it is skipped and logged instead.
        try:
            profile = CourseProfile(
                profile_id=str(item["id"]),
                name=str(item["name"]),
                description=str(item.get("description", "")),
                course_tags=[str(tag) for tag in item.get("course_tags") or []],
                friendly_weights=_normalize_weights(item.get("friendly_weights") or {}),
                backend_weights=_normalize_weights(item.get("backend_weights") or {}),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            logger.warning("Skipping invalid course profile #%d: %s", index, exc)
            continue
        if profile.profile_id in profiles:
            logger.warning("Duplicate course profile id %r; keeping the first", profile.profile_id)
            continue
        profiles[profile.profile_id] = profile
    return profiles


def get_default_profile_id() -> str:
    """Return the configured default course profile ID."""
    payload = _load_profiles_payload()
    configured = str(payload.get("default_profile_id", "balanced_general"))
    profiles = load_course_profiles()
    if configured in profiles or not profiles:
        return configured
    # A default that does not exist made every caller of get_course_profile(default) raise.
    fallback = next(iter(profiles))
    logger.warning("default_profile_id %r is not a loaded profile; using %r", configured, fallback)
    return fallback


def get_course_profile(profile_id: str) -> CourseProfile:
    """Return one course profile by identifier."""
    profiles = load_course_profiles()
    if profile_id not in profiles:
        raise KeyError(f"Unknown course profile: {profile_id}")
    return profiles[profile_id]


def list_course_profile_summaries() -> list[dict[str, Any]]:
    """Return compact summaries for profile pickers and dashboard APIs."""
    profiles = load_course_profiles()
    return [
        {
            "id": profile.profile_id,
            "name": profile.name,
            "description": profile.description,
            "course_tags": profile.course_tags,
            "friendly_weights": profile.friendly_weights,
        }
        for profile in profiles.values()
    ]


def get_active_profile_id() -> str | None:
    """Return the currently applied course profile ID, if one is set."""
    config = load_engine_config()
    profile_section = config.get("course_profile", {})
    active_profile_id = profile_section.get("id")
    return str(active_profile_id) if active_profile_id else None


def apply_course_profile(profile_id: str) -> dict[str, Any]:
    """Apply a course profile onto the active fusion-engine configuration."""
    profile = get_course_profile(profile_id)
    config = load_engine_config()
    config["weights"] = dict(profile.backend_weights)
    config["course_profile"] = {
        "id": profile.profile_id,
        "name": profile.name,
        "description": profile.description,
        "course_tags": profile.course_tags,
        "friendly_weights": profile.friendly_weights,
    }
    save_engine_config(config)
    return {
        "applied_profile": profile.to_dict(),
        "updated_weights": dict(profile.backend_weights),
    }


def export_course_profile_yaml(profile_id: str, output_path: Path) -> Path:
    """Export a single profile as a standalone YAML file."""
    profile = get_course_profile(profile_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(profile.to_dict(), sort_keys=False),
        encoding="utf-8",
    )
    return output_path


def _load_profiles_payload() -> dict[str, Any]:
    """Read the bundled course-profile YAML payload (cached until the file changes)."""
    global _payload_cache
    path = PROFILE_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Missing course profile config: {path}")
    mtime = path.stat().st_mtime
    with _cache_lock:
        if _payload_cache and _payload_cache[0] == path and _payload_cache[1] == mtime:
            return _payload_cache[2]
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        if not isinstance(payload, dict):
            raise TypeError("Course profile config must be a mapping")
        _payload_cache = (path, mtime, payload)
        return payload


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize a weight mapping so the values sum to one."""
    cleaned: dict[str, float] = {}
    for key, value in weights.items():
        number = float(value)
        # ``max(nan, 0.0)`` is nan: a NaN weight made the total NaN, passed the ``<= 0``
        # check, and NaN weights were then saved into the live engine configuration.
        if not math.isfinite(number):
            raise ValueError(f"Profile weight {key!r} is not finite: {value!r}")
        cleaned[str(key)] = max(number, 0.0)
    total = sum(cleaned.values())
    if total <= 0.0:
        raise ValueError("Profile weights must contain at least one positive value")
    return {key: value / total for key, value in cleaned.items()}
