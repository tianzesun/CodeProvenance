"""Contracts module - Single source of truth for all schemas.

This module provides the Schema Registry and validation enforcement
for the entire benchmark system.
"""

from .reproducibility import (
    GoldenDataset,
    ReproducibilityHash,
    RunFingerprint,
    compute_config_hash,
    compute_directory_hash,
    compute_file_hash,
    compute_reproducibility_hash,
    create_golden_dataset,
    create_run_fingerprint,
    verify_golden_dataset,
    verify_run_fingerprint,
)
from .schema_registry import SchemaRegistry, ValidationError, registry
from .validation import (
    ValidationGate,
    ValidationResult,
    validate_enriched_pair,
    validate_evaluation_result,
)
from .versioning import (
    SchemaVersion,
    VersionManifest,
    check_compatibility,
    create_version_manifest,
    validate_manifest,
)

__all__ = [
    "GoldenDataset",
    # Reproducibility
    "ReproducibilityHash",
    "RunFingerprint",
    # Registry
    "SchemaRegistry",
    # Versioning
    "SchemaVersion",
    "ValidationError",
    # Validation
    "ValidationGate",
    "ValidationResult",
    "VersionManifest",
    "check_compatibility",
    "compute_config_hash",
    "compute_directory_hash",
    "compute_file_hash",
    "compute_reproducibility_hash",
    "create_golden_dataset",
    "create_run_fingerprint",
    "create_version_manifest",
    "registry",
    "validate_enriched_pair",
    "validate_evaluation_result",
    "validate_manifest",
    "verify_golden_dataset",
    "verify_run_fingerprint",
]
