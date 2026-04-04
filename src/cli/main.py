"""Unified CLI entrypoint for CodeProvenance benchmark and evaluation system."""
import sys
import os

# Add both project root and src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import typer
from rich.console import Console
from src.cli.commands import benchmark, comparative, diagnostic, dataset, certify
from src.cli.context import initialize_system

app = typer.Typer(
    name="system",
    help="Unified execution CLI for benchmark + evaluation system",
    add_completion=False,
)

console = Console()

# Subcommands
app.add_typer(benchmark.app, name="benchmark", help="Run benchmark pipelines")
app.add_typer(comparative.app, name="compare", help="Comparative analysis")
app.add_typer(diagnostic.app, name="diagnose", help="Diagnostic analysis")
app.add_typer(dataset.app, name="dataset", help="Dataset management")
app.add_typer(certify.app, name="certify", help="Run certification reports with statistical analysis")


@app.callback()
def global_entry() -> None:
    """Global pre-execution hook - runs architecture guard and discovers plugins."""
    initialize_system()


if __name__ == "__main__":
    app()
