"""Engine Registry - formal plugin system."""

from src.backend.engines.base import BaseSimilarityEngine


class EngineRegistry:
    """Central registry for all similarity engines."""

    _engines: dict[str, type[BaseSimilarityEngine]] = {}

    @classmethod
    def register(cls, name: str, engine_class: type[BaseSimilarityEngine]):
        """Register a similarity engine plugin."""
        cls._engines[name] = engine_class

    @classmethod
    def get_engine(cls, name: str):
        """Get a registered engine by name."""
        return cls._engines.get(name)

    @classmethod
    def list_engines(cls) -> list:
        """List all registered engine names."""
        return list(cls._engines.keys())
