"""On-disk embedding cache that never unpickles anything.

The embedding engines cached vectors with ``pickle`` in a directory relative to the
process working directory. Loading a pickle executes code, so anyone who could
write a file into that directory (or into a shared volume mounted there) got code
execution inside the analysis worker. Vectors are now stored as ``.npy`` files and
read with ``allow_pickle=False``; a file that is not a plain finite 1-D float array
is rejected and removed. Existing ``.pkl`` entries are simply ignored (and
recomputed).

The cache location comes from ``SIMILARITY_CACHE_DIR`` (default ``./.<name>_cache``)
and is created on first write, not at construction, so building an engine no longer
touches the filesystem (it failed on read-only deployments).
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class DiskEmbeddingStore:
    """Namespaced ``text -> vector`` store backed by ``.npy`` files."""

    def __init__(self, namespace: str, directory: str | Path | None = None, default_dir: str = ".embedding_cache"):
        self.namespace = namespace
        self._directory = Path(directory) if directory is not None else None
        self._default_dir = default_dir

    @property
    def directory(self) -> Path:
        if self._directory is not None:
            return self._directory
        base = os.environ.get("SIMILARITY_CACHE_DIR")
        return Path(base) / self._default_dir.lstrip("./") if base else Path(self._default_dir)

    def key(self, text: str) -> str:
        """Cache key: depends on the namespace (model), so different models never share entries."""
        return hashlib.sha256(f"{self.namespace}::{text}".encode("utf-8", "surrogatepass")).hexdigest()

    def path(self, text: str) -> Path:
        return self.directory / f"{self.key(text)}.npy"

    def get(self, text: str) -> np.ndarray | None:
        path = self.path(text)
        if not path.exists():
            return None
        try:
            vector = np.load(path, allow_pickle=False)
            if vector.ndim != 1 or vector.size == 0 or not np.issubdtype(vector.dtype, np.floating) or not np.all(np.isfinite(vector)):
                raise ValueError("not a finite 1-D float vector")
            return vector
        except Exception as exc:
            logger.debug("Dropping unreadable cache entry %s: %s", path.name, exc)
            path.unlink(missing_ok=True)  # evict corrupt entry
            return None

    def put(self, text: str, vector: np.ndarray) -> None:
        try:
            directory = self.directory
            directory.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as fh:
                    np.save(fh, np.asarray(vector, dtype=np.float32), allow_pickle=False)
                Path(tmp).replace(self.path(text))  # atomic: never a half-written entry
            finally:
                Path(tmp).unlink(missing_ok=True)
        except Exception as exc:  # a cache failure must never fail a comparison
            logger.debug("Cache write failed (non-fatal): %s", exc)
