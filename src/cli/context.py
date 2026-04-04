"""CLI context and configuration."""
from dataclasses import dataclass
from src.bootstrap.plugins.discovery import discover_plugins
from src.bootstrap.architecture_guard import main as guard


@dataclass
class CLIConfig:
    """CLI configuration."""
    verbose: bool = False
    debug: bool = False


def initialize_system() -> None:
    """Initialize system: run architecture guard and discover plugins.

    Raises:
        RuntimeError: If architecture violations are detected.
    """
    code = guard()
    if code != 0:
        raise RuntimeError("Architecture violation detected")
    discover_plugins()


def ensure_safe_runtime() -> None:
    """Run architecture guard before CLI execution.

    Raises:
        RuntimeError: If architecture violations are detected.
    """
    code = guard()
    if code != 0:
        raise RuntimeError("Architecture violation detected")
