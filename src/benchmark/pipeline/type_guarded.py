"""Type-Guarded Pipeline - No dict passing, explicit types everywhere.

This module enforces type-safe pipeline execution.
No raw dicts passed between modules.
No implicit fields.
No partial objects.

Every pipeline stage must use typed contracts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from contracts import (
    ValidationGate,
    ValidationResult,
    validate_evaluation_result,
    validate_enriched_pair,
)
from contracts.registry import registry
from src.benchmark.contracts.evaluation_result import EvaluationResult, EnrichedPair

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class PipelineContext:
    """Typed context for pipeline execution.
    
    Attributes:
        config: Configuration dictionary.
        metadata: Additional metadata.
    """
    config: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        return self.config.get(key, default)


class TypedStage(ABC, Generic[T, U]):
    """Base class for typed pipeline stages.
    
    Every stage must:
    1. Accept typed input
    2. Return typed output
    3. Validate at boundaries
    """
    
    @property
    @abstractmethod
    def input_schema(self) -> str:
        """Return input schema name."""
        pass
    
    @property
    @abstractmethod
    def output_schema(self) -> str:
        """Return output schema name."""
        pass
    
    @abstractmethod
    def execute(self, input_data: T, context: PipelineContext) -> U:
        """Execute the stage."""
        pass
    
    def validate_input(self, data: Any) -> T:
        """Validate input data."""
        return registry.validate(self.input_schema, data)
    
    def validate_output(self, data: Any) -> U:
        """Validate output data."""
        return registry.validate(self.output_schema, data)


class EvaluationStage(TypedStage[EnrichedPair, EvaluationResult]):
    """Evaluation stage - evaluates a code pair."""
    
    @property
    def input_schema(self) -> str:
        return "EnrichedPair"
    
    @property
    def output_schema(self) -> str:
        return "EvaluationResult"
    
    def __init__(self, engine: Any) -> None:
        """Initialize with engine."""
        self.engine = engine
    
    def execute(self, input_data: EnrichedPair, context: PipelineContext) -> EvaluationResult:
        """Execute evaluation."""
        threshold = context.get("threshold", 0.75)
        raw_result = self.engine.evaluate(input_data)
        validated = validate_evaluation_result(raw_result)
        return validated


class TypedPipeline:
    """Type-safe pipeline executor.
    
    This enforces:
    - No dict passing between stages
    - Explicit typing at every boundary
    - Validation at every stage
    """
    
    def __init__(self) -> None:
        """Initialize pipeline."""
        self.stages: List[TypedStage[Any, Any]] = []
        self.validation_gate = ValidationGate()
    
    def add_stage(self, stage: TypedStage[Any, Any]) -> TypedPipeline:
        """Add a stage to the pipeline."""
        self.stages.append(stage)
        return self
    
    def execute(self, input_data: Any, context: PipelineContext) -> Any:
        """Execute the pipeline."""
        current_data = input_data
        
        for stage in self.stages:
            validated_input = stage.validate_input(current_data)
            output = stage.execute(validated_input, context)
            validated_output = stage.validate_output(output)
            current_data = validated_output
        
        return current_data


class AdapterIsolationLayer:
    """Adapter isolation - translates external chaos to internal structure.
    
    Adapters are TRANSLATORS, not producers.
    They convert external tool output to canonical EvaluationResult.
    """
    
    def __init__(self, engine_name: str, threshold: float = 0.75) -> None:
        """Initialize adapter.
        
        Args:
            engine_name: Name of the engine.
            threshold: Decision threshold.
        """
        self.engine_name = engine_name
        self.threshold = threshold
    
    def translate(
        self,
        pair: EnrichedPair,
        raw_score: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Translate raw score to EvaluationResult.
        
        This is the ONLY way to create EvaluationResult from external tools.
        
        Args:
            pair: The evaluated pair.
            raw_score: Raw similarity score (will be normalized).
            metadata: Additional metadata.
            
        Returns:
            Canonical EvaluationResult.
        """
        # Normalize score to [0, 1]
        normalized_score = max(0.0, min(1.0, raw_score))
        
        # Compute decision
        decision = normalized_score >= self.threshold
        
        # Compute confidence (can be overridden)
        confidence = normalized_score
        
        return EvaluationResult(
            pair_id=pair.pair_id,
            score=normalized_score,
            decision=decision,
            confidence=confidence,
            engine=self.engine_name,
            metadata=metadata or {},
        )


def create_typed_evaluation_pipeline(engine: Any) -> TypedPipeline:
    """Create a typed evaluation pipeline.
    
    Args:
        engine: Similarity engine.
        
    Returns:
        Typed pipeline.
    """
    pipeline = TypedPipeline()
    pipeline.add_stage(EvaluationStage(engine))
    return pipeline
