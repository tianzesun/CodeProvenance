"""Root benchmark package - extends src/benchmark/."""
import sys
from pathlib import Path

_src = Path(__file__).resolve().parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import pkgutil
__path__ = pkgutil.extend_path(__path__, __name__)
