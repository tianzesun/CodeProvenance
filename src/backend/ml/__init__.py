"""
ML Module - Model Definitions and Training/Inference Logic

This module contains ML model definitions and training/inference logic only.
It does NOT contain runtime execution logic or orchestration.

Responsibility: Model definitions, training, inference, model management
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import pickle
from pathlib import Path


class BaseModel(ABC):
    """Base class for all ML models."""
    
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path
        self.model = None
        self.is_trained = False
    
    @abstractmethod
    def train(self, data: Any, labels: Any) -> None:
        """Train the model."""
        pass
    
    @abstractmethod
    def predict(self, data: Any) -> Any:
        """Make predictions."""
        pass
    
    @abstractmethod
    def evaluate(self, data: Any, labels: Any) -> Dict[str, float]:
        """Evaluate model performance."""
        pass
    
    def save(self, path: Path) -> None:
        """Save model to disk."""
        with open(path, 'wb') as f:
            pickle.dump(self.model, f)
    
    def load(self, path: Path) -> None:
        """Load model from disk."""
        with open(path, 'rb') as f:
            self.model = pickle.load(f)
        self.is_trained = True


class ModelRegistry:
    """Registry for ML models."""
    
    def __init__(self):
        self._models: Dict[str, BaseModel] = {}
    
    def register(self, name: str, model: BaseModel) -> None:
        """Register a model."""
        self._models[name] = model
    
    def get(self, name: str) -> Optional[BaseModel]:
        """Get a model by name."""
        return self._models.get(name)
    
    def list_models(self) -> List[str]:
        """List all registered models."""
        return list(self._models.keys())


# Global model registry
registry = ModelRegistry()


def get_model(name: str) -> Optional[BaseModel]:
    """Get a model by name."""
    return registry.get(name)


def register_model(name: str):
    """Decorator to register a model."""
    def decorator(cls):
        registry.register(name, cls())
        return cls
    return decorator