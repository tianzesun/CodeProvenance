"""Plugin loader decorator for registration.

``@register_plugin`` still works bare. Changes: it can take options (``replace``, ``lazy``); a plugin
whose constructor fails raises :class:`PluginRegistrationError` naming the class (it was a bare
traceback from inside the decorator, at import time of the runner module); a non-plugin class is
rejected with a clear ``TypeError``; and with ``lazy=True`` nothing runs at import time at all.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, overload

from .plugin_base import ExecutionPlugin
from .plugin_registry import PluginRegistry

T = TypeVar("T", bound=type)


class PluginRegistrationError(RuntimeError):
    """A plugin class could not be instantiated or registered."""


@overload
def register_plugin(cls: T) -> T: ...
@overload
def register_plugin(*, replace: bool = False, lazy: bool = False) -> Callable[[T], T]: ...


def register_plugin(cls: Any = None, *, replace: bool = False, lazy: bool = False) -> Any:
    """Decorator to register a plugin class.

    Usage::

        @register_plugin
        class PythonRunner(ExecutionPlugin): ...

        @register_plugin(lazy=True)          # instantiate on first PluginRegistry.get()
        class DockerRunner(ExecutionPlugin): ...

    Args:
        cls: Plugin class (when used without parentheses).
        replace: Replace a plugin of the same name registered by a different class.
        lazy: Register the class; it is instantiated on first use.

    Returns:
        The decorated class.
    """

    def decorate(klass: Any) -> Any:
        if not (isinstance(klass, type) and issubclass(klass, ExecutionPlugin)):
            raise TypeError(f"@register_plugin needs an ExecutionPlugin subclass, got {klass!r}")
        if lazy:
            PluginRegistry.register_factory(klass, replace=replace)
            return klass
        try:
            instance = klass()
        except Exception as exc:  # noqa: BLE001
            raise PluginRegistrationError(
                f"could not instantiate plugin {klass.__module__}.{klass.__qualname__}: {exc}"
            ) from exc
        PluginRegistry.register(instance, replace=replace)
        return klass

    return decorate(cls) if cls is not None else decorate
