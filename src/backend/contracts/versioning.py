"""Schema Versioning - Enforce version compatibility.

This module provides version management for schemas.
Every pipeline stage checks schema version at runtime.
Mismatched versions fail fast.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .schema_registry import SchemaVersion, registry


@dataclass(frozen=True)
class VersionManifest:
    """Manifest of schema versions used in a run.

    Attributes:
        schemas: Dict of schema name to version info.
        created_at: ISO timestamp of creation.
        run_id: Unique run identifier.
    """

    schemas: Dict[str, SchemaVersion]
    created_at: str
    run_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Serializable dict.
        """
        return {
            "schemas": {
                name: {"name": v.name, "version": v.version, "hash": v.hash}
                for name, v in self.schemas.items()
            },
            "created_at": self.created_at,
            "run_id": self.run_id,
        }

    def save(self, path: Path) -> None:
        """Save manifest to file.

        Args:
            path: File path to save to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> VersionManifest:
        """Load manifest from file.

        Args:
            path: File path to load from.

        Returns:
            VersionManifest instance.
        """
        with open(path) as f:
            data = json.load(f)
        return cls.load_from_dict(data)

    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> VersionManifest:
        """Load manifest from dictionary.

        Args:
            data: Dictionary with manifest data.

        Returns:
            VersionManifest instance.
        """
        schemas = {}
        for name, info in data["schemas"].items():
            schemas[name] = SchemaVersion(
                name=info["name"],
                version=info["version"],
                hash=info["hash"],
            )

        return cls(
            schemas=schemas,
            created_at=data["created_at"],
            run_id=data["run_id"],
        )


def check_compatibility(
    schema_name: str,
    expected_version: str,
    actual_version: str,
) -> bool:
    """Check if two schema versions are compatible.

    Args:
        schema_name: Schema name.
        expected_version: Expected version.
        actual_version: Actual version.

    Returns:
        True if compatible.
    """
    # Same version is always compatible
    if expected_version == actual_version:
        return True

    # Check registry for compatibility info
    return registry.check_compatibility(schema_name, actual_version)


def create_version_manifest(run_id: str) -> VersionManifest:
    """Create a version manifest for current schemas.

    Args:
        run_id: Unique run identifier.

    Returns:
        VersionManifest with all registered schemas.
    """
    from datetime import datetime

    schemas = registry.list_schemas()

    return VersionManifest(
        schemas=schemas,
        created_at=datetime.now().isoformat(),
        run_id=run_id,
    )


def validate_manifest(manifest: VersionManifest) -> List[str]:
    """Validate a version manifest against current registry.

    Args:
        manifest: Manifest to validate.

    Returns:
        List of error messages (empty if valid).
    """
    errors: List[str] = []

    for name, version_info in manifest.schemas.items():
        # Check if schema exists
        if name not in registry.list_schemas():
            errors.append(f"Schema '{name}' not in current registry")
            continue

        # Check version compatibility
        current_version = registry.get_version(name)
        if not check_compatibility(name, current_version.version, version_info.version):
            errors.append(
                f"Schema '{name}' version mismatch: "
                f"expected {current_version.version}, got {version_info.version}"
            )

        # Check hash compatibility
        if current_version.hash != version_info.hash:
            errors.append(
                f"Schema '{name}' hash mismatch: "
                f"expected {current_version.hash}, got {version_info.hash}"
            )

    return errors
