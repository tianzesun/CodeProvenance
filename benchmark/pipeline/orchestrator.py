"""Pipeline Orchestrator.

Coordinates execution of all pipeline phases:
- IngestionPhase: Phase 1 - File ingestion
- NormalizationPhase: Phase 2 - Code normalization
- RepresentationPhase: Phase 3 - IR generation
- ComparisonPhase: Phase 4 - Similarity computation
- AggregationPhase: Phase 5 - Result aggregation
- EvaluationPhase: Phase 6 - Metric evaluation
- ReportingPhase: Phase 7 - Report generation

Input: Configuration
Output: Final results

Usage:
    from benchmark.pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config)
    results = orchestrator.execute(inputs)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from benchmark.pipeline.phases import (
    IngestionPhase,
    NormalizationPhase,
    RepresentationPhase,
    ComparisonPhase,
    AggregationPhase,
    EvaluationPhase,
    ReportingPhase,
)


@dataclass
class PipelineResult:
    """Final pipeline result.
    
    Attributes:
        ingestion_result: Result from ingestion phase.
        normalization_result: Result from normalization phase.
        representation_result: Result from representation phase.
        comparison_result: Result from comparison phase.
        aggregation_result: Result from aggregation phase.
        evaluation_result: Result from evaluation phase.
        reporting_result: Result from reporting phase.
        metadata: Additional metadata.
    """
    ingestion_result: Any = None
    normalization_result: Any = None
    representation_result: Any = None
    comparison_result: Any = None
    aggregation_result: Any = None
    evaluation_result: Any = None
    reporting_result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineOrchestrator:
    """Coordinates execution of all pipeline phases.
    
    This orchestrator manages the complete pipeline execution:
    1. Ingestion: Load and validate input files
    2. Normalization: Normalize code
    3. Representation: Generate IR
    4. Comparison: Compute similarity
    5. Aggregation: Aggregate results
    6. Evaluation: Compute metrics
    7. Reporting: Generate reports
    
    Input: Configuration dictionary
    Output: PipelineResult with all phase results
    
    Usage:
        orchestrator = PipelineOrchestrator(config)
        results = orchestrator.execute(inputs)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize pipeline orchestrator.
        
        Args:
            config: Pipeline configuration.
        """
        self.config = config
        
        # Initialize phases
        self.phases = [
            IngestionPhase(),
            NormalizationPhase(),
            RepresentationPhase(),
            ComparisonPhase(),
            AggregationPhase(),
            EvaluationPhase(),
            ReportingPhase(),
        ]
    
    def execute(self, inputs: List[str]) -> PipelineResult:
        """Execute full pipeline.
        
        Args:
            inputs: List of input file paths.
            
        Returns:
            PipelineResult with all phase results.
        """
        data = {"inputs": inputs}
        result = PipelineResult()
        
        # Phase 1: Ingestion
        ingestion_phase = self.phases[0]
        ingestion_config = self.config.get('ingestion', {})
        ingestion_result = ingestion_phase.execute(inputs, ingestion_config)
        result.ingestion_result = ingestion_result
        
        # Phase 2: Normalization
        normalization_phase = self.phases[1]
        normalization_config = self.config.get('normalization', {})
        normalization_result = normalization_phase.execute(
            ingestion_result, normalization_config
        )
        result.normalization_result = normalization_result
        
        # Phase 3: Representation
        representation_phase = self.phases[2]
        representation_config = self.config.get('representation', {})
        representation_result = representation_phase.execute(
            normalization_result, representation_config
        )
        result.representation_result = representation_result
        
        # Phase 4: Comparison
        comparison_phase = self.phases[3]
        comparison_config = self.config.get('comparison', {})
        
        # Create representation pairs
        representation_pairs = self._create_representation_pairs(
            representation_result, comparison_config
        )
        comparison_result = comparison_phase.execute(
            representation_pairs, comparison_config
        )
        result.comparison_result = comparison_result
        
        # Phase 5: Aggregation
        aggregation_phase = self.phases[4]
        aggregation_config = self.config.get('aggregation', {})
        aggregation_result = aggregation_phase.execute(
            comparison_result, aggregation_config
        )
        result.aggregation_result = aggregation_result
        
        # Phase 6: Evaluation
        evaluation_phase = self.phases[5]
        evaluation_config = self.config.get('evaluation', {})
        evaluation_result = evaluation_phase.execute(
            aggregation_result, evaluation_config
        )
        result.evaluation_result = evaluation_result
        
        # Phase 7: Reporting
        reporting_phase = self.phases[6]
        reporting_config = self.config.get('reporting', {})
        reporting_result = reporting_phase.execute(
            evaluation_result, reporting_config
        )
        result.reporting_result = reporting_result
        
        return result
    
    def _create_representation_pairs(
        self,
        representations: List[Any],
        config: Dict[str, Any],
    ) -> List[tuple]:
        """Create pairs of representations for comparison.
        
        Args:
            representations: List of representations.
            config: Configuration.
            
        Returns:
            List of (rep_a, rep_b, engine) tuples.
        """
        from benchmark.registry import registry
        
        pairs = []
        engine_name = config.get('engine', 'codeprovenance:v1')
        engine = registry.get_instance(engine_name)
        
        # Create all pairs
        for i in range(len(representations)):
            for j in range(i + 1, len(representations)):
                pairs.append((
                    representations[i],
                    representations[j],
                    engine,
                ))
        
        return pairs