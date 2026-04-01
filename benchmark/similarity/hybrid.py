"""Hybrid similarity algorithm combining token and AST similarity.

Provides weighted combination of multiple similarity measures.
"""
from typing import Dict, List, Any, Optional


class HybridSimilarityConfig:
    """Configuration for hybrid similarity."""
    def __init__(
        self,
        token_weight: float = 0.4,
        ast_weight: float = 0.4,
        style_weight: float = 0.2,
        token_k: int = 6,
        token_window: int = 4,
        ast_max_depth: int = 3
    ):
        self.token_weight = token_weight
        self.ast_weight = ast_weight
        self.style_weight = style_weight
        self.token_k = token_k
        self.token_window = token_window
        self.ast_max_depth = ast_max_depth


class HybridSimilarity:
    """Hybrid code similarity using weighted combination.
    
    Usage:
        config = HybridSimilarityConfig()
        hybrid = HybridSimilarity(config)
        score = hybrid.compare(code1, code2)
    """
    
    def __init__(self, config: Optional[HybridSimilarityConfig] = None):
        self.config = config or HybridSimilarityConfig()
    
    def compare(
        self,
        code1: str,
        code2: str,
        ast1: Any = None,
        ast2: Any = None
    ) -> float:
        """Calculate hybrid similarity score.
        
        Args:
            code1: First source code.
            code2: Second source code.
            ast1: First AST (optional).
            ast2: Second AST (optional).
            
        Returns:
            Similarity score between 0.0 and 1.0.
        """
        scores = {}
        weights = {}
        
        # Token-based similarity
        from benchmark.similarity.token_winnowing import token_similarity
        scores['token'] = token_similarity(
            code1, code2,
            k=self.config.token_k,
            window_size=self.config.token_window
        )
        weights['token'] = self.config.token_weight
        
        # AST-based similarity (if ASTs provided)
        if ast1 is not None and ast2 is not None:
            from benchmark.similarity.ast_subtree import compare_ast
            scores['ast'] = compare_ast(ast1, ast2, self.config.ast_max_depth)
            weights['ast'] = self.config.ast_weight
        else:
            scores['ast'] = 0.0
            weights['ast'] = 0.0
        
        return self._weighted_sum(scores, weights)
    
    def _weighted_sum(
        self,
        scores: Dict[str, float],
        weights: Dict[str, float]
    ) -> float:
        """Calculate weighted sum of scores.
        
        Args:
            scores: Dict of metric name -> score.
            weights: Dict of metric name -> weight.
            
        Returns:
            Weighted combined score.
        """
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0
        
        return sum(scores[k] * weights.get(k, 0) for k in scores) / total_weight
    
    def get_component_scores(
        self,
        code1: str,
        code2: str,
        ast1: Any = None,
        ast2: Any = None
    ) -> Dict[str, float]:
        """Get individual component scores.
        
        Args:
            code1: First source code.
            code2: Second source code.
            ast1: First AST.
            ast2: Second AST.
            
        Returns:
            Dict of component name -> score.
        """
        from benchmark.similarity.token_winnowing import token_similarity
        
        result = {
            'token': token_similarity(
                code1, code2,
                k=self.config.token_k,
                window_size=self.config.token_window
            )
        }
        
        if ast1 is not None and ast2 is not None:
            from benchmark.similarity.ast_subtree import compare_ast
            result['ast'] = compare_ast(ast1, ast2, self.config.ast_max_depth)
        else:
            result['ast'] = None
        
        return result