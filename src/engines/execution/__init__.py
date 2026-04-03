"""Execution engine for external plagiarism detection tools."""
from .execution_engine import (
    ExecutionEngine,
    ExecutionResult,
    BaseToolRunner,
    MossRunner,
    JPlagRunner,
    DolosRunner,
    NiCadRunner,
    SandboxExecutor,
    DeterministicEnv,
)
from .adapter_layer import (
    MossAdapter,
    JPlagAdapter,
    DolosAdapter,
    NiCadAdapter,
    AdapterRegistry,
    ToolFinding,
    adapt_tool_output,
)

__all__ = [
    "ExecutionEngine",
    "ExecutionResult",
    "BaseToolRunner",
    "MossRunner",
    "JPlagRunner",
    "DolosRunner",
    "NiCadRunner",
    "SandboxExecutor",
    "DeterministicEnv",
    "MossAdapter",
    "JPlagAdapter",
    "DolosAdapter",
    "NiCadAdapter",
    "AdapterRegistry",
    "ToolFinding",
    "adapt_tool_output",
]
