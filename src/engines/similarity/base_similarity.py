"""
Base similarity algorithm class.

All similarity algorithms should inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


from src.domain.models import Finding, EvidenceBlock


class BaseSimilarityAlgorithm(ABC):
    """
    Abstract base class for similarity algorithms.
    
    Each algorithm should implement the compare method to calculate
    similarity between two parsed code representations and return a Finding.
    """
    
    def __init__(self, name: str, methodology: str = ""):
        self.name = name
        self.methodology = methodology
    
    @abstractmethod
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Finding:
        """
        Compare two parsed code representations and return a Finding.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            A Finding object containing scores and evidence
        """
        pass
    
    def get_name(self) -> str:
        """
        Get the name of this algorithm.
        
        Returns:
            Algorithm name string
        """
        return self.name


class SimilarityEngine:
    """
    Engine that combines multiple similarity algorithms.
    """
    
    def __init__(self):
        self.algorithms: List[BaseSimilarityAlgorithm] = []
        self.weights: Dict[str, float] = {}
        self._deep_analysis_enabled = True
    
    def add_algorithm(self, algorithm: BaseSimilarityAlgorithm, weight: float = 1.0):
        """
        Add a similarity algorithm to the engine.
        
        Args:
            algorithm: Similarity algorithm instance
            weight: Weight for this algorithm in the final score (default 1.0)
        """
        self.algorithms.append(algorithm)
        self.weights[algorithm.get_name()] = weight
    
    def enable_deep_analysis(self, enabled: bool = True):
        """
        Enable or disable deep analysis features.
        
        Args:
            enabled: Whether to enable deep analysis
        """
        self._deep_analysis_enabled = enabled
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two parsed code representations using all algorithms.
        """
        if not self.algorithms:
            return {
                'overall_score': 0.0,
                'findings': [],
                'individual_scores': {},
                'confidence_interval': {'lower': 0.0, 'upper': 0.0, 'confidence': 0.0}
            }
        
        findings: List[Finding] = []
        individual_scores = {}
        weighted_sum = 0.0
        total_weight = 0.0
        
        for algorithm in self.algorithms:
            try:
                result = algorithm.compare(parsed_a, parsed_b)
                if isinstance(result, (int, float)):
                    finding = Finding(
                        engine=algorithm.get_name(),
                        score=float(result),
                        confidence=1.0,
                    )
                else:
                    finding = result
                findings.append(finding)
                
                score = max(0.0, min(1.0, finding.score))
                algorithm_name = algorithm.get_name()
                individual_scores[algorithm_name] = score
                
                weight = self.weights.get(algorithm_name, 1.0)
                weighted_sum += score * weight
                total_weight += weight
            except Exception as e:
                algorithm_name = algorithm.get_name()
                individual_scores[algorithm_name] = 0.0
        
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        scores = list(individual_scores.values())
        if len(scores) > 1:
            std_dev = np.std(scores)
            margin = 1.96 * std_dev / np.sqrt(len(scores))
            lower = max(0.0, overall_score - margin)
            upper = min(1.0, overall_score + margin)
        else:
            lower = upper = overall_score
        
        result = {
            'overall_score': overall_score,
            'findings': [f.to_dict() for f in findings],
            'individual_scores': individual_scores,
            'confidence_interval': {
                'lower': lower,
                'upper': upper,
                'confidence': 0.95
            }
        }
        
        # Add deep analysis if enabled
        if self._deep_analysis_enabled:
            try:
                from .deep_analysis import compare_codes_deep
                language = parsed_a.get('language', parsed_b.get('language', 'default'))
                deep_result = compare_codes_deep(parsed_a, parsed_b, language)
                result['deep_analysis'] = {
                    'tree_edit_distance': deep_result.get('tree_edit_distance', 1.0),
                    'tree_kernel_similarity': deep_result.get('tree_kernel_similarity', 0.0),
                    'normalized_ast_similarity': deep_result.get('normalized_ast_similarity', 0.0),
                    'cfg_similarity': deep_result.get('cfg_similarity', 0.0),
                    'clone_score': deep_result.get('clone_detection', {}).get('clone_score', 0.0),
                    'is_suspicious': deep_result.get('clone_detection', {}).get('is_suspicious', False)
                }
                
                # Incorporate deep analysis into overall score
                deep_score = deep_result.get('combined_score', 0.0)
                # Weight deep analysis at 50% of final score for better rename detection
                result['overall_score'] = overall_score * 0.5 + deep_score * 0.5
                result['deep_analysis_score'] = deep_score
            except ImportError:
                # Deep analysis module not available
                result['deep_analysis'] = None
        
        return result


# Cached singleton for built-in algorithm instances to avoid recreating on every call.
_builtins = None


def _get_builtin_algorithms() -> Dict[str, BaseSimilarityAlgorithm]:
    """Lazily create and cache all built-in algorithm instances."""
    global _builtins
    if _builtins is not None:
        return _builtins

    from .token_similarity import TokenSimilarity
    from .ngram_similarity import NgramSimilarity
    from .ast_similarity import ASTSimilarity
    from .winnowing_similarity import EnhancedWinnowingSimilarity
    from .execution_similarity import ExecutionSimilarity

    # Use UniXcoder (local GPU) — falls back to OpenAI EmbeddingSimilarity if unavailable
    try:
        from .unixcoder_similarity import UniXcoderSimilarity
        embedding_engine: BaseSimilarityAlgorithm = UniXcoderSimilarity()
    except ImportError:
        from .embedding_similarity import EmbeddingSimilarity
        embedding_engine = EmbeddingSimilarity()
    except Exception:
        from .embedding_similarity import EmbeddingSimilarity
        embedding_engine = EmbeddingSimilarity()

    _builtins = {
        "winnowing": EnhancedWinnowingSimilarity(),
        "token": TokenSimilarity(),
        "ngram": NgramSimilarity(),
        "ast": ASTSimilarity(),
        "execution": ExecutionSimilarity(),
        "embedding": embedding_engine,
    }

    # Graph-based similarity (CFG + DFG structural comparison) — optional
    try:
        from .graph_similarity import GraphSimilarity
        _builtins["graph"] = GraphSimilarity()
    except Exception:
        pass

    return _builtins


# Register built-in algorithms
def register_builtin_algorithms(engine: SimilarityEngine) -> None:
    """Register all built-in similarity algorithms with the engine.

    Shared algorithm instances are reused across calls via a module-level cache.

    Args:
        engine: SimilarityEngine instance to register algorithms with
    """
    default_weights: Dict[str, float] = {
        "winnowing": 1.5,
        "token": 1.0,
        "ngram": 1.0,
        "ast": 2.0,
        "execution": 1.5,
        "embedding": 0.5,
        "graph": 1.5,
    }

    for algo_name, algo in _get_builtin_algorithms().items():
        engine.add_algorithm(algo, weight=default_weights.get(algo_name, 1.0))
