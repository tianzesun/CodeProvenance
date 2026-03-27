"""
Base similarity algorithm class.

All similarity algorithms should inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


class BaseSimilarityAlgorithm(ABC):
    """
    Abstract base class for similarity algorithms.
    
    Each algorithm should implement the compare method to calculate
    similarity between two parsed code representations.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations and return similarity score.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
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
    
    def add_algorithm(self, algorithm: BaseSimilarityAlgorithm, weight: float = 1.0):
        """
        Add a similarity algorithm to the engine.
        
        Args:
            algorithm: Similarity algorithm instance
            weight: Weight for this algorithm in the final score (default 1.0)
        """
        self.algorithms.append(algorithm)
        self.weights[algorithm.get_name()] = weight
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two parsed code representations using all algorithms.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Dictionary containing:
            - overall_score: Weighted average of all algorithm scores
            - individual_scores: Dictionary of algorithm names to scores
            - confidence_interval: Estimated confidence interval
        """
        if not self.algorithms:
            return {
                'overall_score': 0.0,
                'individual_scores': {},
                'confidence_interval': {'lower': 0.0, 'upper': 0.0, 'confidence': 0.0}
            }
        
        individual_scores = {}
        weighted_sum = 0.0
        total_weight = 0.0
        
        for algorithm in self.algorithms:
            try:
                score = algorithm.compare(parsed_a, parsed_b)
                # Ensure score is in valid range
                score = max(0.0, min(1.0, score))
                algorithm_name = algorithm.get_name()
                individual_scores[algorithm_name] = score
                
                weight = self.weights.get(algorithm_name, 1.0)
                weighted_sum += score * weight
                total_weight += weight
            except Exception as e:
                # If an algorithm fails, log the error and continue with score 0
                algorithm_name = algorithm.get_name()
                individual_scores[algorithm_name] = 0.0
                # In a real implementation, you'd log this error
        
        # Calculate overall score
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Calculate simple confidence interval based on score variance
        scores = list(individual_scores.values())
        if len(scores) > 1:
            std_dev = np.std(scores)
            margin = 1.96 * std_dev / np.sqrt(len(scores))  # 95% confidence
            lower = max(0.0, overall_score - margin)
            upper = min(1.0, overall_score + margin)
        else:
            # Single algorithm or no variance
            lower = upper = overall_score
        
        return {
            'overall_score': overall_score,
            'individual_scores': individual_scores,
            'confidence_interval': {
                'lower': lower,
                'upper': upper,
                'confidence': 0.95  # Fixed for now
            }
        }


# Register built-in algorithms
def register_builtin_algorithms(engine: SimilarityEngine):
    """
    Register all built-in similarity algorithms with the engine.
    
    Args:
        engine: SimilarityEngine instance to register algorithms with
    """
    from .token_similarity import TokenSimilarity
    from .ngram_similarity import NgramSimilarity
    from .ast_similarity import ASTSimilarity
    from .winnowing_similarity import WinnowingSimilarity
    from .embedding_similarity import EmbeddingSimilarity
    
    # Add algorithms with default weights
    engine.add_algorithm(TokenSimilarity(), weight=1.0)
    engine.add_algorithm(NgramSimilarity(), weight=1.0)
    engine.add_algorithm(ASTSimilarity(), weight=1.5)  # Higher weight for AST
    engine.add_algorithm(WinnowingSimilarity(), weight=1.2)
    # Embedding similarity is optional and expensive, so lower weight by default
    engine.add_algorithm(EmbeddingSimilarity(), weight=0.5)
