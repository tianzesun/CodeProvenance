"""
Benchmark tool registry.

Single source of truth for official benchmark participants,
metadata, paths, versions, and enablement state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence


@dataclass(frozen=True)
class ToolSpec:
    """
    Immutable specification for a benchmark tool.
    All metadata required for reproducible execution.
    """
    name: str
    category: str  # external | library | internal
    entry_kind: str  # benchmark_tool | helper_lib | internal_engine
    root_path: Path
    adapter_module: Optional[str] = None
    adapter_class: Optional[str] = None
    version: Optional[str] = None
    supported_languages: Sequence[str] = field(default_factory=tuple)
    enabled: bool = True
    official: bool = True
    notes: str = ""


class ToolRegistry:
    """
    Central registry for all tools used in benchmarking.

    Provides filtered views for official, enabled, and benchmark participant tools.
    This is the single source of truth for tool discovery during orchestration.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """Register a tool specification."""
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        """Get tool specification by name."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def all(self) -> Iterable[ToolSpec]:
        """Get all registered tools."""
        return self._tools.values()

    def official_tools(self) -> list[ToolSpec]:
        """Get all official benchmark tools."""
        return [t for t in self._tools.values() if t.official]

    def enabled_tools(self) -> list[ToolSpec]:
        """Get all currently enabled tools."""
        return [t for t in self._tools.values() if t.enabled]

    def benchmark_tools(self) -> list[ToolSpec]:
        """Get all enabled benchmark participant tools."""
        return [
            t for t in self._tools.values()
            if t.entry_kind == "benchmark_tool" and t.enabled
        ]

    def helper_libs(self) -> list[ToolSpec]:
        """Get all registered helper libraries."""
        return [t for t in self._tools.values() if t.entry_kind == "helper_lib"]


def build_default_registry(base_dir: Path) -> ToolRegistry:
    """
    Build and populate default tool registry with official benchmark v1 tools.

    Args:
        base_dir: Root repository directory

    Returns:
        Populated ToolRegistry instance
    """
    registry = ToolRegistry()

    external = base_dir / "tools" / "external"
    libs = base_dir / "tools" / "libs"

    # Official external benchmark tools
    registry.register(
        ToolSpec(
            name="moss",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "moss",
            adapter_module="src.backend.benchmark.adapters.external.moss_adapter",
            adapter_class="MossAdapter",
            supported_languages=("python", "java", "javascript", "c", "cpp"),
            official=True,
        )
    )

    registry.register(
        ToolSpec(
            name="jplag",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "JPlag",
            adapter_module="src.backend.benchmark.adapters.external.jplag_adapter",
            adapter_class="JPlagAdapter",
            supported_languages=("python", "java", "cpp", "csharp"),
            official=True,
        )
    )

    registry.register(
        ToolSpec(
            name="nicad",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "NiCad-6.2",
            adapter_module="src.backend.benchmark.adapters.external.nicad_adapter",
            adapter_class="NiCadAdapter",
            supported_languages=("python", "java", "c", "cpp"),
            official=True,
        )
    )

    registry.register(
        ToolSpec(
            name="dolos",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "dolos",
            adapter_module="src.backend.benchmark.adapters.external.dolos_adapter",
            adapter_class="DolosAdapter",
            supported_languages=("python", "java", "javascript", "c", "cpp"),
            official=True,
        )
    )

    registry.register(
        ToolSpec(
            name="pmd",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "pmd",
            adapter_module="src.backend.benchmark.adapters.external.pmd_adapter",
            adapter_class="PMDAdapter",
            supported_languages=("java",),
            official=True,
        )
    )

    # Pending external tools (not enabled for v1)
    registry.register(
        ToolSpec(
            name="sherlock",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "Sherlock",
            adapter_module="src.backend.benchmark.adapters.external.sherlock_adapter",
            adapter_class="SherlockAdapter",
            supported_languages=("python", "java"),
            official=False,
            enabled=False,
            notes="Enable after adapter and validation are complete.",
        )
    )

    registry.register(
        ToolSpec(
            name="vendetect",
            category="external",
            entry_kind="benchmark_tool",
            root_path=external / "vendetect-0.0.3",
            adapter_module="src.backend.benchmark.adapters.external.vendetect_adapter",
            adapter_class="VendetectAdapter",
            supported_languages=("python", "java"),
            official=False,
            enabled=False,
            notes="Enable after adapter and validation are complete.",
        )
    )

    # Helper libraries (never benchmarked directly)
    registry.register(
        ToolSpec(
            name="textdistance",
            category="library",
            entry_kind="helper_lib",
            root_path=libs / "textdistance",
            official=False,
            enabled=True,
            notes="Use inside lexical_baseline.py, not as standalone benchmark entrant.",
        )
    )

    registry.register(
        ToolSpec(
            name="py_stringmatching",
            category="library",
            entry_kind="helper_lib",
            root_path=libs / "py_stringmatching",
            official=False,
            enabled=True,
            notes="Use for internal baseline features if needed.",
        )
    )

    registry.register(
        ToolSpec(
            name="fuzzywuzzy",
            category="library",
            entry_kind="helper_lib",
            root_path=libs / "fuzzywuzzy",
            official=False,
            enabled=True,
        )
    )

    registry.register(
        ToolSpec(
            name="sim_metrics",
            category="library",
            entry_kind="helper_lib",
            root_path=libs / "sim_metrics",
            official=False,
            enabled=True,
        )
    )

    return registry
