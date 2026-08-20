"""Execution engine for external plagiarism detection tools."""

from .adapter_layer import (
    AdapterRegistry,
    DolosAdapter,
    JPlagAdapter,
    MossAdapter,
    NiCadAdapter,
    ToolFinding,
    adapt_tool_output,
)
from .execution_engine import (
    BaseToolRunner,
    DeterministicEnv,
    DolosRunner,
    ExecutionEngine,
    ExecutionResult,
    JPlagRunner,
    MossRunner,
    NiCadRunner,
    SandboxExecutor,
)

__all__ = [
    "AdapterRegistry",
    "BaseToolRunner",
    "DeterministicEnv",
    "DolosAdapter",
    "DolosRunner",
    "ExecutionEngine",
    "ExecutionResult",
    "JPlagAdapter",
    "JPlagRunner",
    "MossAdapter",
    "MossRunner",
    "NiCadAdapter",
    "NiCadRunner",
    "SandboxExecutor",
    "ToolFinding",
    "adapt_tool_output",
]
