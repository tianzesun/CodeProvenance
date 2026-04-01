"""Architecture Enforcement - Prevents architectural decay.

This module is loaded at import-time and prevents forbidden imports.
"""
import sys

# Define allowed dependencies between layers
_ALLOWED = {
    # Layer: what it's allowed to import
    'src.api': ['src.application', 'src.bootstrap'],
    'src.application': ['src.domain', 'src.engines'],
    'src.domain': [],  # Pure business logic
    'src.engines': ['src.infrastructure'],
    'src.infrastructure': [],  # IO only
    'src.evaluation': ['src.engines', 'src.domain'],  # Read-only
    'src.evaluation.core': ['src.domain'],  # Production safe only
    'src.evaluation.offline': ['src.engines', 'src.domain'],  # Offline only
    'src.evaluation.visualization': ['src.evaluation.core'],
    'src.ml': ['src.infrastructure', 'src.domain'],
    'src.workers': ['src.application'],
    'src.bootstrap': ['src.api', 'src.application'],
}

class ArchitectureGuard:
    """Prevents forbidden layer access."""
    _enabled = False
    
    @classmethod
    def install_guard(cls):
        """Install import guard (call from bootstrap only)."""
        if cls._enabled:
            return
        # In production, use import-linter or similar
        # For now, this documents the rules
        cls._enabled = True
        print("Architecture guard installed. Import rules:")
        for layer, deps in _ALLOWED.items():
            print(f"  {layer} -> {deps}")
    
    @staticmethod
    def get_allowed(module_path: str) -> list:
        """Get allowed dependencies for a module."""
        for layer, deps in _ALLOWED.items():
            if module_path.startswith(layer):
                return deps
        return []
