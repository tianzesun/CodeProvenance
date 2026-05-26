"""Plugin loader decorator for registration."""
from src.backend.bootstrap.plugins.plugin_registry import PluginRegistry


def register_plugin(cls):
    """Decorator to register a plugin class.

    Args:
        cls: Plugin class to register.

    Returns:
        The decorated class.
    """
    instance = cls()
    PluginRegistry.register(instance)
    return cls