"""Phase 5: Result Aggregation.

Aggregates comparison results:
- Group results by engine
- Compute statistics
- Prepare for evaluation

Input: List[ComparisonResult]
Output: AggregatedResult

Usage:
    from benchmark.pipeline.phases.aggregate import AggregationPhase

    phase = AggregationPhase()
    aggregated = phase.execute(comparison_results, config)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import defaultdict


@dataclass
class AggregatedResult:
    """Aggregated comparison results.
    
    Attributes:
        total_pairs: Total number of pairs compared.
        results_by_engine: Results grouped by engine.
        statistics: Aggregated statistics.
        metadata: Additional metadata.
    """
    total_pairs: int = 0
    results_by_engine: Dict[str, List[Any]] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_engine_results(self, engine_name: str) -> List[Any]:
        """Get results for a specific engine.
        
        Args:
            engine_name: Name of engine.
            
        Returns:
            List of results for the engine.
        """
        return self.results_by_engine.get(engine_name, [])


class AggregationPhase:
    """Phase 5: Result Aggregation.
    
    This phase is responsible for:
    - Grouping results by engine
    - Computing aggregate statistics
    - Preparing data for evaluation
    
    Input: List[ComparisonResult] from comparison phase
    Output: AggregatedResult ready for evaluation
    
    Usage:
        phase = AggregationPhase()
        aggregated = phase.execute(comparison_results, config)
    """
    
    def execute(
        self,
        comparison_results: List[Any],
        config: Dict[str, Any],
    ) -> AggregatedResult:
        """Execute aggregation phase.
        
        Args:
            comparison_results: List of ComparisonResult objects.
            config: Configuration for aggregation.
                - group_by_engine: Group results by engine (default: True)
                - compute_statistics: Compute statistics (default: True)
            
        Returns:
            AggregatedResult object.
        """
        group_by_engine = config.get('group_by_engine', True)
        compute_statistics = config.get('compute_statistics', True)
        
        # Group by engine
        results_by_engine: Dict[str, List[Any]] = defaultdict(list)
        for result in comparison_results:
            engine_name = getattr(result, 'engine_name', 'unknown')
            results_by_engine[engine_name].append(result)
        
        # Compute statistics
        statistics = {}
        if compute_statistics:
            statistics = self._compute_statistics(comparison_results)
        
        return AggregatedResult(
            total_pairs=len(comparison_results),
            results_by_engine=dict(results_by_engine),
            statistics=statistics,
            metadata={
                'engines': list(results_by_engine.keys()),
            },
        )
    
    def _compute_statistics(self, results: List[Any]) -> Dict[str, Any]:
        """Compute aggregate statistics.
        
        Args:
            results: List of comparison results.
            
        Returns:
            Dictionary of statistics.
        """
        if not results:
            return {}
        
        scores = [getattr(r, 'similarity_score', 0.0) for r in results]
        
        return {
            'total_pairs': len(results),
            'mean_score': sum(scores) / len(scores) if scores else 0.0,
            'min_score': min(scores) if scores else 0.0,
            'max_score': max(scores) if scores else 0.0,
            'clones_detected': sum(1 for s in scores if s >= 0.5),
            'non_clones': sum(1 for s in scores if s < 0.5),
        }