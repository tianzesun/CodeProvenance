"""Restricted unpickling for model files written by our own training code.

A bare ``pickle.load`` runs whatever the file says to run, so anyone able to write a model
file gets code execution in the process that loads it. These helpers only build
scikit-learn / numpy / scipy objects and plain containers, and refuse every other global
(no ``os.system``, ``eval``, ``subprocess``, ``builtins.getattr`` ...).
"""

from __future__ import annotations

import io
import pickle
import stat
from pathlib import Path
from typing import Any

MAX_MODEL_FILE_BYTES = 50 * 1024 * 1024

_SAFE_BUILTINS = frozenset(
    {
        "dict",
        "list",
        "set",
        "frozenset",
        "tuple",
        "int",
        "float",
        "bool",
        "str",
        "bytes",
        "complex",
        "slice",
        "range",
        "object",
        "bytearray",
    }
)
_SAFE_MODULE_PREFIXES = (
    "sklearn.",
    "numpy.",
    "scipy.",
    "collections",
    "joblib.numpy_pickle",
)


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that only builds scikit-learn / numpy objects and plain containers."""

    def find_class(self, module: str, name: str) -> Any:
        """Resolve a global only when it is on the allow-list."""
        if module == "builtins" and name in _SAFE_BUILTINS:
            return super().find_class(module, name)
        if module.startswith(_SAFE_MODULE_PREFIXES) or module in (
            "sklearn",
            "numpy",
            "scipy",
        ):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"global {module}.{name} is not allowed in a model file"
        )


def load_restricted_pickle(
    path: str | Path, max_bytes: int = MAX_MODEL_FILE_BYTES
) -> Any:
    """Load a pickled model file with :class:`RestrictedUnpickler`.

    Args:
        path: File to load.
        max_bytes: Largest file size accepted.

    Returns:
        The unpickled object.

    Raises:
        ValueError: If the file is larger than ``max_bytes``.
        PermissionError: If the file is world-writable.
        pickle.UnpicklingError: If the file names a global outside the allow-list.
    """
    path = Path(path)
    info = path.stat()
    if info.st_size > max_bytes:
        raise ValueError(f"model file is too large ({info.st_size} bytes)")
    if info.st_mode & stat.S_IWOTH:
        raise PermissionError("model file is world-writable; refusing to load it")
    with open(path, "rb") as handle:
        return RestrictedUnpickler(io.BytesIO(handle.read())).load()
