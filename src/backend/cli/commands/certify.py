"""Certification CLI command module.

Provides commands for running certification reports with statistical analysis.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="certify", help="Run certification reports")
console = Console()


@app.command()
def run(
    dataset: str = typer.Option(..., help="Dataset name or path to records JSON"),
    engines: Optional[str] = typer.Option(None, help="Comma-separated list of engines to evaluate"),
    baseline: Optional[str] = typer.Option(None, help="Baseline engine for comparisons"),
    output: str = typer.Option("reports/certification", help="Output directory"),
    n_bootstrap: int = typer.Option(2000, help="Number of bootstrap samples"),
    confidence_level: float = typer.Option(0.95, help="Confidence level for intervals"),
    alpha: float = typer.Option(0.05, help="Significance level for tests"),
    seed: int = typer.Option(42, help="Random seed for reproducibility"),
    format: str = typer.Option("all", help="Output format: json, html, all"),
) -> None:
    """Run certification pipeline and generate reports.

    Generates publication-grade certification reports with:
    - Statistical significance tests (McNemar, Wilcoxon)
    - Confidence intervals (bootstrap)
    - Effect sizes (Cohen's d, Cliff's delta)
    - Stratified analysis (clone type, difficulty, language)
    - Reproducibility tracking
    """
    from src.backend.benchmark.certification import (
        CertificationReportBuilder,
        BenchmarkRecord,
    )

    console.print(f"[bold blue]Running certification for dataset: {dataset}[/bold blue]")

    # Load records
    records = _load_records(dataset, engines)

    if not records:
        console.print("[bold red]Error: No records found[/bold red]")
        raise typer.Exit(1)

    console.print(f"Loaded {len(records)} records from {len(set(r.engine for r in records))} engine(s)")

    # Build report
    builder = CertificationReportBuilder(
        baseline_engine=baseline,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        alpha=alpha,
        seed=seed,
    )

    with console.status("[bold green]Building certification report..."):
        report = builder.build(
            records,
            dataset_name=Path(dataset).stem if "/" in dataset else dataset,
        )

    # Display summary
    console.print("\n[bold green]✓ Report generated successfully[/bold green]")
    console.print(f"Report ID: {report.report_id}")
    console.print(f"Engines: {', '.join(report.engines)}")
    console.print(f"Samples: {report.n_samples}")

    # Show main results table
    _display_results_table(report)

    # Save outputs
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    if format in ("json", "all"):
        json_path = output_path / f"{report.report_id}.json"
        report.save_json(json_path)
        console.print(f"[green]✓ JSON report saved: {json_path}[/green]")

    if format in ("html", "all"):
        html_path = output_path / f"{report.report_id}.html"
        report.save_html(html_path)
        console.print(f"[green]✓ HTML report saved: {html_path}[/green]")

    console.print("\n[bold]Report summary:[/bold]")
    console.print(report.executive_summary)


@app.command()
def compare(
    records_a: str = typer.Option(..., help="Path to first engine's records JSON"),
    records_b: str = typer.Option(..., help="Path to second engine's records JSON"),
    name_a: str = typer.Option("Engine A", help="Name for first engine"),
    name_b: str = typer.Option("Engine B", help="Name for second engine"),
    output: str = typer.Option("reports/certification", help="Output directory"),
    n_bootstrap: int = typer.Option(2000, help="Number of bootstrap samples"),
    alpha: float = typer.Option(0.05, help="Significance level"),
    seed: int = typer.Option(42, help="Random seed"),
) -> None:
    """Compare two engines and generate certification report."""
    from src.backend.benchmark.certification import (
        CertificationReportBuilder,
        BenchmarkRecord,
    )

    console.print(f"[bold blue]Comparing {name_a} vs {name_b}[/bold blue]")

    # Load records
    records_list_a = _load_records_from_file(records_a, name_a)
    records_list_b = _load_records_from_file(records_b, name_b)

    if not records_list_a or not records_list_b:
        console.print("[bold red]Error: Could not load records[/bold red]")
        raise typer.Exit(1)

    # Combine records
    all_records = records_list_a + records_list_b

    console.print(f"Loaded {len(records_list_a)} records for {name_a}")
    console.print(f"Loaded {len(records_list_b)} records for {name_b}")

    # Build report
    builder = CertificationReportBuilder(
        baseline_engine=name_a,
        n_bootstrap=n_bootstrap,
        alpha=alpha,
        seed=seed,
    )

    with console.status("[bold green]Building comparison report..."):
        report = builder.build(
            all_records,
            dataset_name=f"{name_a}_vs_{name_b}",
        )

    # Display results
    console.print("\n[bold green]✓ Comparison report generated[/bold green]")
    _display_results_table(report)

    # Show comparison details
    for comp_name, comparison in report.comparisons.items():
        console.print(f"\n[bold]{comp_name}[/bold]")
        console.print(f"  McNemar p-value: {comparison.mcnemar_pvalue:.6f} {'✓' if comparison.mcnemar_significant else '✗'}")
        console.print(f"  Wilcoxon p-value: {comparison.wilcoxon_pvalue:.6f} {'✓' if comparison.wilcoxon_significant else '✗'}")
        console.print(f"  Cohen's d: {comparison.cohens_d:.4f}")
        console.print(f"  Cliff's δ: {comparison.cliffs_delta:.4f}")
        console.print(f"  F1 difference: {comparison.f1_diff:+.4f}")

    # Save outputs
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / f"{report.report_id}.json"
    report.save_json(json_path)
    console.print(f"\n[green]✓ JSON report saved: {json_path}[/green]")

    html_path = output_path / f"{report.report_id}.html"
    report.save_html(html_path)
    console.print(f"[green]✓ HTML report saved: {html_path}[/green]")


def _load_records(dataset: str, engines: Optional[str] = None) -> List:
    """Load benchmark records from dataset.

    Args:
        dataset: Dataset name or path to JSON file.
        engines: Optional comma-separated list of engines to filter.

    Returns:
        List of BenchmarkRecord objects.
    """
    from src.backend.benchmark.certification import BenchmarkRecord

    # Check if it's a file path
    if "/" in dataset or dataset.endswith(".json"):
        return _load_records_from_file(dataset)

    # Otherwise, it's a dataset name - try to load from standard location
    dataset_path = Path("data") / f"{dataset}.json"
    if dataset_path.exists():
        return _load_records_from_file(str(dataset_path))

    console.print(f"[yellow]Warning: Dataset not found: {dataset}[/yellow]")
    return []


def _load_records_from_file(file_path: str, engine_name: Optional[str] = None) -> List:
    """Load records from a JSON file.

    Args:
        file_path: Path to JSON file.
        engine_name: Optional engine name to assign.

    Returns:
        List of BenchmarkRecord objects.
    """
    from src.backend.benchmark.certification import BenchmarkRecord

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return []

    try:
        with open(path) as f:
            data = json.load(f)

        records = []
        if isinstance(data, list):
            for item in data:
                if engine_name and "engine" not in item:
                    item["engine"] = engine_name
                records.append(BenchmarkRecord.from_dict(item))
        elif isinstance(data, dict) and "records" in data:
            for item in data["records"]:
                if engine_name and "engine" not in item:
                    item["engine"] = engine_name
                records.append(BenchmarkRecord.from_dict(item))

        return records
    except Exception as e:
        console.print(f"[red]Error loading records: {e}[/red]")
        return []


def _display_results_table(report) -> None:
    """Display results table in console."""
    table = Table(title="Main Results")
    table.add_column("Engine", style="bold")
    table.add_column("Precision", justify="right")
    table.add_column("Recall", justify="right")
    table.add_column("F1", justify="right")
    table.add_column("Accuracy", justify="right")

    for engine in report.engines:
        metrics = report.main_results.metrics
        precision = metrics.get("Precision", [0.0])[report.engines.index(engine)]
        recall = metrics.get("Recall", [0.0])[report.engines.index(engine)]
        f1 = metrics.get("F1", [0.0])[report.engines.index(engine)]
        accuracy = metrics.get("Accuracy", [0.0])[report.engines.index(engine)]

        table.add_row(
            engine,
            f"{precision:.4f}",
            f"{recall:.4f}",
            f"{f1:.4f}",
            f"{accuracy:.4f}",
        )

    console.print(table)