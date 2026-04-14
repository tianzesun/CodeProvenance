"""Runtime Validation Gate - Hard stop at every boundary.

This module provides validation enforcement at system boundaries.
Every adapter, pipeline stage, and API endpoint must validate through this gate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from benchmark.contracts.evaluation_result import EvaluationResult, EnrichedPair
from .registry import ValidationError, registry

T = TypeVar("T")


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation.
    
    Attributes:
        is_valid: Whether validation passed.
        errors: List of error messages.
        warnings: List of warning messages.
    """
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def raise_if_invalid(self) -> None:
        """Raise ValidationError if not valid.
        
        Raises:
            ValidationError: If validation failed.
        """
        if not self.is_valid:
            raise ValidationError(
                f"Validation failed with {len(self.errors)} error(s): "
                + "; ".join(self.errors)
            )


class ValidationGate:
    """Runtime validation gate.
    
    Every boundary must pass through this gate.
    This is the HARD STOP for invalid data.
    
    Enforcement rules:
    - reject NaN scores
    - reject score > 1 or < 0
    - reject missing pair_id
    - reject unknown fields (optional strict mode)
    
    Usage:
        gate = ValidationGate()
        result = gate.validate_evaluation_result(data)
        result.raise_if_invalid()
    """
    
    def __init__(self, strict_mode: bool = False) -> None:
        """Initialize validation gate.
        
        Args:
            strict_mode: If True, reject unknown fields.
        """
        self.strict_mode = strict_mode
    
    def validate_evaluation_result(self, data: Any) -> ValidationResult:
        """Validate EvaluationResult data.
        
        Args:
            data: Data to validate (dict or EvaluationResult).
            
        Returns:
            ValidationResult with errors and warnings.
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        # Check type
        if isinstance(data, EvaluationResult):
            # Already validated, check for NaN
            if math.isnan(data.score):
                errors.append("score is NaN")
            if math.isnan(data.confidence):
                errors.append("confidence is NaN")
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
            )
        
        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=[f"Expected dict or EvaluationResult, got {type(data).__name__}"],
                warnings=[],
            )
        
        # Required fields
        required_fields = {"pair_id", "score", "decision", "confidence", "engine"}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            errors.append(f"Missing required fields: {missing_fields}")
        
        # Check for unknown fields in strict mode
        if self.strict_mode:
            known_fields = required_fields | {"metadata"}
            unknown_fields = set(data.keys()) - known_fields
            if unknown_fields:
                errors.append(f"Unknown fields: {unknown_fields}")
        
        # Validate score
        if "score" in data:
            score = data["score"]
            if not isinstance(score, (int, float)):
                errors.append(f"score must be numeric, got {type(score).__name__}")
            elif math.isnan(score):
                errors.append("score is NaN")
            elif not 0.0 <= score <= 1.0:
                errors.append(f"score must be in [0, 1], got {score}")
        
        # Validate confidence
        if "confidence" in data:
            confidence = data["confidence"]
            if not isinstance(confidence, (int, float)):
                errors.append(f"confidence must be numeric, got {type(confidence).__name__}")
            elif math.isnan(confidence):
                errors.append("confidence is NaN")
            elif not 0.0 <= confidence <= 1.0:
                errors.append(f"confidence must be in [0, 1], got {confidence}")
        
        # Validate decision
        if "decision" in data:
            decision = data["decision"]
            if not isinstance(decision, bool):
                errors.append(f"decision must be bool, got {type(decision).__name__}")
        
        # Validate pair_id
        if "pair_id" in data:
            pair_id = data["pair_id"]
            if not isinstance(pair_id, str):
                errors.append(f"pair_id must be string, got {type(pair_id).__name__}")
            elif not pair_id:
                errors.append("pair_id must not be empty")
        
        # Validate engine
        if "engine" in data:
            engine = data["engine"]
            if not isinstance(engine, str):
                errors.append(f"engine must be string, got {type(engine).__name__}")
            elif not engine:
                errors.append("engine must not be empty")
        
        # Validate metadata
        if "metadata" in data:
            metadata = data["metadata"]
            if not isinstance(metadata, dict):
                errors.append(f"metadata must be dict, got {type(metadata).__name__}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def validate_enriched_pair(self, data: Any) -> ValidationResult:
        """Validate EnrichedPair data.
        
        Args:
            data: Data to validate (dict or EnrichedPair).
            
        Returns:
            ValidationResult with errors and warnings.
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        # Check type
        if isinstance(data, EnrichedPair):
            return ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=[f"Expected dict or EnrichedPair, got {type(data).__name__}"],
                warnings=[],
            )
        
        # Required fields
        required_fields = {
            "pair_id", "id_a", "id_b", "code_a", "code_b",
            "label", "clone_type", "difficulty", "language",
        }
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            errors.append(f"Missing required fields: {missing_fields}")
        
        # Validate label
        if "label" in data:
            label = data["label"]
            if label not in (0, 1):
                errors.append(f"label must be 0 or 1, got {label}")
        
        # Validate clone_type
        if "clone_type" in data:
            clone_type = data["clone_type"]
            if clone_type not in (0, 1, 2, 3, 4):
                errors.append(f"clone_type must be 0-4, got {clone_type}")
        
        # Validate difficulty
        if "difficulty" in data:
            difficulty = data["difficulty"]
            if difficulty not in ("EASY", "MEDIUM", "HARD", "EXPERT"):
                errors.append(f"difficulty must be EASY/MEDIUM/HARD/EXPERT, got {difficulty}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def validate_batch(
        self,
        schema_name: str,
        items: List[Any],
    ) -> ValidationResult:
        """Validate a batch of items.
        
        Args:
            schema_name: Schema name to validate against.
            items: List of items to validate.
            
        Returns:
            ValidationResult with aggregated errors.
        """
        all_errors: List[str] = []
        all_warnings: List[str] = []
        
        for i, item in enumerate(items):
            if schema_name == "EvaluationResult":
                result = self.validate_evaluation_result(item)
            elif schema_name == "EnrichedPair":
                result = self.validate_enriched_pair(item)
            else:
                try:
                    registry.validate(schema_name, item)
                    result = ValidationResult(is_valid=True, errors=[], warnings=[])
                except ValidationError as e:
                    result = ValidationResult(
                        is_valid=False,
                        errors=[str(e)],
                        warnings=[],
                    )
            
            if not result.is_valid:
                all_errors.extend([f"Item {i}: {e}" for e in result.errors])
            all_warnings.extend([f"Item {i}: {w}" for w in result.warnings])
        
        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
        )


def validate_evaluation_result(data: Any) -> EvaluationResult:
    """Convenience function to validate and return EvaluationResult.
    
    Args:
        data: Data to validate.
        
    Returns:
        Validated EvaluationResult.
        
    Raises:
        ValidationError: If validation fails.
    """
    gate = ValidationGate()
    result = gate.validate_evaluation_result(data)
    result.raise_if_invalid()
    
    if isinstance(data, EvaluationResult):
        return data
    
    return EvaluationResult.from_dict(data)


def validate_enriched_pair(data: Any) -> EnrichedPair:
    """Convenience function to validate and return EnrichedPair.
    
    Args:
        data: Data to validate.
        
    Returns:
        Validated EnrichedPair.
        
    Raises:
        ValidationError: If validation fails.
    """
    gate = ValidationGate()
    result = gate.validate_enriched_pair(data)
    result.raise_if_invalid()
    
    if isinstance(data, EnrichedPair):
        return data
    
    return EnrichedPair(**data)