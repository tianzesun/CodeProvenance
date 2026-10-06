"""Schema Versioning - Enforce version compatibility.

Every pipeline stage checks schema version at runtime. Mismatched versions fail fast.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._io import read_json, utc_now_iso, write_json_atomic
from .schema_registry import SchemaVersion, registry


@dataclass(frozen=True)
class VersionManifest:
    """Manifest of schema versions used in a run."""

    schemas: dict[str, SchemaVersion]
    created_at: str
    run_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemas": {
                name: {"name": v.name, "version": v.version, "hash": v.hash}
                for name, v in self.schemas.items()
            },
            "created_at": self.created_at,
            "run_id": self.run_id,
        }

    def save(self, path: Path) -> None:
        write_json_atomic(path, self.to_dict())

    @classmethod
    def load(cls, path: Path) -> VersionManifest:
        return cls.load_from_dict(read_json(path))

    @classmethod
    def load_from_dict(cls, data: dict[str, Any]) -> VersionManifest:
        """Build a manifest from a dict.

        Raises:
            ValueError: If the data is malformed.
        """
        try:
            schemas = {
                name: SchemaVersion(
                    name=info["name"], version=info["version"], hash=info["hash"]
                )
                for name, info in data["schemas"].items()
            }
            return cls(
                schemas=schemas, created_at=data["created_at"], run_id=data["run_id"]
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise ValueError(f"Malformed version manifest: {e!r}") from e


def check_compatibility(
    schema_name: str, expected_version: str, actual_version: str
) -> bool:
    """True if versions are identical or the registry lists ``actual_version``
    as compatible. Fail-closed for anything else."""
    if expected_version == actual_version:
        return True
    return registry.check_compatibility(schema_name, actual_version)


def create_version_manifest(run_id: str) -> VersionManifest:
    """Create a version manifest for all currently registered schemas."""
    return VersionManifest(
        schemas=registry.list_schemas(),
        created_at=utc_now_iso(),
        run_id=run_id,
    )


def validate_manifest(manifest: VersionManifest) -> list[str]:
    """Validate a manifest against the current registry.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []
    current_schemas = registry.list_schemas()  # one snapshot, not one per loop

    for name, recorded in manifest.schemas.items():
        current = current_schemas.get(name)
        if current is None:
            errors.append(f"Schema '{name}' not in current registry")
            continue

        if recorded.name != name:
            errors.append(f"Manifest entry '{name}' is labelled '{recorded.name}'")

        if not check_compatibility(name, current.version, recorded.version):
            errors.append(
                f"Schema '{name}' version mismatch: "
                f"expected {current.version}, got {recorded.version}"
            )

        if current.hash != recorded.hash:
            hint = (
                " (definition changed without a version bump)"
                if (current.version == recorded.version)
                else ""
            )
            errors.append(
                f"Schema '{name}' hash mismatch{hint}: "
                f"expected {current.hash}, got {recorded.hash}"
            )

    for name in current_schemas.keys() - manifest.schemas.keys():
        errors.append(f"Schema '{name}' is registered but missing from manifest")

    return errors
