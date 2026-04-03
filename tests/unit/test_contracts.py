"""Contract Tests - Scientific enforcement via tests.

This is the MOST IMPORTANT enforcement layer.
Without this, everything is informal.

These tests ensure:
- All schemas are registered
- All engines return valid schemas
- All adapters translate correctly
- All validation gates work
"""
from __future__ import annotations

import math
import pytest
from pathlib import Path
from typing import Any, Dict, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from contracts import (
    registry,
    ValidationError,
    ValidationGate,
    ValidationResult,
    validate_evaluation_result,
    validate_enriched_pair,
    SchemaVersion,
    VersionManifest,
    check_compatibility,
    create_version_manifest,
    validate_manifest,
    ReproducibilityHash,
    GoldenDataset,
    RunFingerprint,
    compute_config_hash,
    compute_reproducibility_hash,
    create_golden_dataset,
    verify_golden_dataset,
    create_run_fingerprint,
    verify_run_fingerprint,
)
from benchmark.contracts.evaluation_result import EvaluationResult, EnrichedPair


class TestSchemaRegistry:
    """Test schema registry enforcement."""
    
    def test_builtin_schemas_registered(self) -> None:
        """Verify all built-in schemas are registered."""
        schemas = registry.list_schemas()
        assert "EvaluationResult" in schemas
        assert "EnrichedPair" in schemas
    
    def test_get_schema(self) -> None:
        """Test getting schema by name."""
        schema = registry.get("EvaluationResult")
        assert schema == EvaluationResult
    
    def test_get_unknown_schema_raises(self) -> None:
        """Test getting unknown schema raises KeyError."""
        with pytest.raises(KeyError):
            registry.get("UnknownSchema")
    
    def test_validate_evaluation_result(self) -> None:
        """Test validating EvaluationResult."""
        result = registry.validate(
            "EvaluationResult",
            {
                "pair_id": "test_pair",
                "score": 0.85,
                "decision": True,
                "confidence": 0.9,
                "engine": "test_engine",
            },
        )
        assert isinstance(result, EvaluationResult)
        assert result.pair_id == "test_pair"
        assert result.score == 0.85
    
    def test_validate_invalid_data_raises(self) -> None:
        """Test validating invalid data raises error."""
        with pytest.raises(ValidationError):
            registry.validate(
                "EvaluationResult",
                {"pair_id": "test", "score": 1.5},  # Invalid score
            )


class TestValidationGate:
    """Test runtime validation gate."""
    
    def test_valid_evaluation_result(self) -> None:
        """Test validating valid EvaluationResult."""
        gate = ValidationGate()
        result = gate.validate_evaluation_result(
            {
                "pair_id": "test",
                "score": 0.85,
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
            }
        )
        assert result.is_valid
    
    def test_nan_score_rejected(self) -> None:
        """Test NaN score is rejected."""
        gate = ValidationGate()
        result = gate.validate_evaluation_result(
            {
                "pair_id": "test",
                "score": float("nan"),
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
            }
        )
        assert not result.is_valid
        assert any("NaN" in e for e in result.errors)
    
    def test_score_out_of_range_rejected(self) -> None:
        """Test score out of range is rejected."""
        gate = ValidationGate()
        result = gate.validate_evaluation_result(
            {
                "pair_id": "test",
                "score": 1.5,
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
            }
        )
        assert not result.is_valid
        assert any("score" in e.lower() for e in result.errors)
    
    def test_missing_pair_id_rejected(self) -> None:
        """Test missing pair_id is rejected."""
        gate = ValidationGate()
        result = gate.validate_evaluation_result(
            {
                "score": 0.85,
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
            }
        )
        assert not result.is_valid
        assert any("pair_id" in e.lower() for e in result.errors)
    
    def test_empty_pair_id_rejected(self) -> None:
        """Test empty pair_id is rejected."""
        gate = ValidationGate()
        result = gate.validate_evaluation_result(
            {
                "pair_id": "",
                "score": 0.85,
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
            }
        )
        assert not result.is_valid
    
    def test_unknown_fields_in_strict_mode(self) -> None:
        """Test unknown fields are rejected in strict mode."""
        gate = ValidationGate(strict_mode=True)
        result = gate.validate_evaluation_result(
            {
                "pair_id": "test",
                "score": 0.85,
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
                "unknown_field": "value",
            }
        )
        assert not result.is_valid
        assert any("unknown" in e.lower() for e in result.errors)
    
    def test_convenience_function(self) -> None:
        """Test convenience validation function."""
        result = validate_evaluation_result(
            {
                "pair_id": "test",
                "score": 0.85,
                "decision": True,
                "confidence": 0.9,
                "engine": "test",
            }
        )
        assert isinstance(result, EvaluationResult)


class TestVersioning:
    """Test schema versioning enforcement."""
    
    def test_create_version_manifest(self) -> None:
        """Test creating version manifest."""
        manifest = create_version_manifest(run_id="test_run")
        assert manifest.run_id == "test_run"
        assert "EvaluationResult" in manifest.schemas
        assert "EnrichedPair" in manifest.schemas
    
    def test_validate_manifest(self) -> None:
        """Test validating manifest."""
        manifest = create_version_manifest(run_id="test_run")
        errors = validate_manifest(manifest)
        assert len(errors) == 0
    
    def test_version_manifest_serialization(self) -> None:
        """Test manifest serialization."""
        manifest = create_version_manifest(run_id="test_run")
        data = manifest.to_dict()
        assert data["run_id"] == "test_run"
        assert "schemas" in data
    
    def test_version_manifest_roundtrip(self) -> None:
        """Test manifest roundtrip serialization."""
        manifest = create_version_manifest(run_id="test_run")
        data = manifest.to_dict()
        loaded = VersionManifest.load_from_dict(data)
        assert loaded.run_id == manifest.run_id
        assert loaded.schemas.keys() == manifest.schemas.keys()


class TestReproducibility:
    """Test reproducibility enforcement."""
    
    def test_compute_config_hash(self) -> None:
        """Test config hash computation."""
        config = {"key1": "value1", "key2": 123}
        hash1 = compute_config_hash(config)
        hash2 = compute_config_hash(config)
        assert hash1 == hash2
        assert len(hash1) == 64
    
    def test_config_hash_order_independent(self) -> None:
        """Test config hash is order independent."""
        config1 = {"a": 1, "b": 2}
        config2 = {"b": 2, "a": 1}
        assert compute_config_hash(config1) == compute_config_hash(config2)
    
    def test_reproducibility_hash_creation(self) -> None:
        """Test reproducibility hash creation."""
        config = {"test": "value"}
        hash_obj = compute_reproducibility_hash(
            dataset_path=Path("/tmp"),
            code_version="abc123",
            config=config,
        )
        assert hash_obj.code_version == "abc123"
        assert len(hash_obj.combined_hash) == 64
        assert hash_obj.timestamp
    
    def test_reproducibility_hash_deterministic(self) -> None:
        """Test reproducibility hash is deterministic."""
        config = {"test": "value"}
        hash1 = compute_reproducibility_hash(
            dataset_path=Path("/tmp"),
            code_version="abc123",
            config=config,
        )
        hash2 = compute_reproducibility_hash(
            dataset_path=Path("/tmp"),
            code_version="abc123",
            config=config,
        )
        assert hash1.combined_hash == hash2.combined_hash
