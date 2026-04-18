"""Schema registry - single source of truth for all schemas.

This is the scientific enforcement layer. Every schema must be registered here.
Unregistered schemas cannot be used in the system.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, Type, TypeVar

from src.backend.benchmark.contracts.evaluation_result import (
    EnrichedPair,
    EvaluationResult,
)

T = TypeVar("T")


@dataclass(frozen=True)
class SchemaVersion:
    """Schema version information.

    Attributes:
        name: Schema name.
        version: Version string (semantic versioning).
        hash: SHA256 hash of schema definition.
    """

    name: str
    version: str
    hash: str


class SchemaRegistry:
    """Central registry for all schemas.

    This is the SINGLE SOURCE OF TRUTH for schema validation.
    Every module must register its schemas here.

    Enforcement:
    - No unregistered schemas can be used
    - Schema mismatch detected at runtime
    - Version compatibility enforced

    Usage:
        registry = SchemaRegistry()
        registry.register("EvaluationResult", EvaluationResult, version="1.0")

        # Later, validate:
        result = registry.validate("EvaluationResult", data)
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._schemas: Dict[str, Type[Any]] = {}
        self._versions: Dict[str, SchemaVersion] = {}
        self._compatibility: Dict[str, Set[str]] = {}

    def register(
        self,
        name: str,
        schema: Type[T],
        version: str = "1.0",
        compatible_with: Optional[Set[str]] = None,
    ) -> SchemaVersion:
        """Register a schema.

        Args:
            name: Unique schema name.
            schema: Schema class (dataclass or Pydantic model).
            version: Version string.
            compatible_with: Set of compatible versions.

        Returns:
            SchemaVersion with hash.

        Raises:
            ValueError: If schema already registered with different type.
        """
        if name in self._schemas:
            existing = self._schemas[name]
            if existing != schema:
                raise ValueError(
                    f"Schema '{name}' already registered with different type: "
                    f"{existing.__name__} vs {schema.__name__}"
                )

        # Compute schema hash
        schema_hash = self._compute_schema_hash(schema)

        # Store
        self._schemas[name] = schema
        version_info = SchemaVersion(name=name, version=version, hash=schema_hash)
        self._versions[name] = version_info

        # Compatibility
        if compatible_with:
            self._compatibility[name] = compatible_with

        return version_info

    def get(self, name: str) -> Type[Any]:
        """Get schema by name.

        Args:
            name: Schema name.

        Returns:
            Schema class.

        Raises:
            KeyError: If schema not registered.
        """
        if name not in self._schemas:
            raise KeyError(
                f"Schema '{name}' not registered. "
                f"Available: {list(self._schemas.keys())}"
            )
        return self._schemas[name]

    def validate(self, name: str, data: Any) -> Any:
        """Validate data against schema.

        Args:
            name: Schema name.
            data: Data to validate.

        Returns:
            Validated schema instance.

        Raises:
            KeyError: If schema not registered.
            ValidationError: If data doesn't match schema.
        """
        schema = self.get(name)

        # If already instance of schema, return as-is
        if isinstance(data, schema):
            return data

        # If dict, try to construct
        if isinstance(data, dict):
            try:
                return schema(**data)
            except (TypeError, ValueError) as e:
                raise ValidationError(f"Failed to validate '{name}': {e}") from e

        raise ValidationError(
            f"Cannot validate '{name}': expected dict or {schema.__name__}, "
            f"got {type(data).__name__}"
        )

    def get_version(self, name: str) -> SchemaVersion:
        """Get version info for schema.

        Args:
            name: Schema name.

        Returns:
            SchemaVersion info.
        """
        return self._versions[name]

    def check_compatibility(self, name: str, other_version: str) -> bool:
        """Check if a version is compatible.

        Args:
            name: Schema name.
            other_version: Version to check.

        Returns:
            True if compatible.
        """
        if name not in self._compatibility:
            return True
        return other_version in self._compatibility[name]

    def list_schemas(self) -> Dict[str, SchemaVersion]:
        """List all registered schemas.

        Returns:
            Dict of schema name to version info.
        """
        return dict(self._versions)

    def _compute_schema_hash(self, schema: Type[Any]) -> str:
        """Compute deterministic hash of schema.

        Args:
            schema: Schema class.

        Returns:
            SHA256 hash string.
        """
        # Get schema fields
        if hasattr(schema, "__dataclass_fields__"):
            fields = sorted(schema.__dataclass_fields__.keys())
        elif hasattr(schema, "__annotations__"):
            fields = sorted(schema.__annotations__.keys())
        else:
            fields = []

        # Compute hash
        schema_str = f"{schema.__name__}:{','.join(fields)}"
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


# Global registry instance
registry = SchemaRegistry()

# Register built-in schemas
registry.register("EvaluationResult", EvaluationResult, version="1.0")
registry.register("EnrichedPair", EnrichedPair, version="1.0")
