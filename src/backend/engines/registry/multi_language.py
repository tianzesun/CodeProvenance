"""Multi-language support registry.

Registers the programming languages the platform recognises (23 built in) and the file extensions
that identify them, with optional language-specific normalizers and parsers.

What was wrong:
- Extensions shared by several languages silently belonged to whichever registered LAST: ``.h``
  is declared by C++, Objective-C and C, so only C was ever found. Every candidate is kept now,
  a documented primary is chosen (C for ``.h``), and :meth:`detect_language` can look at the file
  CONTENT to tell C, C++ and Objective-C headers apart.
- ``filename.split('.')[-1]`` treated a file without an extension as having one: a file called
  ``py`` was Python, ``Makefile`` became ``.makefile``, and a dotted directory (``pkg.v2/run``) made
  ``.v2/run``. The extension is taken from the base name with ``os.path.splitext``.
- Re-registering a language left its OLD extensions pointing at the stale config.
- Language names and extensions shared one dict, so a language and an extension could collide, and
  ``get_config_for_file`` handed out the live internal dict (callers could corrupt the registry).
  Configs are immutable ``LanguageConfig`` objects (still readable like the old dict:
  ``config["name"]``).
- Extensions were not validated or normalised (``"py"`` or ``".PY"`` never matched), registration
  was not thread-safe, and bootstrapping logged 23 INFO lines per instance.
- No lookup by language NAME existed (``"cpp"``, ``"c#"``, ``"js"``); aliases are supported.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_EXT = re.compile(r"^\.[a-z0-9_+\-]+$")
_ID_OVERRIDES = {"c++": "cpp", "c#": "csharp", "objective-c": "objc"}
_ALIASES = {
    "cpp": "c++", "cplusplus": "c++", "cxx": "c++", "csharp": "c#", "cs": "c#", "js": "javascript",
    "node": "javascript", "nodejs": "javascript", "ts": "typescript", "py": "python",
    "python3": "python", "golang": "go", "rs": "rust", "kt": "kotlin", "rb": "ruby", "sh": "shell",
    "bash": "shell", "objc": "objective-c", "objectivec": "objective-c", "pl": "perl", "hs": "haskell",
    "jl": "julia",
}  # fmt: skip
#: When several languages claim an extension, this one is the primary (the rest stay candidates).
_PRIMARY = {".h": "c"}

_CPP_MARKERS = re.compile(
    r"\bnamespace\s+\w+|\btemplate\s*<|\bstd::|#\s*include\s*<(?:iostream|vector|string|map|set|memory|algorithm|cstdio|cstdlib)>"
    r"|\bclass\s+\w+\s*(?::|\{)|\b(?:public|private|protected)\s*:",
)
_OBJC_MARKERS = re.compile(r"@(?:interface|implementation|protocol|property|end)\b|#\s*import\b|\bNS[A-Z]\w+")


@dataclass(frozen=True)
class LanguageConfig:
    """Immutable description of one language (readable like the old dict: ``config["name"]``)."""

    name: str
    extensions: tuple[str, ...]
    normalizer: type | None = None
    parser: Any | None = None
    id: str = ""  # canonical lower-case identifier: "python", "cpp", "csharp", "objc", ...

    def __getitem__(self, key: str) -> Any:
        if key == "extensions":
            return list(self.extensions)  # the old config stored a list
        if key in ("name", "normalizer", "parser", "id"):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        return {k: self[k] for k in ("name", "extensions", "normalizer", "parser", "id")}


def _normalize_extension(ext: str) -> str:
    if not isinstance(ext, str):
        raise TypeError(f"extension must be a string, got {ext!r}")
    text = ext.strip().lower()
    if text and not text.startswith("."):
        text = "." + text
    if not _EXT.match(text):
        raise ValueError(f"invalid file extension {ext!r}")
    return text


def _language_id(name: str) -> str:
    key = name.strip().lower()
    return _ID_OVERRIDES.get(key, key)


class MultiLanguageRegistry:
    """Registers and maintains support for 20+ programming languages.

    Provides language-specific normalizers and similarity engines (via ``register_language``).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._languages: dict[str, LanguageConfig] = {}  # lower-case name -> config
        self._by_extension: dict[str, list[str]] = {}  # extension -> language keys, registration order
        self._bootstrap_languages()

    # ------------------------------------------------------------------ registration

    def register_language(
        self,
        name: str,
        extensions: Iterable[str],
        normalizer_cls: type | None = None,
        ast_parser: Any | None = None,
    ) -> LanguageConfig:
        """Register (or replace) a language and its support tools.

        Re-registering a name replaces the old config AND drops its old extensions.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("language name must be a non-empty string")
        if isinstance(extensions, str):
            extensions = [extensions]
        exts = tuple(dict.fromkeys(_normalize_extension(e) for e in extensions))
        key = name.strip().lower()
        config = LanguageConfig(
            name=name.strip(), extensions=exts, normalizer=normalizer_cls, parser=ast_parser, id=_language_id(name)
        )
        with self._lock:
            self._drop_extensions(key)
            self._languages[key] = config
            for ext in exts:
                self._by_extension.setdefault(ext, []).append(key)
        logger.debug("Registered language: %s (extensions: %s)", name, ", ".join(exts))
        return config

    def unregister_language(self, name: str) -> bool:
        """Remove a language and its extensions; True when it existed."""
        key = self._resolve(name)
        with self._lock:
            if key is None:
                return False
            self._drop_extensions(key)
            del self._languages[key]
            return True

    def _drop_extensions(self, key: str) -> None:
        for ext in [e for e, keys in self._by_extension.items() if key in keys]:
            self._by_extension[ext].remove(key)
            if not self._by_extension[ext]:
                del self._by_extension[ext]

    def _bootstrap_languages(self) -> None:
        """Populate registry with the core supported languages."""
        # Core 6
        self.register_language("Python", [".py", ".pyw", ".pyi"])
        self.register_language("C++", [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".h"])
        self.register_language("Java", [".java"])
        self.register_language("JavaScript", [".js", ".mjs", ".jsx"])
        self.register_language("TypeScript", [".ts", ".tsx"])
        self.register_language("C#", [".cs"])

        # Expanding to 20+
        self.register_language("Go", [".go"])
        self.register_language("Ruby", [".rb"])
        self.register_language("PHP", [".php"])
        self.register_language("Swift", [".swift"])
        self.register_language("Rust", [".rs"])
        self.register_language("Kotlin", [".kt", ".kts"])
        self.register_language("Scala", [".scala"])
        self.register_language("Haskell", [".hs"])
        self.register_language("Lua", [".lua"])
        self.register_language("Perl", [".pl", ".pm"])
        self.register_language("R", [".r"])
        self.register_language("Dart", [".dart"])
        self.register_language("Objective-C", [".m", ".h"])
        self.register_language("C", [".c", ".h"])
        self.register_language("SQL", [".sql"])
        self.register_language("Julia", [".jl"])
        self.register_language("Shell", [".sh", ".bash"])

    # ------------------------------------------------------------------ lookup

    @property
    def language_configs(self) -> dict[str, LanguageConfig]:
        """Snapshot ``{name or extension: primary config}`` (the old combined mapping, read-only copy)."""
        with self._lock:
            combined: dict[str, LanguageConfig] = dict(self._languages)
            for ext in self._by_extension:
                combined[ext] = self._primary_for_extension(ext)  # type: ignore[assignment]
            return combined

    @staticmethod
    def _extension_of(filename: object) -> str:
        """``".py"`` for ``"dir/run.PY"``; ``""`` when the BASE name has no extension."""
        if not isinstance(filename, str) or not filename:
            return ""
        base = os.path.basename(filename.replace("\\", "/"))
        return os.path.splitext(base)[1].lower()

    def _primary_for_extension(self, ext: str) -> LanguageConfig | None:
        keys = self._by_extension.get(ext)
        if not keys:
            return None
        preferred = _PRIMARY.get(ext)
        if preferred in keys:
            return self._languages[preferred]
        return self._languages[keys[0]]

    def candidates_for_file(self, filename: str) -> list[LanguageConfig]:
        """Every language that claims the file's extension (primary first)."""
        ext = self._extension_of(filename)
        with self._lock:
            primary = self._primary_for_extension(ext)
            if primary is None:
                return []
            others = [self._languages[k] for k in self._by_extension[ext] if self._languages[k] is not primary]
            return [primary, *others]

    def get_config_for_file(self, filename: str) -> LanguageConfig | None:
        """Language of a file from its extension (the primary language for ambiguous ones like ``.h``)."""
        found = self.candidates_for_file(filename)
        return found[0] if found else None

    def detect_language(self, filename: str, content: str | None = None) -> LanguageConfig | None:
        """Like :meth:`get_config_for_file`, but uses the content to settle an ambiguous extension.

        For ``.h``: Objective-C markers (``@interface``, ``#import``) -> Objective-C; C++ markers
        (``namespace``, ``template<``, ``std::``, ``class X {``) -> C++; otherwise C.
        """
        candidates = self.candidates_for_file(filename)
        if len(candidates) <= 1 or not content:
            return candidates[0] if candidates else None
        by_id = {c.id: c for c in candidates}
        sample = content[:20000]
        if "objc" in by_id and _OBJC_MARKERS.search(sample):
            return by_id["objc"]
        if "cpp" in by_id and _CPP_MARKERS.search(sample):
            return by_id["cpp"]
        return candidates[0]

    def _resolve(self, name: str) -> str | None:
        if not isinstance(name, str):
            return None
        key = name.strip().lower()
        key = _ALIASES.get(key, key)
        return key if key in self._languages else None

    def get_config_for_language(self, name: str) -> LanguageConfig | None:
        """Config by language NAME or alias (``"C++"``, ``"cpp"``, ``"csharp"``, ``"js"`` ...)."""
        with self._lock:
            key = self._resolve(name)
            return self._languages[key] if key else None

    def get_supported_languages(self) -> list[str]:
        """Returns a unique, sorted list of supported language names."""
        with self._lock:
            return sorted(cfg.name for cfg in self._languages.values())

    def get_supported_extensions(self) -> list[str]:
        """Every recognised file extension, sorted."""
        with self._lock:
            return sorted(self._by_extension)


_default_registry: MultiLanguageRegistry | None = None
_default_lock = threading.Lock()


def get_language_registry() -> MultiLanguageRegistry:
    """Shared registry (built once; creating ``MultiLanguageRegistry()`` per use re-bootstraps every time)."""
    global _default_registry
    if _default_registry is None:
        with _default_lock:
            if _default_registry is None:
                _default_registry = MultiLanguageRegistry()
    return _default_registry
