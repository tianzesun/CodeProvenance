"""Plugin registry - single source of truth for execution plugins."""
from typing import Dict
from engines.registry.plugin_base import ExecutionPlugin


class PluginRegistry:
    """Registry for execution plugins."""

    _plugins: Dict[str, ExecutionPlugin] = {}

    @classmethod
    def register(cls, plugin: ExecutionPlugin) -> None:
        """Register a plugin.

        Args:
            plugin: Plugin instance to register.

        Raises:
            ValueError: If plugin name already registered.
        """
        name = plugin.name
        if name in cls._plugins:
            raise ValueError(f"Duplicate plugin: {name}")
        cls._plugins[name] = plugin

    @classmethod
    def get(cls, name: str) -> ExecutionPlugin:
        """Get a plugin by name.

        Args:
            name: Plugin name.

        Returns:
            Plugin instance.

        Raises:
            KeyError: If plugin not found.
        """
        return cls._plugins[name]

    @classmethod
    def list(cls) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names.
        """
        return list(cls._plugins.keys())