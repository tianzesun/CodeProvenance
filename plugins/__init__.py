"""Plugin system for custom detection engines.

Drop a Python file in the plugins/ directory that defines a class
inheriting from DetectionEngine. It will be auto-loaded on startup.

Example plugin (plugins/my_engine.py):

    from benchmark.similarity.base_engine import BaseSimilarityEngine

    class MyEngine(BaseSimilarityEngine):
        def name(self) -> str:
            return "my_engine"

        def description(self) -> str:
            return "My custom detection engine"

        def compare(self, code1: str, code2: str) -> float:
            # Your similarity logic here
            return 0.5
"""
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from benchmark.registry import registry


def load_plugins(plugins_dir: str = "plugins") -> List[str]:
    """Load all plugins from the plugins directory.

    Scans the plugins directory for .py files, imports them,
    and registers any DetectionEngine subclasses found.

    Args:
        plugins_dir: Path to the plugins directory.

    Returns:
        List of successfully loaded plugin names.
    """
    loaded = []
    plugins_path = Path(plugins_dir)
    if not plugins_path.exists():
        return loaded

    for py_file in sorted(plugins_path.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            _load_plugin(py_file)
            loaded.append(py_file.stem)
        except Exception as e:
            print(f"Warning: Failed to load plugin {py_file.name}: {e}", file=sys.stderr)

    return loaded


def _load_plugin(py_file: Path) -> None:
    """Load a single plugin file and register its engines."""
    from benchmark.similarity.base_engine import BaseSimilarityEngine
    from benchmark.registry import DetectionEngine

    spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec from {py_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[py_file.stem] = module
    spec.loader.exec_module(module)

    # Find and register all engine classes in the module
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if not isinstance(attr, type):
            continue
        if attr.__module__ != module.__name__:
            continue
        if issubclass(attr, (DetectionEngine, BaseSimilarityEngine)) and attr not in (DetectionEngine, BaseSimilarityEngine):
            # Create instance to get name
            try:
                instance = attr()
                name = getattr(instance, 'name', lambda: attr_name)
                engine_name = name() if callable(name) else name
                registry.register(engine_name, attr)
            except Exception:
                # Fallback: register with module.class name
                registry.register(f"{py_file.stem}.{attr_name}", attr)
