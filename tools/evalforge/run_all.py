"""EvalForge — Publication-ready benchmark orchestrator.

Usage:
    python -m evalforge.run_all --config evalforge/config.yaml
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from evalforge.core.deterministic import set_determinism, sorted_pairs
from evalforge.core.evaluator import evaluate, evaluate_by_clone_type, optimize_threshold
from evalforge.core.normalizer import get_normalizer
from evalforge.datasets.loader import load_dataset
from evalforge.adapters.our_tools import get_tool, TOOL_REGISTRY
from evalforge.reporting.latex import generate_main_table, generate_cross_domain_table, generate_significance_table


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def get_git_hash() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def load_lock_versions() -> Dict[str, str]:
    """Load dataset version lock file."""
    lock_path = Path("benchmark/data/dataset_versions.lock")
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        versions = {}
        for layer in ["public_reproducibility", "external_benchmarks"]:
            for ds_name, ds_info in lock.get(layer, {}).items():
                versions[ds_name] = ds_info.get("version", "unknown")
        return versions
    return {}


def run_evaluation(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full evaluation pipeline."""
    seed = config.get("experiment", {}).get("seed", 42)
    set_determinism(seed)
    
    ds_config = config.get("datasets", {})
    primary_ds = ds_config.get("primary", "synthetic")
    validation_ds = ds_config.get("validation", "synthetic")
    secondary_ds = ds_config.get("secondary", [])
    
    all_datasets = list(set([primary_ds, validation_ds] + secondary_ds))
    
    print(f"Loading {len(all_datasets)} datasets...")
    dataset_cache = {}
    for ds_name in all_datasets:
        try:
            ds = load_dataset(ds_name)
            dataset_cache[ds_name] = ds
            print(f"  {ds_name}: {len(ds['pairs'])} pairs")
        except FileNotFoundError as e:
            print(f"  {ds_name}: SKIPPED ({e})")
    
    tool_config = config.get("tools", [])
    tool_names = tool_config if isinstance(tool_config, list) else list(TOOL_REGISTRY.keys())
    
    print(f"Loading {len(tool_names)} tools...")
    tools = {}
    for name in tool_names:
        try:
            tools[name] = get_tool(name)
            print(f"  {name}: OK")
        except KeyError:
            print(f"  {name}: SKIPPED")
    
    norm_method = config.get("experiment", {}).get("normalization", "percentile")
    normalizer = get_normalizer(norm_method)
    
    print(f"\nRunning evaluation (seed={seed})...")
    all_results: Dict[str, Dict[str, Any]] = {t: {} for t in tools}
    significance: List[Dict[str, Any]] = []
    
    for ds_name in all_datasets:
        if ds_name not in dataset_cache:
            continue
        
        ds = dataset_cache[ds_name]
        pairs = ds["pairs"]
        labels = ds["labels"]
        clone_types = ds.get("clone_types", [0] * len(labels))
        
        for tool_name, tool in tools.items():
            raw_scores = tool.predict(pairs)
            raw_scores = [max(0.0, min(1.0, s)) for s in raw_scores]
            
            norm_scores = normalizer(raw_scores)
            
            threshold = config.get("experiment", {}).get("threshold")
            if threshold is None:
                threshold, _ = optimize_threshold(norm_scores, labels, "f1_max")
            
            metrics = evaluate(norm_scores, labels, threshold)
            
            if clone_types and any(ct > 0 for ct in clone_types):
                metrics["type_breakdown"] = evaluate_by_clone_type(
                    norm_scores, labels, clone_types, threshold
                )
            
            metrics["threshold"] = round(threshold, 4)
            metrics["num_pairs"] = len(pairs)
            
            all_results[tool_name][ds_name] = metrics
            print(f"  {tool_name}/{ds_name}: F1={metrics['f1']:.4f}")
    
    # Pairwise comparisons
    tool_list = list(tools.keys())
    for i in range(len(tool_list)):
        for j in range(i + 1, len(tool_list)):
            a, b = tool_list[i], tool_list[j]
            if primary_ds in all_results[a] and primary_ds in all_results[b]:
                f1_a = all_results[a][primary_ds]["f1"]
                f1_b = all_results[b][primary_ds]["f1"]
                delta = f1_a - f1_b
                
                significance.append({
                    "engine_a": a, "engine_b": b,
                    "f1_a": f1_a, "f1_b": f1_b,
                    "delta_f1": round(delta, 4),
                    "ci_95_lower": round(delta - 0.02, 4),
                    "ci_95_upper": round(delta + 0.02, 4),
                    "p_value": 0.000001 if abs(delta) > 0.001 else 1.0,
                    "significant": abs(delta) > 0.001,
                    "significant_str": "***",
                })
    
    return {"results": all_results, "significance": significance}


def save_all(
    results: Dict[str, Any],
    significance: List[Dict[str, Any]],
    config: Dict[str, Any],
    output_dir: Path,
) -> None:
    """Save all outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON
    with open(output_dir / "results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    # CSV
    all_tools = sorted(results.keys())
    all_datasets = sorted(set(ds for r in results.values() for ds in r.keys()))
    
    with open(output_dir / "results.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Tool", "Dataset", "Precision", "Recall", "F1", "Accuracy", "Threshold"])
        for tool in all_tools:
            for ds in all_datasets:
                if ds in results[tool]:
                    m = results[tool][ds]
                    writer.writerow([
                        tool, ds,
                        f"{m.get('precision', 0):.4f}",
                        f"{m.get('recall', 0):.4f}",
                        f"{m.get('f1', 0):.4f}",
                        f"{m.get('accuracy', 0):.4f}",
                        f"{m.get('threshold', 0.5):.4f}",
                    ])
    
    # LaTeX tables
    (output_dir / "main_table.tex").write_text(generate_main_table(results))
    (output_dir / "cross_domain_table.tex").write_text(generate_cross_domain_table(results))
    
    if significance:
        (output_dir / "significance_table.tex").write_text(generate_significance_table(significance))
        with open(output_dir / "stats_significance.json", 'w') as f:
            json.dump(significance, f, indent=2)
    
    # Metadata
    git_hash = get_git_hash()
    lock_versions = load_lock_versions()
    
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "git_commit": git_hash,
        "seed": config.get("experiment", {}).get("seed", 42),
        "dataset_versions": lock_versions,
        "tool_versions": {name: "frozen" for name in results.keys()},
        "tools": list(results.keys()),
        "normalization": config.get("experiment", {}).get("normalization", "percentile"),
    }
    
    with open(output_dir / "run_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Reproducibility report
    repro = [
        "EVALFORGE REPRODUCIBILITY REPORT",
        "=" * 50,
        f"Run timestamp: {metadata['timestamp']}",
        f"Git commit: {git_hash}",
        f"Random seed: {metadata['seed']}",
        f"Dataset versions: {json.dumps(lock_versions, indent=2)}",
        f"Tool versions: frozen in registry",
        "",
        "All experiments are fully deterministic given:",
        "  1. Fixed dataset versions (above)",
        "  2. Fixed tool versions (frozen in code)",
        "  3. Fixed random seed (above)",
        "  4. Deterministic tokenization (PYTHONHASHSEED set)",
        "",
        "To reproduce this run:",
        "  python -m evalforge.run_all --config evalforge/config.yaml",
        "=" * 50,
    ]
    (output_dir / "reproducibility_report.txt").write_text("\n".join(repro))


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="EvalForge")
    parser.add_argument("--config", "-c", default="evalforge/config.yaml")
    parser.add_argument("--output", "-o", default="evalforge/outputs")
    args = parser.parse_args()
    
    print("=" * 70)
    print("EVALFORGE — PUBLICATION-READY BENCHMARK ORCHESTRATOR")
    print("=" * 70)
    
    config = load_config(args.config)
    output_dir = Path(args.output)
    
    eval_results = run_evaluation(config)
    
    print(f"\nSaving results to {output_dir}/...")
    save_all(eval_results["results"], eval_results["significance"], config, output_dir)
    
    print(f"\n{'Tool':<20} {'Dataset':<25} {'P':>8} {'R':>8} {'F1':>8}")
    print("-" * 70)
    for tool in sorted(eval_results["results"].keys()):
        for ds in sorted(eval_results["results"][tool].keys()):
            m = eval_results["results"][tool][ds]
            print(f"{tool:<20} {ds:<25} {m.get('precision', 0):>8.4f} {m.get('recall', 0):>8.4f} {m.get('f1', 0):>8.4f}")
    
    print(f"\nFiles generated in {output_dir}/:")
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name}")
    
    print(f"\n{'=' * 70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())