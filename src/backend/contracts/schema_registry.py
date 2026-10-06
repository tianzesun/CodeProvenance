"""Schema registry - single source of truth for all schemas.

This is the scientific enforcement layer. Every schema must be registered here.
Unregistered schemas cannot be used in the system.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from src.backend.contracts.evaluation_result import EnrichedPair, EvaluationResult

T = TypeVar("T")


class ValidationError(Exception):
    """Raised when validation fails."""


@dataclass(frozen=True)
class SchemaVersion:
    """Schema version information.

    Attributes:
        name: Schema name.
        version: Version string (semantic versioning).
        hash: SHA256 hash of the schema definition (field names + types).
    """

    name: str
    version: str
    hash: str


class SchemaRegistry:
    """Central registry for all schemas (thread-safe).

    Enforcement:
    - No unregistered schemas can be used
    - Schema mismatch detected at runtime
    - Version compatibility enforced (fail-closed: a version is compatible only
      if it equals the registered one or is explicitly listed)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._schemas: dict[str, type[Any]] = {}
        self._versions: dict[str, SchemaVersion] = {}
        self._compatibility: dict[str, frozenset[str]] = {}

    def register(
        self,
        name: str,
        schema: type[T],
        version: str = "1.0",
        compatible_with: set[str] | None = None,
    ) -> SchemaVersion:
        """Register a schema.

        Raises:
            ValueError: If the name is already registered with a different type.
        """
        with self._lock:
            existing = self._schemas.get(name)
            if existing is not None and existing != schema:
                raise ValueError(
                    f"Schema '{name}' already registered with different type: "
                    f"{existing.__name__} vs {schema.__name__}"
                )

            version_info = SchemaVersion(
                name=name, version=version, hash=self._compute_schema_hash(schema)
            )
            self._schemas[name] = schema
            self._versions[name] = version_info
            # Always overwrite so a re-register can't leave stale compatibility behind.
            self._compatibility[name] = frozenset(compatible_with or ())
            return version_info

    def get(self, name: str) -> type[Any]:
        """Get schema by name.

        Raises:
            KeyError: If schema not registered.
        """
        with self._lock:
            if name not in self._schemas:
                raise KeyError(
                    f"Schema '{name}' not registered. Available: {sorted(self._schemas)}"
                )
            return self._schemas[name]

    def validate(self, name: str, data: Any) -> Any:
        """Validate data against schema and return an instance.

        Raises:
            KeyError: If schema not registered.
            ValidationError: If data doesn't match schema.
        """
        schema = self.get(name)

        if isinstance(data, schema):
            return data

        if isinstance(data, Mapping):
            try:
                return schema(**data)
            except (TypeError, ValueError) as e:
                raise ValidationError(f"Failed to validate '{name}': {e}") from e

        raise ValidationError(
            f"Cannot validate '{name}': expected mapping or {schema.__name__}, "
            f"got {type(data).__name__}"
        )

    def get_version(self, name: str) -> SchemaVersion:
        """Get version info for schema.

        Raises:
            KeyError: If schema not registered.
        """
        with self._lock:
            if name not in self._versions:
                raise KeyError(f"Schema '{name}' not registered.")
            return self._versions[name]

    def check_compatibility(self, name: str, other_version: str) -> bool:
        """True if ``other_version`` equals the registered version or is listed
        in ``compatible_with``. Unknown schemas are never compatible."""
        with self._lock:
            current = self._versions.get(name)
            if current is None:
                return False
            return (
                other_version == current.version
                or other_version in self._compatibility.get(name, frozenset())
            )

    def list_schemas(self) -> dict[str, SchemaVersion]:
        """Snapshot of all registered schemas."""
        with self._lock:
            return dict(self._versions)

    @staticmethod
    def _compute_schema_hash(schema: type[Any]) -> str:
        """Deterministic hash over schema name and (field name, type) pairs.

        Hashing only field names (the old behaviour) missed type changes such as
        ``score: float`` -> ``score: str``.
        """
        if dataclasses.is_dataclass(schema):
            fields = [(f.name, str(f.type)) for f in dataclasses.fields(schema)]
        elif hasattr(schema, "model_fields"):  # Pydantic v2
            fields = [
                (n, str(getattr(f, "annotation", "")))
                for n, f in schema.model_fields.items()
            ]
        else:
            fields = [
                (n, str(t)) for n, t in getattr(schema, "__annotations__", {}).items()
            ]
        payload = json.dumps({"name": schema.__qualname__, "fields": sorted(fields)})
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Global registry instance
registry = SchemaRegistry()

# Register built-in schemas
registry.register("EvaluationResult", EvaluationResult, version="1.0")
registry.register("EnrichedPair", EnrichedPair, version="1.0")
