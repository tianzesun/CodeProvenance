"""Dataset Validators for CodeProvenance.

Validates datasets against schema:
- DatasetValidator: Validates metadata and ground truth
- Validates metadata completeness
- Validates ground truth format

This module enables:
- Validation catches issues early
- Consistent metadata across datasets
- Cross-dataset comparison

Usage:
    from benchmark.datasets.validators import DatasetValidator

    errors = DatasetValidator.validate_metadata(metadata)
    if errors:
        print("Validation errors:", errors)
"""
from __future__ import annotations

from typing import Any, Dict, List

from benchmark.datasets.schema import DatasetMetadata


class DatasetValidator:
    """Validates datasets against schema.
    
    Provides static methods for validating dataset metadata
    and ground truth format.
    
    Usage:
        errors = DatasetValidator.validate_metadata(metadata)
        if errors:
            print("Validation errors:", errors)
    """
    
    @staticmethod
    def validate_metadata(metadata: DatasetMetadata) -> List[str]:
        """Validate metadata and return errors.
        
        Args:
            metadata: DatasetMetadata to validate.
            
        Returns:
            List of error strings (empty if valid).
        """
        errors = []
        
        if not metadata.name:
            errors.append("Dataset name is required")
        
        if not metadata.version:
            errors.append("Dataset version is required")
        
        if not metadata.language:
            errors.append("Language is required")
        
        if not metadata.clone_types:
            errors.append("At least one clone type is required")
        
        if metadata.size <= 0:
            errors.append("Dataset size must be positive")
        
        if not metadata.source:
            errors.append("Source is required")
        
        if not metadata.license:
            errors.append("License is required")
        
        if not metadata.ground_truth_format:
            errors.append("Ground truth format is required")
        elif metadata.ground_truth_format not in ["binary", "continuous", "multi-class"]:
            errors.append(
                f"Invalid ground truth format: {metadata.ground_truth_format}. "
                "Must be 'binary', 'continuous', or 'multi-class'"
            )
        
        if not metadata.description:
            errors.append("Description is required")
        
        return errors
    
    @staticmethod
    def validate_ground_truth(pairs: List[Dict[str, Any]]) -> List[str]:
        """Validate ground truth format.
        
        Args:
            pairs: List of pair dictionaries with 'label' field.
            
        Returns:
            List of error strings (empty if valid).
        """
        errors = []
        
        for i, pair in enumerate(pairs):
            if 'label' not in pair:
                errors.append(f"Pair {i} missing label")
            elif pair['label'] not in [0, 1]:
                errors.append(f"Pair {i} has invalid label: {pair['label']}")
        
        return errors
    
    @staticmethod
    def validate_clone_types(metadata: DatasetMetadata) -> List[str]:
        """Validate clone types.
        
        Args:
            metadata: DatasetMetadata to validate.
            
        Returns:
            List of error strings (empty if valid).
        """
        errors = []
        
        if not metadata.clone_types:
            errors.append("At least one clone type is required")
        
        return errors
    
    @staticmethod
    def validate_all(metadata: DatasetMetadata, pairs: List[Dict[str, Any]] = None) -> List[str]:
        """Validate all aspects of a dataset.
        
        Args:
            metadata: DatasetMetadata to validate.
            pairs: Optional list of pairs to validate.
            
        Returns:
            List of all error strings (empty if valid).
        """
        errors = []
        
        # Validate metadata
        errors.extend(DatasetValidator.validate_metadata(metadata))
        
        # Validate clone types
        errors.extend(DatasetValidator.validate_clone_types(metadata))
        
        # Validate ground truth if provided
        if pairs is not None:
            errors.extend(DatasetValidator.validate_ground_truth(pairs))
        
        return errors