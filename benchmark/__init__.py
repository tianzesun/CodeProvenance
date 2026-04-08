"""Compatibility package for legacy ``benchmark.*`` imports.

This top-level directory primarily stores benchmark data, while the Python
implementation lives in ``src/benchmark``. Extending ``__path__`` lets callers
continue importing ``benchmark.datasets`` and friends.
"""

from pathlib import Path

_here = Path(__file__).resolve().parent
_src_pkg = _here.parent / "src" / "benchmark"

if _src_pkg.exists():
    __path__.append(str(_src_pkg))
