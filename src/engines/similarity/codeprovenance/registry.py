"""
CodeProvenance Engine Registry.

Provides versioned engine registration for reproducible evaluations.
"""

from typing import Dict, Type, List, Optional
from src.engines.similarity.codeprovenance.base import BaseCodeProvenanceEngine


# Global engine registry
ENGINE_REGISTRY: Dict[str, Type[BaseCodeProvenanceEngine]] = {}


def register_engine(version: str):
    """Decorator to register an engine version.
    
    Args:
        version: Version identifier (e.g., 'codeprovenance:v1')
        
    Returns:
        Decorator function
        
    Example:
        @register_engine("codeprovenance:v1")
        class CodeProvenanceV1(BaseCodeProvenanceEngine):
            ...
    """
    def decorator(cls: Type[BaseCodeProvenanceEngine]) -> Type[BaseCodeProvenanceEngine]:
        if version in ENGINE_REGISTRY:
            raise ValueError(f"Engine version '{version}' already registered")
        
        # Validate that class implements required interface
        if not issubclass(cls, BaseCodeProvenanceEngine):
            raise TypeError(
                f"Engine class {cls.__name__} must inherit from BaseCodeProvenanceEngine"
            )
        
        # Register the engine
        ENGINE_REGISTRY[version] = cls
        return cls
    
    return decorator


def get_engine(version: str) -> BaseCodeProvenanceEngine:
    """Get engine instance by version.
    
    Args:
        version: Version identifier (e.g., 'codeprovenance:v1')
        
    Returns:
        Engine instance
        
    Raises:
        ValueError: If version is not registered
    """
    if version not in ENGINE_REGISTRY:
        available = list_engines()
        raise ValueError(
            f"Unknown engine version: '{version}'. "
            f"Available versions: {available}"
        )
    
    engine_class = ENGINE_REGISTRY[version]
    return engine_class()


def list_engines() -> List[str]:
    """List all registered engine versions.
    
    Returns:
        List of version identifiers
    """
    return sorted(ENGINE_REGISTRY.keys())


def get_engine_class(version: str) -> Type[BaseCodeProvenanceEngine]:
    """Get engine class by version.
    
    Args:
        version: Version identifier (e.g., 'codeprovenance:v1')
        
    Returns:
        Engine class
        
    Raises:
        ValueError: If version is not registered
    """
    if version not in ENGINE_REGISTRY:
        available = list_engines()
        raise ValueError(
            f"Unknown engine version: '{version}'. "
            f"Available versions: {available}"
        )
    
    return ENGINE_REGISTRY[version]


def is_registered(version: str) -> bool:
    """Check if an engine version is registered.
    
    Args:
        version: Version identifier
        
    Returns:
        True if registered, False otherwise
    """
    return version in ENGINE_REGISTRY


def get_registry_info() -> Dict[str, Dict[str, str]]:
    """Get information about all registered engines.
    
    Returns:
        Dictionary mapping version to engine info
    """
    info = {}
    for version, engine_class in ENGINE_REGISTRY.items():
        # Create temporary instance to get properties
        try:
            instance = engine_class()
            info[version] = {
                "version": instance.version,
                "name": instance.name,
                "description": instance.description,
                "class": engine_class.__name__,
            }
        except Exception as e:
            info[version] = {
                "version": version,
                "name": "Unknown",
                "description": f"Error: {str(e)}",
                "class": engine_class.__name__,
            }
    
    return info


def unregister_engine(version: str) -> bool:
    """Unregister an engine version.
    
    Args:
        version: Version identifier
        
    Returns:
        True if unregistered, False if not found
    """
    if version in ENGINE_REGISTRY:
        del ENGINE_REGISTRY[version]
        return True
    return False


def clear_registry() -> None:
    """Clear all registered engines.
    
    Warning: This is primarily for testing purposes.
    """
    ENGINE_REGISTRY.clear()