"""
Base Intermediate Representation (IR) classes.

Defines the abstract interface and metadata for all IR representations.
"""

import contextlib
import hashlib
import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar

SUPPORTED_LANGUAGES = ("python", "java", "javascript")
_LANGUAGE_ALIASES = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "jsx": "javascript",
    "node": "javascript",
}


def normalize_language(language: str) -> str:
    """Canonical language name ("Python " -> "python", "js" -> "javascript")."""
    lang = (language or "").strip().lower()
    return _LANGUAGE_ALIASES.get(lang, lang)


@dataclass
class IRMetadata:
    """Metadata for any IR representation.

    Attributes:
        language: Programming language (e.g., 'python', 'java', 'javascript')
        source_hash: SHA-256 hash of original source code
        timestamp: When the IR was created (ISO-8601, UTC)
        representation_type: Type of IR ('ast', 'token', 'graph')
        file_path: Optional path to source file
        line_count: Number of lines in original source
        char_count: Number of characters in original source
    """

    language: str
    source_hash: str
    timestamp: str
    representation_type: str
    file_path: str | None = None
    line_count: int = 0
    char_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata to dictionary."""
        return {
            "language": self.language,
            "source_hash": self.source_hash,
            "timestamp": self.timestamp,
            "representation_type": self.representation_type,
            "file_path": self.file_path,
            "line_count": self.line_count,
            "char_count": self.char_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IRMetadata":
        """Deserialize metadata from dictionary."""
        return cls(
            language=data["language"],
            source_hash=data["source_hash"],
            timestamp=data["timestamp"],
            representation_type=data["representation_type"],
            file_path=data.get("file_path"),
            line_count=data.get("line_count", 0),
            char_count=data.get("char_count", 0),
        )

    @classmethod
    def create_metadata(
        cls,
        source_code: str,
        language: str,
        representation_type: str,
        file_path: str | None = None,
    ) -> "IRMetadata":
        """Create metadata directly from source code.

        Older callers construct metadata through ``IRMetadata.create_metadata``
        rather than ``BaseIR.create_metadata``. Keeping the helper here
        preserves that public API.
        """
        return cls(
            language=language,
            # surrogatepass: lone surrogates (bad decoding upstream) must not
            # crash hashing with UnicodeEncodeError.
            source_hash=hashlib.sha256(
                source_code.encode("utf-8", errors="surrogatepass")
            ).hexdigest(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            representation_type=representation_type,
            file_path=file_path,
            # split("\n") counted a phantom line after a trailing newline
            # ("a\nb\n" -> 3) and reported 1 line for an empty file.
            line_count=len(source_code.splitlines()),
            char_count=len(source_code),
        )

    def validate(self) -> bool:
        """Validate metadata completeness."""
        return all(
            [self.language, self.source_hash, self.timestamp, self.representation_type]
        )


class BaseIR(ABC):
    """Abstract base class for all intermediate representations.

    All IR implementations must provide:
    - Serialization to/from dictionary
    - Validation of IR integrity
    - Metadata tracking
    """

    #: 'ast' / 'token' / 'graph'; checked by :meth:`load`.
    REPRESENTATION_TYPE: ClassVar[str] = ""

    def __init__(self, metadata: IRMetadata):
        self.metadata = metadata

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize the IR payload (metadata is stored separately)."""

    @classmethod
    @abstractmethod
    def from_dict(
        cls, data: dict[str, Any], metadata: IRMetadata | None = None
    ) -> "BaseIR":
        """Deserialize IR from the output of :meth:`to_dict`.

        ``metadata`` may be passed explicitly; otherwise ``data["metadata"]``
        is used if present, else a placeholder. (Concrete ``from_dict``
        implementations used to discard ``data`` entirely and return an empty
        IR.)
        """

    @abstractmethod
    def validate(self) -> bool:
        """Validate IR integrity and completeness."""

    @classmethod
    def _resolve_metadata(
        cls, data: dict[str, Any], metadata: IRMetadata | None
    ) -> IRMetadata:
        if metadata is not None:
            return metadata
        embedded = data.get("metadata") if isinstance(data, dict) else None
        if isinstance(embedded, dict):
            return IRMetadata.from_dict(embedded)
        return IRMetadata(
            language="unknown",
            source_hash="",
            timestamp="",
            representation_type=cls.REPRESENTATION_TYPE,
        )

    @classmethod
    def create_metadata(
        cls,
        source_code: str,
        language: str,
        representation_type: str,
        file_path: str | None = None,
    ) -> IRMetadata:
        """Create metadata from source code."""
        return IRMetadata.create_metadata(
            source_code=source_code,
            language=language,
            representation_type=representation_type,
            file_path=file_path,
        )

    def save(self, filepath: "str | os.PathLike[str]") -> None:
        """Save IR to a JSON file (atomically: temp file + rename)."""
        data = {"metadata": self.metadata.to_dict(), "ir": self.to_dict()}
        path = os.fspath(filepath)
        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".ir_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    @classmethod
    def load(cls, filepath: "str | os.PathLike[str]") -> "BaseIR":
        """Load IR from a JSON file written by :meth:`save`.

        Raises:
            ValueError: If the file holds a different IR type than ``cls``
                (e.g. ``ASTIR.load`` on a graph file used to die with KeyError).
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        metadata = IRMetadata.from_dict(data["metadata"])
        expected = cls.REPRESENTATION_TYPE
        if expected and metadata.representation_type != expected:
            raise ValueError(
                f"{cls.__name__}.load() got a '{metadata.representation_type}' IR file"
            )
        return cls.from_dict(data["ir"], metadata)

    def _load_from_dict(self, data: dict[str, Any]) -> None:
        """Deprecated hook kept for subclasses written against the old loader."""

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(language={self.metadata.language}, "
            f"hash={self.metadata.source_hash[:8]}...)"
        )

    def _identity(self) -> tuple[str, str, str]:
        return (
            type(self).__name__,
            self.metadata.representation_type,
            self.metadata.source_hash,
        )

    def __eq__(self, other: object) -> bool:
        """Equal if same IR class, representation and source hash.

        (Previously an ASTIR equalled a TokenIR of the same source, and every
        merged graph — hash "merged" — equalled every other.)
        """
        if not isinstance(other, BaseIR):
            return False
        return self._identity() == other._identity()

    def __hash__(self) -> int:
        return hash(self._identity())
