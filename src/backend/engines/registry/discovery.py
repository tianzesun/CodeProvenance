"""Plugin auto-discovery system.

What was wrong:
- ``import runners`` ran when ``discovery`` was imported, so importing this module failed whenever
  the ``runners`` package was not importable, even if ``discover_plugins`` was never called.
- The FIRST runner module that raised (a missing optional dependency, a constructor that failed)
  aborted the loop: every later runner stayed unregistered, with no hint which ones.
- ``pkgutil.iter_modules`` lists only the top level, so runners in sub-packages were never imported.
- Calling it again after the registry was cleared did nothing (``import_module`` is cached); there
  was no way to reload.
- It returned nothing, so a caller could not tell what was registered or what failed.

Failure policy: by default every module is tried, then ONE ``PluginDiscoveryError`` listing all
failures is raised (fail fast at start-up, but with the complete picture). ``strict=False`` returns
the report instead.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from dataclasses import dataclass, field
from types import ModuleType

from .plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

DEFAULT_PACKAGE = "runners"


class PluginDiscoveryError(RuntimeError):
    """One or more runner modules failed to import."""

    def __init__(self, failures: dict[str, str]):
        self.failures = dict(failures)
        lines = "; ".join(f"{name}: {error}" for name, error in sorted(failures.items()))
        super().__init__(f"{len(failures)} plugin module(s) failed to import: {lines}")


@dataclass(frozen=True)
class DiscoveryReport:
    """What a discovery run did."""

    package: str
    imported: tuple[str, ...] = ()
    failed: dict[str, str] = field(default_factory=dict)
    skipped: tuple[str, ...] = ()
    registered: tuple[str, ...] = ()  # plugin names that are new after this run

    @property
    def ok(self) -> bool:
        return not self.failed


def discover_plugins(
    package: str | ModuleType = DEFAULT_PACKAGE,
    *,
    recursive: bool = True,
    strict: bool = True,
    reload: bool = False,
    skip_private: bool = True,
) -> DiscoveryReport:
    """Dynamically import every runner module so that it self-registers.

    Args:
        package: Package (or its dotted name) holding the runner modules.
        recursive: Also import modules in sub-packages.
        strict: Raise :class:`PluginDiscoveryError` after trying everything if any import failed.
        reload: ``importlib.reload`` modules that were already imported (re-registers plugins after
            ``PluginRegistry.clear()``).
        skip_private: Skip modules and packages whose name starts with ``_``.

    Returns:
        A :class:`DiscoveryReport` (also when ``strict`` and everything worked).

    Raises:
        ImportError: ``package`` itself cannot be imported.
        PluginDiscoveryError: ``strict`` and at least one module failed.
    """
    root = importlib.import_module(package) if isinstance(package, str) else package
    paths = getattr(root, "__path__", None)
    if paths is None:
        raise TypeError(f"{getattr(root, '__name__', root)!r} is not a package")
    prefix = root.__name__ + "."
    before = set(PluginRegistry.names())

    failed: dict[str, str] = {}

    def on_walk_error(name: str) -> None:  # a sub-package whose __init__ fails while walking
        failed[name] = _describe(sys.exc_info()[1])
        logger.error("Plugin sub-package %s failed to import", name, exc_info=True)

    walker = (
        pkgutil.walk_packages(paths, prefix, onerror=on_walk_error)
        if recursive
        else pkgutil.iter_modules(paths, prefix)
    )
    names = sorted({m.name for m in walker})

    imported: list[str] = []
    skipped: list[str] = []
    for name in names:
        if skip_private and any(part.startswith("_") for part in name[len(prefix) :].split(".")):
            skipped.append(name)
            continue
        try:
            module = sys.modules.get(name)
            if reload and module is not None:
                importlib.reload(module)
            else:
                importlib.import_module(name)
            imported.append(name)
        except Exception as exc:  # noqa: BLE001 - one broken runner must not hide the others
            failed[name] = _describe(exc)
            logger.error("Plugin module %s failed to import", name, exc_info=True)

    report = DiscoveryReport(
        package=root.__name__,
        imported=tuple(imported),
        failed=failed,
        skipped=tuple(skipped),
        registered=tuple(n for n in PluginRegistry.names() if n not in before),
    )
    if failed and strict:
        raise PluginDiscoveryError(failed)
    return report


def _describe(exc: BaseException | None) -> str:
    return f"{type(exc).__name__}: {exc}" if exc is not None else "unknown error"
