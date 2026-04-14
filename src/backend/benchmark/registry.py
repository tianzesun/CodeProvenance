"""Engine registry for benchmark system.

All detection engines MUST implement the DetectionEngine interface.
This ensures results are comparable and reproducible.

Required engine contract:
- name() -> str: unique engine identifier
- compare(code1, code2) -> float: similarity in [0, 1]
"""
from abc import ABC, abstractmethod
from typing import Dict, Type, Any, Optional


class DetectionEngine(ABC):
    """Abstract base class for all detection engines.
    
    ALL engines must implement this interface to be registered.
    This guarantees:
    1. Consistent API across engines
    2. Comparable results
    3. Reproducible experiments
    
    Usage:
        class MyEngine(DetectionEngine):
            def name(self) -> str:
                return "my_engine_v1"
            
            def compare(self, code1: str, code2: str) -> float:
                # Return similarity in [0, 1]
                return 0.85
    """
    
    @abstractmethod
    def name(self) -> str:
        """Return unique engine name.
        
        Returns:
            Unique engine identifier (e.g., "token_v1", "ast_hybrid").
        """
        pass
    
    @abstractmethod
    def compare(self, code1: str, code2: str) -> float:
        """Compare two code snippets and return similarity score.
        
        MANDATORY CONTRACT:
        - Input: two normalized code strings
        - Output: similarity score in [0.0, 1.0]
        - 0.0 means completely different
        - 1.0 means identical
        
        Args:
            code1: First normalized code string.
            code2: Second normalized code string.
            
        Returns:
            Similarity score between 0.0 and 1.0.
            
        Raises:
            ValueError: If score is outside [0, 1].
        """
        pass
    
    def _validate_score(self, score: float) -> float:
        """Validate similarity score is in [0, 1].
        
        Args:
            score: Raw similarity score.
            
        Returns:
            Clamped score in [0, 1].
            
        Raises:
            ValueError: If score is NaN.
        """
        if score != score:  # NaN check
            raise ValueError("Similarity score cannot be NaN")
        return max(0.0, min(1.0, score))


class EngineRegistry:
    """Central registry for detection engines.
    
    Accepts engines that implement either:
    - DetectionEngine (legacy abstract interface)
    - BaseSimilarityEngine (new canonical interface)
    
    Usage:
        registry = EngineRegistry()
        registry.register("similarity", SimilarityEngine)
        engine = registry.get_instance("similarity")
        score = engine.compare(code1, code2)
    """
    
    def __init__(self):
        self._engines: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
    
    def register(
        self,
        name: str,
        engine_class: Type,
        config: Optional[dict] = None
    ) -> None:
        """Register a detection engine.
        
        Args:
            name: Unique engine identifier.
            engine_class: Engine class (must have compare method).
            config: Optional config passed to constructor.
            
        Raises:
            TypeError: If engine_class does not have a compare method.
        """
        # Check for either DetectionEngine or BaseSimilarityEngine interface
        from src.backend.benchmark.similarity.base_engine import BaseSimilarityEngine
        has_abstract = (
            issubclass(engine_class, DetectionEngine)
            if isinstance(engine_class, type) and issubclass(engine_class, DetectionEngine)
            else False
        )
        has_concrete = (
            issubclass(engine_class, BaseSimilarityEngine)
            if isinstance(engine_class, type) and issubclass(engine_class, BaseSimilarityEngine)
            else False
        )
        
        # Allow BaseSimilarityEngine or DetectionEngine subclasses
        if not (has_abstract or has_concrete):
            # Fallback: check if it has compare method (duck typing for adapters)
            if not hasattr(engine_class, 'compare'):
                raise TypeError(
                    f"Engine '{name}' must have a 'compare' method. "
                    f"Got: {engine_class}"
                )
        
        self._engines[name] = engine_class
        if config:
            self._instances[name] = engine_class(**config)
    
    def get(self, name: str) -> Type[DetectionEngine]:
        """Get engine class by name.
        
        Args:
            name: Registered engine name.
            
        Returns:
            Engine class.
            
        Raises:
            KeyError: If engine not found.
        """
        if name not in self._engines:
            raise KeyError(
                f"Engine '{name}' not found. "
                f"Available: {list(self._engines.keys())}"
            )
        return self._engines[name]
    
    def get_instance(self, name: str, **kwargs) -> DetectionEngine:
        """Get engine instance by name.
        
        Args:
            name: Registered engine name.
            **kwargs: Constructor arguments.
            
        Returns:
            Engine instance.
        """
        if name not in self._instances:
            engine_class = self.get(name)
            self._instances[name] = engine_class(**kwargs)
        return self._instances[name]
    
    def list_engines(self) -> Dict[str, Type[DetectionEngine]]:
        """List all registered engines.
        
        Returns:
            Dict mapping engine name to class.
        """
        return dict(self._engines)
    
    def has(self, name: str) -> bool:
        """Check if engine is registered.
        
        Args:
            name: Engine name.
            
        Returns:
            True if engine is registered.
        """
        return name in self._engines


# Global singleton
registry = EngineRegistry()


def register_engine(name: str, config: Optional[dict] = None):
    """Decorator for registering engines.
    
    Usage:
        @register_engine("token_winnowing")
        class TokenEngine(DetectionEngine):
            def name(self) -> str:
                return "token_winnowing"
            def compare(self, code1, code2) -> float:
                return token_similarity(code1, code2)
    """
    def decorator(engine_class: Type[DetectionEngine]) -> Type[DetectionEngine]:
        registry.register(name, engine_class, config)
        return engine_class
    return decorator