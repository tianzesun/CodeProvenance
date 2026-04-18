"""Compatibility namespace for legacy ``src.backend.backend`` imports.

This package intentionally points Python's module resolution at the parent
``src.backend`` directory so older imports continue to work while the backend
package layout is normalized.
"""

from pathlib import Path

_PARENT_PACKAGE_DIR = Path(__file__).resolve().parent.parent

# Expose the parent package tree as this package's import path so imports like
# ``src.backend.backend.main`` resolve to ``src/backend/main.py``.
__path__ = [str(_PARENT_PACKAGE_DIR)]
