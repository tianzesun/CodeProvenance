"""Contracts module - Single source of truth for all schemas.

This module provides the Schema Registry and validation enforcement
for the entire benchmark system.
"""

from .schema_registry import SchemaRegistry, registry, ValidationError
from .validation import (
    ValidationGate,
    ValidationResult,
    validate_evaluation_result,
    validate_enriched_pair,
)
from .versioning import (
    SchemaVersion,
    VersionManifest,
    check_compatibility,
    create_version_manifest,
    validate_manifest,
)
from .reproducibility import (
    ReproducibilityHash,
    GoldenDataset,
    RunFingerprint,
    compute_file_hash,
    compute_directory_hash,
    compute_config_hash,
    compute_reproducibility_hash,
    create_golden_dataset,
    verify_golden_dataset,
    create_run_fingerprint,
    verify_run_fingerprint,
)

__all__ = [
    # Registry
    "SchemaRegistry",
    "registry",
    "ValidationError",
    # Validation
    "ValidationGate",
    "ValidationResult",
    "validate_evaluation_result",
    "validate_enriched_pair",
    # Versioning
    "SchemaVersion",
    "VersionManifest",
    "check_compatibility",
    "create_version_manifest",
    "validate_manifest",
    # Reproducibility
    "ReproducibilityHash",
    "GoldenDataset",
    "RunFingerprint",
    "compute_file_hash",
    "compute_directory_hash",
    "compute_config_hash",
    "compute_reproducibility_hash",
    "create_golden_dataset",
    "verify_golden_dataset",
    "create_run_fingerprint",
    "verify_run_fingerprint",
]
