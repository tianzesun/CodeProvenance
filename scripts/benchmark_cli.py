"""CLI for CodeProvenance Benchmark Framework.

Usage:
    benchmark run --engine hybrid --dataset poj104 --pairs 100
    benchmark compare --engines hybrid,token_winnowing --dataset poj104
    benchmark cv --dataset poj104 --folds 5
    benchmark list-engines
    benchmark list-datasets
"""
import sys
import os
import json

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import click
from benchmark.pipeline import BenchmarkRunner, BenchmarkConfig
from benchmark.pipeline.external_loader import ExternalDatasetLoader
from benchmark.registry import registry


def _get_loader():
    return ExternalDatasetLoader(
        data_root=os.path.join(os.path.dirname(__file__), "data", "datasets"),
        seed=42,
    )


def _load_config(path):
    """Load config from YAML or JSON file."""
    if not os.path.exists(path):
        click.echo(f"Config file not found: {path}", err=True)
        sys.exit(1)
    with open(path) as f:
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml
                data = yaml.safe_load(f)
            except ImportError:
                click.echo("PyYAML not installed. Install with: pip install pyyaml", err=True)
                sys.exit(1)
        else:
            data = json.load(f)
    
    # Normalize flat config to nested structure expected by BenchmarkConfig
    if "metrics" in data and isinstance(data["metrics"], list):
        data["metrics"] = {"metrics": data["metrics"]}
    if "threshold" in data and isinstance(data["threshold"], (int, float)):
        data["threshold"] = {"value": data["threshold"], "optimize": False}
    if "output" in data and isinstance(data["output"], dict):
        pass  # Already nested correctly
    elif "output" not in data:
        data["output"] = {}
    
    return BenchmarkConfig.from_dict(data)


def _format_metrics(result, prefix=""):
    """Format metrics result as a table."""
    lines = []
    if result.success:
        m = result.metrics
        lines.append(f"{prefix}Precision:  {m.precision:.4f}")
        lines.append(f"{prefix}Recall:     {m.recall:.4f}")
        lines.append(f"{prefix}F1 Score:   {m.f1:.4f}")
        lines.append(f"{prefix}Accuracy:   {m.accuracy:.4f}")
        lines.append(f"{prefix}MAP:        {m.map_score:.4f}")
        lines.append(f"{prefix}MRR:        {m.mrr_score:.4f}")
        lines.append(f"{prefix}Threshold:  {m.threshold:.4f}")
        lines.append(f"{prefix}TP/FP/TN/FN: {m.tp}/{m.fp}/{m.tn}/{m.fn}")
    else:
        lines.append(f"{prefix}FAILED: {result.error}")
    return "\n".join(lines)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """CodeProvenance Benchmark Framework CLI."""
    pass


@cli.command()
@click.option("--engine", "-e", default=None, help="Engine name to use.")
@click.option("--dataset", "-d", required=True, help="Dataset name (poj104, bigclonebench, etc.).")
@click.option("--pairs", "-n", default=None, type=int, help="Maximum number of pairs to load.")
@click.option("--split", default="test", help="Dataset split to use.")
@click.option("--threshold", "-t", default=None, type=float, help="Fixed threshold (disables optimization).")
@click.option("--output-dir", "-o", default="reports", help="Output directory for reports.")
@click.option("--json/--no-json", default=None, help="Generate JSON report.")
@click.option("--html/--no-html", default=None, help="Generate HTML report.")
@click.option("--leaderboard/--no-leaderboard", default=None, help="Update leaderboard.")
@click.option("--config", "-c", default=None, help="Path to config file (YAML or JSON).")
def run(engine, dataset, pairs, split, threshold, output_dir, json, html, leaderboard, config):
    """Run benchmark on a single dataset."""
    # Load config file if provided, otherwise use defaults
    if config:
        cfg = _load_config(config)
    else:
        cfg = BenchmarkConfig()

    # CLI options override config file values
    engine_name = engine or cfg.engine.name
    threshold_val = threshold
    json_out = json if json is not None else cfg.output.json
    html_out = html if html is not None else cfg.output.html
    lb_out = leaderboard if leaderboard is not None else cfg.output.leaderboard

    click.echo(f"Running benchmark: {engine_name} on {dataset}")
    click.echo(f"  Pairs: {pairs or 'all'}, Split: {split}")
    click.echo()

    loader = _get_loader()
    try:
        ds = loader.load_by_name(dataset, split=split, max_pairs=pairs)
    except (FileNotFoundError, RuntimeError) as e:
        click.echo(f"Error loading dataset: {e}", err=True)
        sys.exit(1)

    click.echo(f"  Loaded {len(ds.pairs)} pairs ({sum(1 for p in ds.pairs if p.label == 1)} positive, {sum(1 for p in ds.pairs if p.label == 0)} negative)")
    click.echo()

    runner = BenchmarkRunner(seed=42)
    from benchmark.pipeline.config import EngineConfig, OutputConfig, ThresholdConfig
    run_config = BenchmarkConfig(
        engine=EngineConfig(name=engine_name),
        threshold=ThresholdConfig(optimize=(threshold_val is None)),
        output=OutputConfig(json=json_out, html=html_out, leaderboard=lb_out),
    )

    result = runner.run(ds, run_config)

    click.echo("=" * 60)
    click.echo(f"RESULTS - {engine_name} on {dataset}")
    click.echo("=" * 60)
    click.echo(_format_metrics(result))
    click.echo("=" * 60)

    if result.report_paths:
        click.echo()
        click.echo("Reports saved:")
        for fmt, path in result.report_paths.items():
            click.echo(f"  {fmt}: {path}")

    if not result.success:
        sys.exit(1)


@cli.command()
@click.option("--engines", "-e", required=True, help="Comma-separated engine names to compare.")
@click.option("--dataset", "-d", required=True, help="Dataset name.")
@click.option("--pairs", "-n", default=None, type=int, help="Maximum number of pairs.")
@click.option("--split", default="test", help="Dataset split.")
def compare(engines, dataset, pairs, split):
    """Compare multiple engines on a dataset."""
    engine_list = [e.strip() for e in engines.split(",")]
    click.echo(f"Comparing {len(engine_list)} engines on {dataset}: {', '.join(engine_list)}")
    click.echo()

    loader = _get_loader()
    try:
        ds = loader.load_by_name(dataset, split=split, max_pairs=pairs)
    except (FileNotFoundError, RuntimeError) as e:
        click.echo(f"Error loading dataset: {e}", err=True)
        sys.exit(1)

    click.echo(f"  Loaded {len(ds.pairs)} pairs")
    click.echo()

    runner = BenchmarkRunner(seed=42)
    report = runner.run_comparison_report(ds, engine_list)
    click.echo(report)


@cli.command()
@click.option("--dataset", "-d", required=True, help="Dataset name.")
@click.option("--folds", "-k", default=5, type=int, help="Number of CV folds.")
@click.option("--pairs", "-n", default=None, type=int, help="Maximum number of pairs.")
@click.option("--split", default="test", help="Dataset split.")
def cv(dataset, folds, pairs, split):
    """Run cross-validated benchmark."""
    click.echo(f"Cross-validation: {folds} folds on {dataset}")
    click.echo()

    loader = _get_loader()
    try:
        ds = loader.load_by_name(dataset, split=split, max_pairs=pairs)
    except (FileNotFoundError, RuntimeError) as e:
        click.echo(f"Error loading dataset: {e}", err=True)
        sys.exit(1)

    click.echo(f"  Loaded {len(ds.pairs)} pairs")
    click.echo()

    runner = BenchmarkRunner(seed=42)
    config = BenchmarkConfig()
    result = runner.run_cv(ds, config, n_folds=folds)

    click.echo("=" * 60)
    click.echo(f"CV RESULTS - {dataset} ({folds} folds)")
    click.echo("=" * 60)
    click.echo(_format_metrics(result, "  "))
    click.echo("=" * 60)

    if not result.success:
        sys.exit(1)


@cli.command("list-engines")
def list_engines():
    """List all registered detection engines."""
    engines = registry.list_engines()
    click.echo("Registered engines:")
    for name in sorted(engines):
        try:
            instance = registry.get_instance(name)
            desc = getattr(instance, 'description', '')
            if desc:
                click.echo(f"  {name:<30} {desc}")
            else:
                click.echo(f"  {name}")
        except Exception:
            click.echo(f"  {name}")


@cli.command("list-datasets")
def list_datasets():
    """List all available datasets."""
    datasets = {
        "poj104": "Java programs from PKU Online Judge (clone detection)",
        "bigclonebench": "BigCloneBench - Java clone pairs (Type-1 to Type-4)",
        "google_codejam": "Google Code Jam - Python solutions (requires HuggingFace)",
        "codexglue_clone": "CodeXGLUE clone detection (Java)",
        "codexglue_defect": "CodeXGLUE defect detection (C)",
        "codesearchnet": "CodeSearchNet (multi-language)",
        "codesearchnet_python": "CodeSearchNet Python subset",
        "codesearchnet_java": "CodeSearchNet Java subset",
        "kaggle": "Kaggle Student Code plagiarism pairs",
        "human_eval": "HumanEval Python function generation",
        "mbpp": "MBPP Python benchmark problems",
    }
    click.echo("Available datasets:")
    for name, desc in sorted(datasets.items()):
        click.echo(f"  {name:<25} {desc}")


@cli.command()
@click.option("--output", "-o", default="benchmark.yaml", help="Output config file path.")
@click.option("--engine", "-e", default="hybrid", help="Default engine.")
@click.option("--threshold", "-t", default=0.5, type=float, help="Default threshold.")
@click.option("--optimize/--no-optimize", default=True, help="Enable threshold optimization.")
def init_config(output, engine, threshold, optimize):
    """Generate a sample benchmark.yaml config file."""
    config = f"""# CodeProvenance Benchmark Configuration
# Generated by benchmark init-config

engine:
  name: {engine}
  weights:
    token_winnowing: 0.3
    ast_structural: 0.4
    style: 0.3

threshold:
  optimize: {str(optimize).lower()}
  value: {threshold}
  strategy: f1_max

normalizer:
  type: basic

parser:
  type: basic

metrics:
  - precision
  - recall
  - f1
  - accuracy
  - map
  - mrr

output:
  json: true
  html: false
  leaderboard: true
"""
    with open(output, "w") as f:
        f.write(config)
    click.echo(f"Config written to {output}")


@cli.command("list-plugins")
def list_plugins():
    """List installed plugins."""
    try:
        import plugins
        loaded = plugins.load_plugins()
    except ImportError:
        loaded = []

    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    click.echo(f"Plugins directory: {plugins_dir}")
    click.echo()

    if os.path.exists(plugins_dir):
        py_files = [f for f in os.listdir(plugins_dir) if f.endswith(".py") and not f.startswith("_")]
        if py_files:
            click.echo("Plugin files:")
            for f in sorted(py_files):
                status = "✓ loaded" if f[:-3] in loaded else "✗ failed"
                click.echo(f"  {f:<30} {status}")
        else:
            click.echo("No plugin files found.")
    else:
        click.echo("Plugins directory does not exist.")

    click.echo()
    click.echo(f"Total engines registered: {len(registry.list_engines())}")


@cli.command("plugin-create")
@click.argument("name")
def plugin_create(name):
    """Create a new plugin template."""
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    os.makedirs(plugins_dir, exist_ok=True)

    filepath = os.path.join(plugins_dir, f"{name}.py")
    if os.path.exists(filepath):
        click.echo(f"Plugin '{name}' already exists at {filepath}", err=True)
        sys.exit(1)

    class_name = "".join(w.capitalize() for w in name.split("_")) + "Engine"
    template = f'''"""{name} detection engine plugin."""
from benchmark.similarity.base_engine import BaseSimilarityEngine


class {class_name}(BaseSimilarityEngine):
    """Custom detection engine: {name}."""

    def name(self) -> str:
        return "{name}"

    def description(self) -> str:
        return "Custom {name} detection engine"

    def compare(self, code1: str, code2: str) -> float:
        """Compute similarity between two code snippets.

        Args:
            code1: First code snippet.
            code2: Second code snippet.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        # TODO: Implement your similarity logic here
        return 0.5
'''
    with open(filepath, "w") as f:
        f.write(template)
    click.echo(f"Plugin template created: {filepath}")
    click.echo("Edit the file and run 'benchmark list-plugins' to verify.")


if __name__ == "__main__":
    cli()
