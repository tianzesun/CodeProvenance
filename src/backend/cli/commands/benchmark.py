"""Benchmark CLI command module."""
import typer
from rich.console import Console
from src.backend.cli.context import initialize_system
from src.backend.bootstrap.plugins.plugin_registry import PluginRegistry

app = typer.Typer()
console = Console()


@app.command()
def run(
    dataset: str = typer.Option(..., help="Dataset name"),
    mode: str = typer.Option("full", help="Execution mode"),
) -> None:
    """Run benchmark pipeline."""
    initialize_system()
    plugin = PluginRegistry.get("benchmark")
    result = plugin.run(dataset=dataset, mode=mode)
    console.print(result)
