"""Plugin auto-discovery system."""
import importlib
import pkgutil
import runners


def discover_plugins() -> None:
    """Dynamically imports all runner modules so they self-register."""
    package = runners
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"runners.{module_name}")