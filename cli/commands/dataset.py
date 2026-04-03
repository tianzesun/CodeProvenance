"""Dataset CLI command module."""
import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def list() -> None:
    """List available datasets."""
    console.print("[bold]Available datasets:[/bold]")
    # TODO: Implement dataset listing


@app.command()
def info(
    name: str = typer.Argument(..., help="Dataset name"),
) -> None:
    """Show dataset information."""
    console.print(f"[bold]Dataset info:[/bold] {name}")
    # TODO: Implement dataset info