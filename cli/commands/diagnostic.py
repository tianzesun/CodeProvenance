"""Diagnostic CLI command module."""
import typer
from rich.console import Console
from cli.context import initialize_system
from engines.registry.plugin_registry import PluginRegistry

app = typer.Typer()
console = Console()


@app.command()
def run(
    job_id: str = typer.Argument(..., help="Job ID to diagnose"),
) -> None:
    """Run diagnostic analysis on a job."""
    initialize_system()
    plugin = PluginRegistry.get("diagnose")
    result = plugin.run(job_id)
    console.print(result)
