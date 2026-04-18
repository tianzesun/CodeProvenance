"""Benchmark adapter registry.

Central registry for all official benchmark participants.
Only tools that appear in validation results are registered here.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


class ToolCategory(Enum):
    """Official benchmark tool categories."""

    EXTERNAL_TOOL = "external_tool"
    BASELINE = "baseline"
    INTERNAL = "internal"


@dataclass(frozen=True)
class AdapterMetadata:
    """Metadata for registered benchmark adapters."""

    name: str
    adapter_class: Any
    category: ToolCategory
    supported_languages: List[str]
    is_external_dependency: bool
    enabled: bool
    description: str = ""
    reference_paper: str = ""


class AdapterRegistry:
    """
    Central registry for benchmark adapters.

    Maintains list of official benchmark participants
    and provides generic lookup for orchestration.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, AdapterMetadata] = {}

    def register(
        self,
        name: str,
        adapter_class: Any,
        category: ToolCategory,
        supported_languages: List[str],
        is_external_dependency: bool = False,
        enabled: bool = True,
        description: str = "",
        reference_paper: str = "",
    ) -> None:
        """Register an adapter as official benchmark participant."""
        self._adapters[name] = AdapterMetadata(
            name=name,
            adapter_class=adapter_class,
            category=category,
            supported_languages=supported_languages,
            is_external_dependency=is_external_dependency,
            enabled=enabled,
            description=description,
            reference_paper=reference_paper,
        )

    def get(self, name: str) -> Optional[AdapterMetadata]:
        """Get metadata for a registered adapter."""
        return self._adapters.get(name)

    def list(self, category: Optional[ToolCategory] = None) -> List[AdapterMetadata]:
        """List all registered adapters, optionally filtered by category."""
        adapters = list(self._adapters.values())
        if category:
            adapters = [a for a in adapters if a.category == category]
        return [a for a in adapters if a.enabled]

    def list_names(self, category: Optional[ToolCategory] = None) -> List[str]:
        """List names of registered adapters."""
        return [a.name for a in self.list(category)]


# Global registry instance
adapter_registry = AdapterRegistry()


def initialize_registry() -> None:
    """Initialize registry with official benchmark participants."""
    from .baselines.lexical_baseline import LexicalBaselineAdapter
    from .baselines.ast_baseline import ASTBaselineAdapter
    from .external.moss_adapter import MossAdapter
    from .external.jplag_adapter import JPlagAdapter
    from .external.dolos_adapter import DolosBenchmarkEngine
    from .external.nicad_adapter import NiCadAdapter
    from .external.pmd_adapter import PMDBenchmarkEngine
    from .internal.codeprovenance_engine import CodeProvenanceAdapter

    # Internal baselines
    adapter_registry.register(
        "lexical_baseline",
        LexicalBaselineAdapter,
        ToolCategory.BASELINE,
        ["all"],
        is_external_dependency=False,
        description="Simple n-gram winnowing baseline",
    )

    adapter_registry.register(
        "ast_baseline",
        ASTBaselineAdapter,
        ToolCategory.BASELINE,
        ["python", "java"],
        is_external_dependency=False,
        description="AST histogram structural baseline",
    )

    # External plagiarism tools
    adapter_registry.register(
        "moss",
        MossAdapter,
        ToolCategory.EXTERNAL_TOOL,
        ["all"],
        is_external_dependency=True,
        description="MOSS (Measure Of Software Similarity)",
        reference_paper="Aiken 1998",
    )

    adapter_registry.register(
        "jplag",
        JPlagAdapter,
        ToolCategory.EXTERNAL_TOOL,
        ["java", "python", "c", "cpp", "csharp"],
        is_external_dependency=True,
        description="JPlag code similarity detector",
        reference_paper="Prechelt et al. 2002",
    )

    adapter_registry.register(
        "dolos",
        DolosBenchmarkEngine,
        ToolCategory.EXTERNAL_TOOL,
        ["python", "javascript", "java"],
        is_external_dependency=True,
        description="Dolos plagiarism detector",
        reference_paper="De Sutter et al. 2022",
    )

    adapter_registry.register(
        "nicad",
        NiCadAdapter,
        ToolCategory.EXTERNAL_TOOL,
        ["c", "java", "python"],
        is_external_dependency=True,
        description="NiCad Clone Detector",
        reference_paper="Roy and Cordy 2008",
    )

    adapter_registry.register(
        "pmd",
        PMDBenchmarkEngine,
        ToolCategory.EXTERNAL_TOOL,
        ["java"],
        is_external_dependency=True,
        description="PMD Copy-Paste Detector",
    )

    # Internal engines
    adapter_registry.register(
        "codeprovenance",
        CodeProvenanceAdapter,
        ToolCategory.INTERNAL,
        ["all"],
        is_external_dependency=False,
        description="CodeProvenance core detection engine",
    )
