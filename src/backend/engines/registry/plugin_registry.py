"""Plugin registry - single source of truth for execution plugins.

What was wrong:
- ``register`` raised ``ValueError("Duplicate plugin")`` when a runner module was reloaded
  (``importlib.reload``, test re-imports, a second interpreter-level import path), although it was
  the SAME class registering again. The same class now re-registers (it replaces its previous
  instance); a DIFFERENT class with the same name still raises, and the message names both.
- Nothing checked that the argument was a plugin INSTANCE: registering the class, or an object with no
  ``name``, failed with an obscure ``AttributeError`` / stored the wrong thing.
- The registry was an unsynchronised class-level dict.
- ``get`` failed with a bare ``KeyError('x')`` and did not say what is registered.
- There was no way to remove a plugin or reset the registry (tests had to poke ``_plugins``).
- Imports were absolute (``from engines.registry...``). When the package is imported under another
  root (the rest of the code base uses ``src.backend.engines...``), ``loader`` and ``discovery``
  still bound to the ``engines.registry`` copy of the registry: a plugin registered by
  ``@register_plugin`` was invisible to code reading ``src.backend.engines.registry.PluginRegistry``.
  Imports are relative now, so every copy of the package is self-consistent. (Importing the SAME
  package under two roots still creates two registries; keep to one root.)
- Plugins can be registered LAZILY (a class, instantiated on first ``get``) so that a constructor
  with side effects does not run, and cannot fail, at import time.
"""

from __future__ import annotations

import threading
from typing import Any, ClassVar

from .plugin_base import ExecutionPlugin, validate_plugin_name


class PluginRegistry:
    """Registry for execution plugins."""

    #: name -> instantiated plugin (kept as ``_plugins`` for existing callers)
    _plugins: ClassVar[dict[str, ExecutionPlugin]] = {}
    #: name -> plugin CLASS registered lazily (moved to ``_plugins`` on first ``get``)
    _factories: ClassVar[dict[str, type[ExecutionPlugin]]] = {}
    _lock: ClassVar[threading.RLock] = threading.RLock()

    # ------------------------------------------------------------------ registration

    @classmethod
    def register(cls, plugin: ExecutionPlugin, *, replace: bool = False) -> None:
        """Register a plugin instance.

        Args:
            plugin: Plugin instance to register.
            replace: Allow replacing a plugin registered under the same name by ANY class.

        Raises:
            TypeError: ``plugin`` is not an ``ExecutionPlugin`` instance.
            ValueError: invalid name, or a different class already uses the name.
        """
        if isinstance(plugin, type):
            raise TypeError(
                f"register() takes a plugin INSTANCE, got the class {plugin.__qualname__} "
                "(use register_factory() or @register_plugin(lazy=True) for classes)"
            )
        if not isinstance(plugin, ExecutionPlugin):
            raise TypeError(f"{type(plugin).__qualname__} is not an ExecutionPlugin")
        name = validate_plugin_name(getattr(plugin, "name", None), type(plugin).__qualname__)
        with cls._lock:
            cls._check_free(name, type(plugin), replace)
            cls._factories.pop(name, None)
            cls._plugins[name] = plugin

    @classmethod
    def register_factory(cls, plugin_cls: type[ExecutionPlugin], *, replace: bool = False) -> None:
        """Register a plugin CLASS; it is instantiated on the first ``get`` (needs a class-level ``name``)."""
        if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, ExecutionPlugin)):
            raise TypeError(f"{plugin_cls!r} is not an ExecutionPlugin subclass")
        name = validate_plugin_name(getattr(plugin_cls, "name", None), plugin_cls.__qualname__)
        with cls._lock:
            cls._check_free(name, plugin_cls, replace)
            cls._plugins.pop(name, None)
            cls._factories[name] = plugin_cls

    @classmethod
    def _check_free(cls, name: str, new_cls: type, replace: bool) -> None:
        """Raise unless ``name`` is free, or held by the same class (a reload), or ``replace``."""
        existing = cls._plugins.get(name)
        existing_cls = type(existing) if existing is not None else cls._factories.get(name)
        if existing_cls is None or replace:
            return
        if _same_class(existing_cls, new_cls):
            return  # module reloaded: the fresh class replaces the stale one
        raise ValueError(
            f"Duplicate plugin: {name!r} is already registered by "
            f"{existing_cls.__module__}.{existing_cls.__qualname__}; "
            f"cannot register {new_cls.__module__}.{new_cls.__qualname__}"
        )

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Remove a plugin; True when something was removed."""
        with cls._lock:
            removed = cls._plugins.pop(name, None) is not None
            return (cls._factories.pop(name, None) is not None) or removed

    @classmethod
    def clear(cls) -> None:
        """Remove every plugin (tests, hot reload)."""
        with cls._lock:
            cls._plugins.clear()
            cls._factories.clear()

    # ------------------------------------------------------------------ lookup

    @classmethod
    def get(cls, name: str) -> ExecutionPlugin:
        """Get a plugin by name (a lazily registered class is instantiated now, once).

        Raises:
            KeyError: if not found; the message lists the registered names.
        """
        with cls._lock:
            plugin = cls._plugins.get(name)
            if plugin is not None:
                return plugin
            factory = cls._factories.get(name)
            if factory is None:
                raise KeyError(f"Unknown plugin {name!r}; registered: {cls._names()}")
            plugin = factory()  # a failing constructor leaves the factory registered
            cls._plugins[name] = plugin
            del cls._factories[name]
            return plugin

    @classmethod
    def has(cls, name: str) -> bool:
        """Whether a plugin (eager or lazy) is registered under ``name``."""
        with cls._lock:
            return name in cls._plugins or name in cls._factories

    @classmethod
    def _names(cls) -> list[str]:
        return list(cls._plugins) + [n for n in cls._factories if n not in cls._plugins]

    @classmethod
    def names(cls) -> list[str]:
        """Registered plugin names, in registration order."""
        with cls._lock:
            return cls._names()

    @classmethod
    def list(cls) -> list[str]:  # noqa: A003 (kept for existing callers)
        """List all registered plugin names (alias of :meth:`names`)."""
        return cls.names()

    @classmethod
    def describe(cls) -> list[dict[str, Any]]:
        """Name / version / description of every plugin, without instantiating lazy ones."""
        with cls._lock:
            out = [p.metadata() for p in cls._plugins.values()]
            for name, factory in cls._factories.items():
                out.append(
                    {
                        "name": name,
                        "version": str(getattr(factory, "version", "")),
                        "description": str(getattr(factory, "description", "")),
                        "class": f"{factory.__module__}.{factory.__qualname__}",
                        "lazy": True,
                    }
                )
            return out


def _same_class(a: type, b: type) -> bool:
    """Same class identity, including a RELOADED module's new class object."""
    return a is b or (a.__module__ == b.__module__ and a.__qualname__ == b.__qualname__)
