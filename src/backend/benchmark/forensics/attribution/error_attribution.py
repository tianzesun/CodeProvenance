"""Error Attribution Model for code similarity detection.

Wraps ErrorAnalyzer with additional functionality for diagnostic benchmarking.
Provides component-level error attribution and clone type sensitivity analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.backend.benchmark.forensics.attribution.error_analysis import ErrorAnalyzer, ErrorReport


@dataclass
class ErrorAttributionReport:
    """Error attribution report with component analysis.
    
    Attributes:
        true_positives: Number of true positives.
        false_positives: Number of false positives.
        false_negatives: Number of false negatives.
        true_negatives: Number of true negatives.
        primary_cause_distribution: Distribution of primary failure causes.
        component_losses: Loss metrics per component.
    """
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    primary_cause_distribution: Dict[str, int] = field(default_factory=dict)
    component_losses: Dict[str, float] = field(default_factory=dict)


class ErrorAttributionModel:
    """Error attribution model for diagnostic analysis.
    
    Provides component-level error attribution and clone type sensitivity.
    """
    
    def __init__(self):
        """Initialize error attribution model."""
        self.error_analyzer = ErrorAnalyzer()
    
    def analyze(
        self,
        pairs: List[Any],
        engine: Any,
        threshold: float = 0.5,
    ) -> ErrorAttributionReport:
        """Analyze errors from benchmark pairs.
        
        Args:
            pairs: List of code pairs with labels.
            engine: Similarity engine to use.
            threshold: Decision threshold.
            
        Returns:
            ErrorAttributionReport with analysis.
        """
        # Convert pairs to results format expected by ErrorAnalyzer
        results = []
        for pair in pairs:
            code_a = getattr(pair, 'code_a', '')
            code_b = getattr(pair, 'code_b', '')
            label = getattr(pair, 'label', 0)
            clone_type = getattr(pair, 'clone_type', 0)
            
            # Get similarity score from engine
            try:
                score = engine.compare(code_a, code_b)
            except Exception:
                score = 0.0
            
            results.append((score, label, clone_type, code_a, code_b))
        
        # Analyze errors
        error_report = self.error_analyzer.analyze(
            engine_name=getattr(engine, 'name', 'unknown'),
            dataset_name='synthetic',
            results=results,
            threshold=threshold,
        )
        
        # Build attribution report
        report = ErrorAttributionReport(
            true_positives=error_report.true_positives,
            false_positives=error_report.false_positives,
            false_negatives=error_report.false_negatives,
            true_negatives=error_report.true_negatives,
        )
        
        # Compute primary cause distribution
        report.primary_cause_distribution = self._compute_primary_causes(error_report)
        
        # Compute component losses
        report.component_losses = self._compute_component_losses(results, engine)
        
        return report
    
    def compute_clone_type_sensitivity(
        self,
        pairs: List[Any],
        engines: Dict[str, Any],
        threshold: float = 0.5,
    ) -> Dict[str, Dict[str, float]]:
        """Compute sensitivity matrix by clone type.
        
        Args:
            pairs: List of code pairs with labels.
            engines: Dictionary of engine name to engine instance.
            threshold: Decision threshold.
            
        Returns:
            Dictionary mapping engine name to clone type recall scores.
        """
        sensitivity_matrix = {}
        
        for engine_name, engine in engines.items():
            type_recalls = {}
            
            # Group pairs by clone type
            type_pairs: Dict[int, List[Any]] = {}
            for pair in pairs:
                clone_type = getattr(pair, 'clone_type', 0)
                type_pairs.setdefault(clone_type, []).append(pair)
            
            # Compute recall per clone type
            for clone_type, type_pair_list in type_pairs.items():
                tp = 0
                fn = 0
                
                for pair in type_pair_list:
                    code_a = getattr(pair, 'code_a', '')
                    code_b = getattr(pair, 'code_b', '')
                    label = getattr(pair, 'label', 0)
                    
                    try:
                        score = engine.compare(code_a, code_b)
                        predicted = 1 if score >= threshold else 0
                        
                        if predicted == 1 and label == 1:
                            tp += 1
                        elif predicted == 0 and label == 1:
                            fn += 1
                    except Exception:
                        fn += 1
                
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                type_name = f"type_{clone_type}" if clone_type > 0 else "non_clone"
                type_recalls[type_name] = recall
            
            sensitivity_matrix[engine_name] = type_recalls
        
        return sensitivity_matrix
    
    def _compute_primary_causes(self, error_report: ErrorReport) -> Dict[str, int]:
        """Compute primary failure causes from error report.
        
        Args:
            error_report: Error report from ErrorAnalyzer.
            
        Returns:
            Dictionary of cause name to count.
        """
        causes: Dict[str, int] = {}
        
        # From characteristic errors
        for name, cat in error_report.errors_by_characteristic.items():
            causes[name] = cat.count
        
        # From type errors
        for name, cat in error_report.errors_by_type.items():
            causes[f"clone_type_{name}"] = cat.count
        
        return causes
    
    def _compute_component_losses(
        self,
        results: List[Tuple[float, int, int, str, str]],
        engine: Any,
    ) -> Dict[str, float]:
        """Compute loss metrics per component.
        
        Args:
            results: List of (score, label, clone_type, code_a, code_b).
            engine: Similarity engine.
            
        Returns:
            Dictionary of component name to loss value.
        """
        losses: Dict[str, float] = {}
        
        # Basic loss: mean absolute error
        total_error = 0.0
        for score, label, _, _, _ in results:
            total_error += abs(score - label)
        
        losses["overall"] = total_error / len(results) if results else 0.0
        
        # Component-specific losses (if engine has components)
        if hasattr(engine, 'token_weight'):
            losses["token"] = losses["overall"] * (1 - getattr(engine, 'token_weight', 0.5))
        if hasattr(engine, 'ast_weight'):
            losses["ast"] = losses["overall"] * (1 - getattr(engine, 'ast_weight', 0.5))
        
        return losses