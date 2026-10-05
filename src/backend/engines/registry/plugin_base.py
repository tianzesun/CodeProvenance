"""Plugin base contract for all execution modules.

A plugin needs a class-level (or instance-level) ``name``. It used to be only a type annotation, so
a subclass that forgot it failed with an ``AttributeError`` deep inside ``PluginRegistry.register``,
at import time of the runner module. :func:`validate_plugin_name` gives a clear error instead.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar

#: Letters, digits, ``_ - . +``; must start with a letter or digit; at most 100 characters.
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+\-]{0,99}$")


def validate_plugin_name(name: object, owner: str = "plugin") -> str:
    """Return ``name`` if it is a valid plugin name, else raise ``ValueError``."""
    if not isinstance(name, str) or not _NAME.match(name):
        raise ValueError(
            f"{owner}: invalid plugin name {name!r} (use 1-100 letters, digits, '_', '-', '.', '+'; "
            "it must start with a letter or digit)"
        )
    return name


class ExecutionPlugin(ABC):
    """Base contract for all execution modules."""

    name: ClassVar[str]
    version: ClassVar[str] = "1.0"
    description: ClassVar[str] = ""

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the plugin with given parameters."""

    def metadata(self) -> dict[str, str]:
        """Name, version and description (what the registry lists)."""
        return {
            "name": validate_plugin_name(getattr(self, "name", None), type(self).__qualname__),
            "version": str(self.version),
            "description": str(self.description),
            "class": f"{type(self).__module__}.{type(self).__qualname__}",
        }
