"""Plugin auto-discovery system."""

import importlib
import pkgutil

from src.backend.benchmark.runners import __path__


def discover_plugins() -> None:
    """Dynamically imports all runner modules so they self-register."""
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        importlib.import_module(f"src.backend.benchmark.runners.{module_name}")
