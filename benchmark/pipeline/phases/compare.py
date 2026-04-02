"""Phase 4: Similarity Computation.

Computes similarity between code representations:
- Token-based similarity
- AST-based similarity
- Hybrid similarity

Input: List[IntermediateRepresentation] pairs
Output: List[ComparisonResult]

Usage:
    from benchmark.pipeline.phases.compare import ComparisonPhase

    phase = ComparisonPhase()
    results = phase.execute(representation_pairs, config)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ComparisonResult:
    """Result of a similarity comparison.
    
    Attributes:
        code_a_id: ID of first code.
        code_b_id: ID of second code.
        similarity_score: Similarity score in [0, 1].
        engine_name: Name of engine used.
        component_scores: Per-component similarity scores.
        metadata: Additional metadata.
    """
    code_a_id: str
    code_b_id: str
    similarity_score: float
    engine_name: str = ""
    component_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_clone(self) -> bool:
        """Check if pair is a clone (score >= 0.5)."""
        return self.similarity_score >= 0.5


class ComparisonPhase:
    """Phase 4: Similarity Computation.
    
    This phase is responsible for:
    - Computing similarity between code pairs
    - Using configured similarity engine
    - Recording component scores
    
    Input: List of (representation_a, representation_b, engine) tuples
    Output: List[ComparisonResult]
    
    Usage:
        phase = ComparisonPhase()
        results = phase.execute(representation_pairs, config)
    """
    
    def execute(
        self,
        representation_pairs: List[Tuple[Any, Any, Any]],
        config: Dict[str, Any],
    ) -> List[ComparisonResult]:
        """Execute comparison phase.
        
        Args:
            representation_pairs: List of (rep_a, rep_b, engine) tuples.
            config: Configuration for comparison.
                - threshold: Similarity threshold (default: 0.5)
                - record_components: Record component scores (default: True)
            
        Returns:
            List of ComparisonResult objects.
        """
        threshold = config.get('threshold', 0.5)
        record_components = config.get('record_components', True)
        
        results: List[ComparisonResult] = []
        
        for rep_a, rep_b, engine in representation_pairs:
            # Get code content
            code_a = getattr(rep_a, 'normalized_content', str(rep_a))
            code_b = getattr(rep_b, 'normalized_content', str(rep_b))
            
            # Get code IDs
            code_a_id = getattr(rep_a, 'code_id', 'unknown_a')
            code_b_id = getattr(rep_b, 'code_id', 'unknown_b')
            
            # Compute similarity
            similarity_score = engine.compare(code_a, code_b)
            
            # Get engine name
            engine_name = self._get_engine_name(engine)
            
            # Compute component scores if enabled
            component_scores = {}
            if record_components:
                component_scores = self._compute_component_scores(
                    code_a, code_b, config
                )
            
            results.append(ComparisonResult(
                code_a_id=code_a_id,
                code_b_id=code_b_id,
                similarity_score=similarity_score,
                engine_name=engine_name,
                component_scores=component_scores,
                metadata={
                    'threshold': threshold,
                    'code_a_length': len(code_a),
                    'code_b_length': len(code_b),
                },
            ))
        
        return results
    
    def _get_engine_name(self, engine: Any) -> str:
        """Get engine name from engine object.
        
        Args:
            engine: Similarity engine.
            
        Returns:
            Engine name string.
        """
        if hasattr(engine, 'name'):
            name_attr = getattr(engine, 'name')
            return name_attr() if callable(name_attr) else name_attr
        return type(engine).__name__
    
    def _compute_component_scores(
        self,
        code_a: str,
        code_b: str,
        config: Dict[str, Any],
    ) -> Dict[str, float]:
        """Compute per-component similarity scores.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            config: Configuration.
            
        Returns:
            Dictionary of component scores.
        """
        component_scores = {}
        
        # Token similarity
        component_scores['token'] = self._token_similarity(code_a, code_b)
        
        # Structure similarity
        component_scores['structure'] = self._structure_similarity(code_a, code_b)
        
        # Length similarity
        component_scores['length'] = self._length_similarity(code_a, code_b)
        
        return component_scores
    
    def _token_similarity(self, code_a: str, code_b: str) -> float:
        """Compute token-based similarity.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Token similarity score [0, 1].
        """
        tokens_a = set(code_a.split())
        tokens_b = set(code_b.split())
        
        if not tokens_a or not tokens_b:
            return 0.0
        
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        
        return len(intersection) / len(union) if union else 0.0
    
    def _structure_similarity(self, code_a: str, code_b: str) -> float:
        """Compute structure-based similarity.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Structure similarity score [0, 1].
        """
        # Simple structure comparison based on indentation patterns
        lines_a = [line for line in code_a.split('\n') if line.strip()]
        lines_b = [line for line in code_b.split('\n') if line.strip()]
        
        if not lines_a or not lines_b:
            return 0.0
        
        # Compare indentation patterns
        indent_a = [len(line) - len(line.lstrip()) for line in lines_a]
        indent_b = [len(line) - len(line.lstrip()) for line in lines_b]
        
        # Normalize
        max_indent = max(max(indent_a) if indent_a else 0, max(indent_b) if indent_b else 0)
        if max_indent == 0:
            return 1.0
        
        norm_a = [i / max_indent for i in indent_a]
        norm_b = [i / max_indent for i in indent_b]
        
        # Compute similarity
        min_len = min(len(norm_a), len(norm_b))
        if min_len == 0:
            return 0.0
        
        differences = sum(abs(norm_a[i] - norm_b[i]) for i in range(min_len))
        return 1.0 - (differences / min_len)
    
    def _length_similarity(self, code_a: str, code_b: str) -> float:
        """Compute length-based similarity.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Length similarity score [0, 1].
        """
        len_a = len(code_a)
        len_b = len(code_b)
        
        if len_a == 0 and len_b == 0:
            return 1.0
        
        max_len = max(len_a, len_b)
        min_len = min(len_a, len_b)
        
        return min_len / max_len if max_len > 0 else 0.0