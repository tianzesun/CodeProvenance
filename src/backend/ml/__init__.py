"""
ML Module - Model Definitions and Training/Inference Logic

This module contains ML model definitions and training/inference logic only.
It does NOT contain runtime execution logic or orchestration.

Responsibility: Model definitions, training, inference, model management
"""

import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseModel(ABC):
    """Base class for all ML models."""

    def __init__(self, model_path: Path | None = None):
        self.model_path = model_path
        self.model = None
        self.is_trained = False

    @abstractmethod
    def train(self, data: Any, labels: Any) -> None:
        """Train the model."""

    @abstractmethod
    def predict(self, data: Any) -> Any:
        """Make predictions."""

    @abstractmethod
    def evaluate(self, data: Any, labels: Any) -> dict[str, float]:
        """Evaluate model performance."""

    def save(self, path: Path) -> None:
        """Save model to disk."""
        with open(path, "wb") as f:
            pickle.dump(self.model, f)

    def load(self, path: Path) -> None:
        """Load model from disk."""
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        self.is_trained = True


class ModelRegistry:
    """Registry for ML models."""

    def __init__(self):
        self._models: dict[str, BaseModel] = {}

    def register(self, name: str, model: BaseModel) -> None:
        """Register a model."""
        self._models[name] = model

    def get(self, name: str) -> BaseModel | None:
        """Get a model by name."""
        return self._models.get(name)

    def list_models(self) -> list[str]:
        """List all registered models."""
        return list(self._models.keys())


# Global model registry
registry = ModelRegistry()


def get_model(name: str) -> BaseModel | None:
    """Get a model by name."""
    return registry.get(name)


def register_model(name: str):
    """Decorator to register a model."""

    def decorator(cls):
        registry.register(name, cls())
        return cls

    return decorator
