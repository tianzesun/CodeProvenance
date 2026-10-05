"""Similarity Registry - extensible registry for all similarity algorithms."""

import threading
from typing import Any, ClassVar


class SimilarityRegistry:
    """Name -> engine registry (process-wide, thread-safe)."""

    _engines: ClassVar[dict[str, Any]] = {}
    _lock: ClassVar[threading.RLock] = threading.RLock()

    @classmethod
    def register(cls, name: str, engine: Any, *, replace: bool = True) -> None:
        """Register ``engine`` under ``name``.

        With ``replace=False`` an existing registration is kept and ``ValueError``
        is raised (the default still overwrites, as before).
        """
        if not isinstance(name, str) or not name:
            raise ValueError("engine name must be a non-empty string")
        with cls._lock:
            if not replace and name in cls._engines:
                raise ValueError(f"engine {name!r} is already registered")
            cls._engines[name] = engine

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Remove ``name``; False when it was not registered."""
        with cls._lock:
            return cls._engines.pop(name, None) is not None

    @classmethod
    def get(cls, name: str) -> Any:
        """The engine registered as ``name``, or None."""
        with cls._lock:
            return cls._engines.get(name)

    @classmethod
    def list(cls) -> "list[str]":
        """Registered engine names, in registration order."""
        with cls._lock:
            return [*cls._engines]

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._engines.clear()
