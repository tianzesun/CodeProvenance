"""Plugin registry package.

Everything here is light (no third-party imports, no discovery at import time), so the public names
are imported eagerly. ``discover_plugins`` imports the runner modules only when it is called.
"""

from .discovery import DiscoveryReport, PluginDiscoveryError, discover_plugins
from .loader import PluginRegistrationError, register_plugin
from .multi_language import LanguageConfig, MultiLanguageRegistry, get_language_registry
from .plugin_base import ExecutionPlugin, validate_plugin_name
from .plugin_registry import PluginRegistry

__all__ = [
    "DiscoveryReport",
    "ExecutionPlugin",
    "LanguageConfig",
    "MultiLanguageRegistry",
    "PluginDiscoveryError",
    "PluginRegistrationError",
    "PluginRegistry",
    "discover_plugins",
    "get_language_registry",
    "register_plugin",
    "validate_plugin_name",
]
