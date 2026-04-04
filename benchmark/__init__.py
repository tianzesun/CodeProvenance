"""Namespace package bridge: benchmark -> src.benchmark"""
import sys
import os
from pkgutil import extend_path

_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

__path__ = extend_path(__path__, __name__)
