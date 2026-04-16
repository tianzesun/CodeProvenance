"""Unified Benchmark Pipeline.

Single authoritative execution model for all datasets, engines, metrics, and reports.
All evaluation must execute through this pipeline - no bypassing.
"""

# Thin package __init__.py with no module imports
# Import directly from submodules to avoid circular import cycles
__all__: list[str] = []

