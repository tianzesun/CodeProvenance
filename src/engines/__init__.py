"""
Engines Module - Runtime Execution Engine

This module provides runtime execution logic only.
It does NOT contain business logic, algorithms, or ML models.

Responsibility: Scheduler, execution context, parallelism
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod


class ExecutionEngine(ABC):
    """Base class for all execution engines."""
    
    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task."""
        pass
    
    @abstractmethod
    def get_status(self) -> str:
        """Get engine status."""
        pass


class EngineRegistry:
    """Registry for execution engines."""
    
    def __init__(self):
        self._engines: Dict[str, ExecutionEngine] = {}
    
    def register(self, name: str, engine: ExecutionEngine) -> None:
        """Register an execution engine."""
        self._engines[name] = engine
    
    def get(self, name: str) -> Optional[ExecutionEngine]:
        """Get an execution engine by name."""
        return self._engines.get(name)
    
    def list_engines(self) -> List[str]:
        """List all registered engines."""
        return list(self._engines.keys())


# Global engine registry
registry = EngineRegistry()


def get_engine(name: str) -> Optional[ExecutionEngine]:
    """Get an execution engine by name."""
    return registry.get(name)


def register_engine(name: str):
    """Decorator to register an execution engine."""
    def decorator(cls):
        registry.register(name, cls())
        return cls
    return decorator