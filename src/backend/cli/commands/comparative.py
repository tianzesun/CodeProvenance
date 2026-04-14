"""Comparative CLI command module."""
import typer
from rich.console import Console
from src.backend.cli.context import initialize_system
from src.backend.bootstrap.plugins.plugin_registry import PluginRegistry

app = typer.Typer()
console = Console()


@app.command()
def run(
    baseline: str = typer.Argument(..., help="Baseline dataset"),
    candidate: str = typer.Argument(..., help="Candidate dataset"),
) -> None:
    """Run comparative analysis between two datasets."""
    initialize_system()
    plugin = PluginRegistry.get("compare")
    result = plugin.run(baseline=baseline, candidate=candidate)
    console.print(result)
