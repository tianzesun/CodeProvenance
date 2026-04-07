"""Threshold Analysis CLI Commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.evaluation.threshold_analysis import (
    threshold_sweep,
    find_optimal_threshold,
    global_threshold_override,
)
from src.pipeline.dataset_builders.ground_truth import load_ground_truth_dataset


app = typer.Typer(name="threshold", help="Threshold configuration and analysis tools")
console = Console()


@app.command("set")
def set_global_threshold(
    threshold: float = typer.Argument(
        ..., help="New global threshold value (0.0 - 1.0)"
    ),
) -> None:
    """Set global runtime decision threshold."""
    try:
        old_value = global_threshold_override()
        new_value = global_threshold_override(threshold)
        console.print(f"Global threshold changed: {old_value:.3f} → {new_value:.3f}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("get")
def get_global_threshold() -> None:
    """Display current active global threshold."""
    current = global_threshold_override()
    console.print(f"Current global threshold: {current:.3f}")


@app.command("sweep")
def run_threshold_sweep(
    dataset_path: Path = typer.Argument(
        ..., help="Path to ground truth dataset JSON file"
    ),
    start: float = typer.Option(0.60, help="Starting threshold value"),
    end: float = typer.Option(0.80, help="Ending threshold value"),
    step: float = typer.Option(0.01, help="Step size between thresholds"),
    output_json: Optional[Path] = typer.Option(None, help="Save results to JSON file"),
    output_plot: Optional[Path] = typer.Option(None, help="Save PR curve plot to file"),
    show_table: bool = typer.Option(True, help="Display metrics table"),
) -> None:
    """Run threshold sweep analysis on a ground truth dataset."""
    if not dataset_path.exists():
        console.print(f"[red]Dataset not found: {dataset_path}[/red]")
        raise typer.Exit(1)

    with console.status("Loading dataset..."):
        dataset = load_ground_truth_dataset(dataset_path)
        scores = [item["score"] for item in dataset]
        labels = [item["ground_truth"] for item in dataset]

    with console.status("Running threshold sweep..."):
        result = threshold_sweep(scores, labels, start, end, step)

    console.print("\n[bold green]Threshold Sweep Complete[/bold green]")
    console.print(f"Total samples: {result.total_samples}")
    console.print(f"Positive cases: {result.positive_count}")
    console.print(f"Negative cases: {result.negative_count}")
    console.print(f"AUC-PR: {result.auc_pr:.4f}\n")

    console.print(f"[bold]Optimal Threshold: {result.optimal_threshold:.2f}[/bold]")
    console.print(f"  F1 Score:  {result.optimal_metrics.f1_score:.4f}")
    console.print(f"  Precision: {result.optimal_metrics.precision:.4f}")
    console.print(f"  Recall:    {result.optimal_metrics.recall:.4f}")
    console.print(f"  FPR:       {result.optimal_metrics.false_positive_rate:.4f}")

    if show_table:
        table = Table(
            title="Threshold Metrics", show_header=True, header_style="bold magenta"
        )
        table.add_column("Threshold", justify="right", style="cyan")
        table.add_column("Precision", justify="right")
        table.add_column("Recall", justify="right")
        table.add_column("F1 Score", justify="right", style="green")
        table.add_column("FPR", justify="right", style="red")

        for metrics in result.metrics:
            is_optimal = abs(metrics.threshold - result.optimal_threshold) < 0.0001
            style = "bold green" if is_optimal else None

            table.add_row(
                f"{metrics.threshold:.2f}",
                f"{metrics.precision:.3f}",
                f"{metrics.recall:.3f}",
                f"{metrics.f1_score:.3f}",
                f"{metrics.false_positive_rate:.3f}",
                style=style,
            )

        console.print("\n", table)

    if output_json:
        result.save_json(output_json)
        console.print(f"\nResults saved to: {output_json}")

    if output_plot:
        try:
            result.save_pr_curve(output_plot)
            console.print(f"PR Curve saved to: {output_plot}")
        except ImportError:
            console.print(
                "\n[yellow]Warning: matplotlib not available, plot not generated[/yellow]"
            )


@app.command("optimize")
def optimize_threshold(
    dataset_path: Path = typer.Argument(
        ..., help="Path to ground truth dataset JSON file"
    ),
    metric: str = typer.Option("f1", help="Metric to maximize: f1, precision, recall"),
    set_global: bool = typer.Option(
        False, help="Set found threshold as global default"
    ),
) -> None:
    """Find optimal threshold maximizing specified metric."""
    if not dataset_path.exists():
        console.print(f"[red]Dataset not found: {dataset_path}[/red]")
        raise typer.Exit(1)

    with console.status("Loading dataset..."):
        dataset = load_ground_truth_dataset(dataset_path)
        scores = [item["score"] for item in dataset]
        labels = [item["ground_truth"] for item in dataset]

    with console.status(f"Optimizing threshold for {metric}..."):
        optimal_threshold, metrics = find_optimal_threshold(scores, labels, metric)

    console.print(f"\nOptimal threshold for maximum {metric}:")
    console.print(f"  Threshold: {optimal_threshold:.4f}")
    console.print(f"  F1 Score:  {metrics.f1_score:.4f}")
    console.print(f"  Precision: {metrics.precision:.4f}")
    console.print(f"  Recall:    {metrics.recall:.4f}")
    console.print(
        f"  TP: {metrics.true_positives}, FP: {metrics.false_positives}, TN: {metrics.true_negatives}, FN: {metrics.false_negatives}"
    )

    if set_global:
        global_threshold_override(optimal_threshold)
        console.print(f"\nGlobal threshold set to {optimal_threshold:.4f}")
