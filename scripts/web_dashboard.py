"""Web Dashboard for CodeProvenance Benchmark Framework.

Styled after artificialanalysis.ai/leaderboards/models.

Usage:
    ./venv/bin/python web_dashboard.py          # Start on port 5000
    ./venv/bin/python web_dashboard.py --port 8080
"""
import sys
import os
import json
import glob as _glob
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flask import Flask, jsonify, render_template_string, request

from benchmark.pipeline import BenchmarkRunner, BenchmarkConfig
from benchmark.pipeline.config import EngineConfig, OutputConfig, ThresholdConfig
from benchmark.pipeline.external_loader import ExternalDatasetLoader
from benchmark.registry import registry

# Auto-load plugins
try:
    import plugins
    plugins.load_plugins()
except ImportError:
    pass

app = Flask(__name__)

# Shared state
_running_benchmarks = {}
_benchmark_results = []
_data_root = os.path.join(os.path.dirname(__file__), "data", "datasets")
_reports_dir = os.path.join(os.path.dirname(__file__), "reports")


def _get_loader():
    return ExternalDatasetLoader(data_root=_data_root, seed=42)


def _load_leaderboard():
    lb_path = os.path.join(_reports_dir, "leaderboard", "leaderboard.json")
    if os.path.exists(lb_path):
        with open(lb_path) as f:
            return json.load(f)
    return {"entries": [], "total_entries": 0}


def _load_recent_reports():
    reports = []
    json_dir = os.path.join(_reports_dir, "json")
    if os.path.exists(json_dir):
        files = sorted(_glob.glob(os.path.join(json_dir, "*.json")), reverse=True)
        for f in files[:20]:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                reports.append({
                    "file": os.path.basename(f),
                    "path": f,
                    "timestamp": os.path.basename(f).replace("benchmark_", "").replace(".json", ""),
                    "data": data,
                })
            except Exception:
                continue
    return reports


def _run_benchmark_task(task_id, engine, dataset, pairs, split):
    """Background task to run benchmark."""
    try:
        _running_benchmarks[task_id]["status"] = "running"
        loader = _get_loader()
        ds = loader.load_by_name(dataset, split=split, max_pairs=pairs)
        runner = BenchmarkRunner(seed=42)
        config = BenchmarkConfig(
            engine=EngineConfig(name=engine),
            threshold=ThresholdConfig(optimize=True),
            output=OutputConfig(json=True, html=True, leaderboard=True),
        )
        result = runner.run(ds, config)
        _running_benchmarks[task_id]["status"] = "completed"
        _running_benchmarks[task_id]["result"] = {
            "success": result.success,
            "error": result.error,
            "engine": engine,
            "dataset": dataset,
            "pairs": len(ds.pairs),
            "metrics": {
                "precision": result.metrics.precision,
                "recall": result.metrics.recall,
                "f1": result.metrics.f1,
                "accuracy": result.metrics.accuracy,
                "map_score": result.metrics.map_score,
                "mrr_score": result.metrics.mrr_score,
                "threshold": result.metrics.threshold,
                "tp": result.metrics.tp,
                "fp": result.metrics.fp,
                "tn": result.metrics.tn,
                "fn": result.metrics.fn,
            },
            "report_paths": result.report_paths,
        }
        _benchmark_results.append(_running_benchmarks[task_id]["result"])
    except Exception as e:
        _running_benchmarks[task_id]["status"] = "failed"
        _running_benchmarks[task_id]["error"] = str(e)


# ---- Dashboard Route ----

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE)


# ---- API Routes ----

@app.route("/api/engines")
def api_engines():
    engines = registry.list_engines()
    return jsonify({
        "engines": [
            {"name": name, "class": cls.__name__}
            for name, cls in sorted(engines.items())
        ]
    })


@app.route("/api/datasets")
def api_datasets():
    datasets = {
        "poj104": {"language": "Java", "description": "PKU Online Judge clone detection"},
        "bigclonebench": {"language": "Java", "description": "BigCloneBench - Java clone pairs"},
        "google_codejam": {"language": "Python", "description": "Google Code Jam solutions"},
        "codexglue_clone": {"language": "Java", "description": "CodeXGLUE clone detection"},
        "codexglue_defect": {"language": "C", "description": "CodeXGLUE defect detection"},
        "codesearchnet_python": {"language": "Python", "description": "CodeSearchNet Python"},
        "codesearchnet_java": {"language": "Java", "description": "CodeSearchNet Java"},
        "kaggle": {"language": "Python", "description": "Kaggle Student Code"},
        "human_eval": {"language": "Python", "description": "HumanEval"},
        "mbpp": {"language": "Python", "description": "MBPP Python benchmark"},
    }
    return jsonify({"datasets": datasets})


@app.route("/api/leaderboard")
def api_leaderboard():
    return jsonify(_load_leaderboard())


@app.route("/api/reports")
def api_reports():
    reports = _load_recent_reports()
    return jsonify({"reports": reports})


@app.route("/api/benchmark/run", methods=["POST"])
def api_run_benchmark():
    data = request.get_json()
    engine = data.get("engine", "hybrid")
    dataset = data.get("dataset")
    pairs = data.get("pairs")
    split = data.get("split", "test")
    if not dataset:
        return jsonify({"error": "Dataset is required"}), 400
    task_id = f"task_{int(time.time() * 1000)}"
    _running_benchmarks[task_id] = {
        "task_id": task_id, "engine": engine, "dataset": dataset,
        "status": "queued", "started_at": datetime.now().isoformat(),
    }
    thread = threading.Thread(target=_run_benchmark_task, args=(task_id, engine, dataset, pairs, split))
    thread.daemon = True
    thread.start()
    return jsonify({"task_id": task_id, "status": "queued"})


@app.route("/api/benchmark/status/<task_id>")
def api_benchmark_status(task_id):
    if task_id not in _running_benchmarks:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(_running_benchmarks[task_id])


@app.route("/api/benchmark/history")
def api_benchmark_history():
    return jsonify({"results": _benchmark_results[-50:]})


@app.route("/api/compare", methods=["POST"])
def api_compare():
    data = request.get_json()
    engines = data.get("engines", [])
    dataset = data.get("dataset")
    pairs = data.get("pairs")
    split = data.get("split", "test")
    if not dataset or not engines:
        return jsonify({"error": "Dataset and engines are required"}), 400
    loader = _get_loader()
    try:
        ds = loader.load_by_name(dataset, split=split, max_pairs=pairs)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    runner = BenchmarkRunner(seed=42)
    results = {}
    for engine in engines:
        config = BenchmarkConfig(
            engine=EngineConfig(name=engine),
            threshold=ThresholdConfig(optimize=True),
            output=OutputConfig(json=False, html=False, leaderboard=False),
        )
        result = runner.run(ds, config)
        results[engine] = {
            "success": result.success, "error": result.error,
            "metrics": {
                "precision": result.metrics.precision, "recall": result.metrics.recall,
                "f1": result.metrics.f1, "accuracy": result.metrics.accuracy,
                "map_score": result.metrics.map_score, "mrr_score": result.metrics.mrr_score,
                "threshold": result.metrics.threshold,
                "tp": result.metrics.tp, "fp": result.metrics.fp,
                "tn": result.metrics.tn, "fn": result.metrics.fn,
            } if result.success else None,
        }
    return jsonify({"results": results, "dataset": dataset, "pairs": len(ds.pairs)})


@app.route("/api/export/csv")
def api_export_csv():
    """Export leaderboard data as CSV."""
    import csv
    import io
    data = _load_leaderboard()
    entries = data.get("entries", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Engine", "Dataset", "Precision", "Recall", "F1", "Accuracy", "MAP", "MRR", "Threshold", "Timestamp"])
    for e in entries:
        writer.writerow([
            e.get("engine", ""), e.get("dataset", ""),
            e.get("precision", ""), e.get("recall", ""),
            e.get("f1", ""), e.get("accuracy", ""),
            e.get("map_score", ""), e.get("mrr_score", ""),
            e.get("threshold", ""), e.get("timestamp", ""),
        ])
    output.seek(0)
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=leaderboard.csv"})


@app.route("/api/export/markdown")
def api_export_markdown():
    """Export leaderboard data as Markdown table."""
    data = _load_leaderboard()
    entries = data.get("entries", [])
    lines = [
        "# CodeProvenance Benchmark Leaderboard",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "| # | Engine | Dataset | Precision | Recall | F1 | Accuracy | MAP | MRR | Threshold | Timestamp |",
        "|---|--------|---------|-----------|--------|-----|----------|-----|-----|-----------|-----------|",
    ]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"| {i} | {e.get('engine','')} | {e.get('dataset','')} | "
            f"{e.get('precision','—')} | {e.get('recall','—')} | "
            f"{e.get('f1','—')} | {e.get('accuracy','—')} | "
            f"{e.get('map_score','—')} | {e.get('mrr_score','—')} | "
            f"{e.get('threshold','—')} | {e.get('timestamp','—')} |"
        )
    from flask import Response
    return Response("\n".join(lines), mimetype="text/markdown",
                    headers={"Content-Disposition": "attachment; filename=leaderboard.md"})


@app.route("/api/export/json")
def api_export_json():
    """Export leaderboard data as JSON."""
    data = _load_leaderboard()
    from flask import Response
    return Response(json.dumps(data, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=leaderboard.json"})


@app.route("/api/plugins")
def api_plugins():
    """List loaded plugins and available plugin files."""
    import glob as _glob
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    plugin_files = []
    if os.path.exists(plugins_dir):
        plugin_files = [os.path.basename(f) for f in _glob.glob(os.path.join(plugins_dir, "*.py")) if not os.path.basename(f).startswith("_")]

    engines = registry.list_engines()
    plugin_engines = []
    builtin_engines = []
    for name, cls in sorted(engines.items()):
        info = {"name": name, "class": cls.__name__}
        try:
            instance = registry.get_instance(name)
            info["description"] = getattr(instance, 'description', lambda: '')() if callable(getattr(instance, 'description', None)) else getattr(instance, 'description', '')
        except Exception:
            info["description"] = ''
        if any(name == pf[:-3] for pf in plugin_files):
            plugin_engines.append(info)
        else:
            builtin_engines.append(info)

    return jsonify({
        "plugin_files": sorted(plugin_files),
        "plugin_engines": plugin_engines,
        "builtin_engines": builtin_engines,
    })


@app.route("/api/engine/<name>")
def api_engine_detail(name):
    """Get detailed metrics for a specific engine across all datasets."""
    data = _load_leaderboard()
    entries = data.get("entries", [])
    engine_results = [e for e in entries if e.get("engine") == name]
    
    if not engine_results:
        return jsonify({"error": "Engine not found"}), 404
    
    # Calculate aggregate metrics
    metrics_by_dataset = {}
    for entry in engine_results:
        ds = entry.get("dataset", "unknown")
        metrics_by_dataset[ds] = {
            "precision": entry.get("precision", 0),
            "recall": entry.get("recall", 0),
            "f1": entry.get("f1", 0),
            "accuracy": entry.get("accuracy", 0),
            "map_score": entry.get("map_score", 0),
            "mrr_score": entry.get("mrr_score", 0),
            "threshold": entry.get("threshold", 0),
            "timestamp": entry.get("timestamp", ""),
        }
    
    # Calculate overall averages
    avg_metrics = {}
    for key in ["precision", "recall", "f1", "accuracy", "map_score", "mrr_score"]:
        values = [m[key] for m in metrics_by_dataset.values() if m[key] > 0]
        avg_metrics[key] = sum(values) / len(values) if values else 0
    
    return jsonify({
        "engine": name,
        "total_runs": len(engine_results),
        "datasets": metrics_by_dataset,
        "average_metrics": avg_metrics,
    })


@app.route("/api/dataset/<name>")
def api_dataset_detail(name):
    """Get detailed metrics for a specific dataset across all engines."""
    data = _load_leaderboard()
    entries = data.get("entries", [])
    dataset_results = [e for e in entries if e.get("dataset") == name]
    
    if not dataset_results:
        return jsonify({"error": "Dataset not found"}), 404
    
    # Group by engine
    engine_results = {}
    for entry in dataset_results:
        eng = entry.get("engine", "unknown")
        engine_results[eng] = {
            "precision": entry.get("precision", 0),
            "recall": entry.get("recall", 0),
            "f1": entry.get("f1", 0),
            "accuracy": entry.get("accuracy", 0),
            "map_score": entry.get("map_score", 0),
            "mrr_score": entry.get("mrr_score", 0),
            "threshold": entry.get("threshold", 0),
            "timestamp": entry.get("timestamp", ""),
        }
    
    return jsonify({
        "dataset": name,
        "total_runs": len(dataset_results),
        "engines": engine_results,
    })


# ---- HTML Template (Artificial Analysis style) ----

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeProvenance — Benchmark Leaderboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #06060b;
            --surface: rgba(18, 18, 30, 0.7);
            --surface-solid: #12121e;
            --surface-2: rgba(26, 26, 42, 0.6);
            --surface-3: rgba(34, 34, 52, 0.5);
            --border: rgba(255,255,255,0.06);
            --border-hover: rgba(255,255,255,0.12);
            --text: #e8e8f0;
            --text-dim: #9090a8;
            --text-muted: #55556a;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --accent-glow: rgba(99,102,241,0.3);
            --green: #34d399;
            --green-dim: #16a34a;
            --red: #f87171;
            --yellow: #fbbf24;
            --blue: #60a5fa;
            --orange: #fb923c;
            --cyan: #22d3ee;
            --pink: #f472b6;
            --radius: 16px;
            --radius-sm: 10px;
            --radius-xs: 6px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated gradient background */
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background:
                radial-gradient(ellipse 80% 60% at 20% 10%, rgba(99,102,241,0.08) 0%, transparent 60%),
                radial-gradient(ellipse 60% 80% at 80% 80%, rgba(34,211,238,0.06) 0%, transparent 50%),
                radial-gradient(ellipse 50% 50% at 50% 50%, rgba(244,114,182,0.04) 0%, transparent 60%);
            pointer-events: none;
            z-index: 0;
            animation: bgShift 20s ease-in-out infinite alternate;
        }
        @keyframes bgShift {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.05); }
            100% { opacity: 1; transform: scale(1); }
        }

        /* Noise texture overlay */
        body::after {
            content: '';
            position: fixed;
            inset: 0;
            opacity: 0.03;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
            pointer-events: none;
            z-index: 0;
        }

        *, *::before, *::after { position: relative; z-index: 1; }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-hover); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

        /* Header */
        .header {
            background: rgba(10, 10, 18, 0.8);
            backdrop-filter: blur(20px) saturate(1.5);
            -webkit-backdrop-filter: blur(20px) saturate(1.5);
            border-bottom: 1px solid var(--border);
            padding: 0 2rem;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-brand { display: flex; align-items: center; gap: 0.6rem; cursor: pointer; }
        .header-brand .logo {
            width: 28px; height: 28px;
            background: linear-gradient(135deg, var(--accent), var(--cyan));
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 900; font-size: 0.75rem; color: white;
        }
        .header-brand h1 {
            font-size: 1rem; font-weight: 800; letter-spacing: -0.03em;
            background: linear-gradient(135deg, var(--text) 0%, var(--text-dim) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .nav { display: flex; gap: 0.2rem; }
        .nav a {
            color: var(--text-muted); text-decoration: none; padding: 0.45rem 0.9rem;
            border-radius: var(--radius-xs); font-size: 0.8rem; font-weight: 500; cursor: pointer;
            transition: all 0.2s ease;
        }
        .nav a:hover { color: var(--text-dim); background: rgba(255,255,255,0.04); }
        .nav a.active {
            color: var(--text); background: rgba(99,102,241,0.12);
            box-shadow: 0 0 0 1px rgba(99,102,241,0.2);
        }

        /* Main */
        .container { max-width: 1600px; margin: 0 auto; padding: 1.5rem 2rem; }

        /* Page transitions */
        .page {
            display: none;
            animation: pageIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .page.active { display: block; }
        @keyframes pageIn {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Hero stats */
        .hero-stats {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem; margin-bottom: 1.5rem;
        }
        .hero-stat {
            background: var(--surface);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.25rem 1.5rem;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            overflow: hidden;
            cursor: pointer;
        }
        .hero-stat::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
        }
        .hero-stat:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .hero-stat .label {
            font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.08em; font-weight: 600;
        }
        .hero-stat .value {
            font-size: 1.75rem; font-weight: 800; margin-top: 0.35rem;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, var(--text), var(--text-dim));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .hero-stat .value.green {
            background: linear-gradient(135deg, var(--green), var(--cyan));
            -webkit-background-clip: text; background-clip: text;
        }
        .hero-stat .value.accent {
            background: linear-gradient(135deg, var(--accent-light), var(--pink));
            -webkit-background-clip: text; background-clip: text;
        }
        .hero-stat .sub { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }

        /* Top badges */
        .top-badges { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
        .top-badge {
            background: var(--surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1rem 1.25rem; flex: 1; min-width: 240px;
            transition: all 0.3s ease;
        }
        .top-badge:hover { border-color: var(--border-hover); }
        .top-badge::before {
            content: '';
            position: absolute; top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
        }
        .top-badge .cat {
            font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.08em; font-weight: 700;
            display: flex; align-items: center; gap: 0.4rem;
        }
        .top-badge .cat .dot {
            width: 6px; height: 6px; border-radius: 50%;
        }
        .top-badge .cat .dot.f1 { background: var(--green); box-shadow: 0 0 8px var(--green); }
        .top-badge .cat .dot.prec { background: var(--blue); box-shadow: 0 0 8px var(--blue); }
        .top-badge .cat .dot.rec { background: var(--orange); box-shadow: 0 0 8px var(--orange); }
        .top-badge .engines { display: flex; gap: 0.4rem; margin-top: 0.6rem; flex-wrap: wrap; }
        .top-badge .engine-tag {
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            border-radius: var(--radius-xs);
            padding: 0.25rem 0.55rem;
            font-size: 0.72rem; font-weight: 500;
            font-family: 'JetBrains Mono', monospace;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .top-badge .engine-tag:hover { background: rgba(255,255,255,0.08); }
        .top-badge .engine-tag.first {
            border-color: rgba(52,211,153,0.3);
            color: var(--green);
            background: rgba(52,211,153,0.08);
        }

        /* Filters bar */
        .filters-bar {
            background: var(--surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 0.75rem 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .filter-group { display: flex; align-items: center; gap: 0.4rem; }
        .filter-group label { font-size: 0.75rem; color: var(--text-muted); font-weight: 500; white-space: nowrap; }
        .filter-group select, .filter-group input {
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 0.4rem 0.75rem;
            border-radius: var(--radius-xs);
            font-size: 0.78rem;
            font-family: inherit;
            transition: all 0.2s ease;
        }
        .filter-group select:hover, .filter-group input:hover { border-color: var(--border-hover); }
        .filter-group select:focus, .filter-group input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        .filter-group select option { background: var(--surface-solid); }
        .btn {
            background: linear-gradient(135deg, var(--accent), #7c3aed);
            color: white;
            border: none;
            padding: 0.5rem 1.25rem;
            border-radius: var(--radius-xs);
            cursor: pointer;
            font-size: 0.78rem;
            font-weight: 600;
            font-family: inherit;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(99,102,241,0.2);
        }
        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(99,102,241,0.3);
        }
        .btn:active { transform: translateY(0); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-sm { padding: 0.35rem 0.75rem; font-size: 0.72rem; }
        .btn-outline {
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            color: var(--text-dim);
            box-shadow: none;
        }
        .btn-outline:hover { background: rgba(255,255,255,0.08); color: var(--text); box-shadow: none; }
        .btn-group { display: flex; gap: 0.4rem; }

        /* Table */
        .table-container {
            background: var(--surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
        }
        .table-container::before {
            content: '';
            position: absolute; top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
        }
        .table-scroll { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; min-width: 1000px; }
        thead th {
            background: rgba(255,255,255,0.02);
            padding: 0.85rem 1rem;
            text-align: left;
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
            transition: color 0.2s;
        }
        thead th:hover { color: var(--text-dim); }
        thead th .sort-arrow { margin-left: 0.2rem; opacity: 0.3; font-size: 0.6rem; }
        thead th.sorted .sort-arrow { opacity: 1; color: var(--accent-light); }
        tbody tr {
            border-bottom: 1px solid rgba(255,255,255,0.03);
            transition: all 0.15s ease;
        }
        tbody tr:hover { background: rgba(255,255,255,0.03); }
        tbody tr:last-child { border-bottom: none; }
        tbody td { padding: 0.8rem 1rem; font-size: 0.82rem; white-space: nowrap; }

        /* Cell styles */
        .cell-rank {
            font-weight: 800; color: var(--text-muted); width: 44px; text-align: center;
            font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
        }
        .cell-rank.top-1 { color: #fbbf24; text-shadow: 0 0 12px rgba(251,191,36,0.3); }
        .cell-rank.top-2 { color: #94a3b8; }
        .cell-rank.top-3 { color: #b45309; }
        .cell-engine { font-weight: 600; cursor: pointer; color: var(--accent-light); }
        .cell-engine:hover { text-decoration: underline; }
        .cell-dataset { color: var(--text-dim); cursor: pointer; }
        .cell-dataset:hover { color: var(--text); text-decoration: underline; }
        .cell-metric {
            font-weight: 600; font-variant-numeric: tabular-nums;
            font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
        }
        .cell-metric.best {
            color: var(--green);
            text-shadow: 0 0 12px rgba(52,211,153,0.2);
        }
        .cell-status {
            font-size: 0.65rem; font-weight: 700; padding: 0.2rem 0.55rem;
            border-radius: 20px; text-transform: uppercase; letter-spacing: 0.04em;
        }
        .cell-status.success { background: rgba(52,211,153,0.12); color: var(--green); border: 1px solid rgba(52,211,153,0.2); }
        .cell-status.failed { background: rgba(248,113,113,0.12); color: var(--red); border: 1px solid rgba(248,113,113,0.2); }
        .cell-status.running { background: rgba(96,165,250,0.12); color: var(--blue); border: 1px solid rgba(96,165,250,0.2); }

        /* Bar chart */
        .bar-chart { display: flex; align-items: center; gap: 0.5rem; }
        .bar-chart .bar {
            height: 6px; border-radius: 3px;
            background: linear-gradient(90deg, var(--accent), var(--cyan));
            transition: width 0.5s ease;
        }
        .bar-chart .bar.green { background: linear-gradient(90deg, var(--green), var(--cyan)); }
        .bar-chart .bar.blue { background: linear-gradient(90deg, var(--blue), var(--accent)); }
        .bar-chart .bar.orange { background: linear-gradient(90deg, var(--orange), var(--yellow)); }

        /* Sparkline */
        .sparkline { width: 60px; height: 24px; }

        /* Modal */
        .modal-overlay {
            position: fixed; inset: 0;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(8px);
            display: none; align-items: center; justify-content: center; z-index: 200;
            animation: fadeIn 0.2s ease;
        }
        .modal-overlay.show { display: flex; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .modal {
            background: var(--surface-solid);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.75rem;
            max-width: 480px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.95) translateY(10px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .modal h2 {
            font-size: 1.1rem; font-weight: 700; margin-bottom: 1.25rem;
            letter-spacing: -0.01em;
        }
        .modal .form-group { margin-bottom: 1rem; }
        .modal .form-group label { display: block; margin-bottom: 0.4rem; font-size: 0.78rem; color: var(--text-dim); font-weight: 500; }
        .modal .form-group select, .modal .form-group input {
            width: 100%; background: rgba(255,255,255,0.04); border: 1px solid var(--border);
            color: var(--text); padding: 0.55rem 0.75rem; border-radius: var(--radius-xs);
            font-size: 0.85rem; font-family: inherit;
            transition: all 0.2s ease;
        }
        .modal .form-group select:focus, .modal .form-group input:focus {
            outline: none; border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        .modal .form-group select option { background: var(--surface-solid); }
        .modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1.5rem; }

        /* Toast */
        #toast {
            position: fixed; bottom: 24px; right: 24px;
            background: var(--surface-solid);
            border: 1px solid var(--border);
            backdrop-filter: blur(12px);
            color: var(--text); padding: 0.8rem 1.25rem; border-radius: var(--radius-sm);
            display: none; z-index: 300; font-size: 0.82rem; font-weight: 500;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            animation: toastIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes toastIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* Compare cards */
        .compare-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 1rem; }
        .compare-card {
            background: var(--surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.5rem; text-align: center;
            position: relative; overflow: hidden;
            transition: all 0.3s ease;
            animation: cardIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes cardIn {
            from { opacity: 0; transform: translateY(16px) scale(0.96); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .compare-card::before {
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, var(--accent), var(--cyan));
        }
        .compare-card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .compare-card h4 { font-size: 0.85rem; font-weight: 600; margin-bottom: 0.75rem; color: var(--text-dim); }
        .compare-card .metric { font-size: 2.25rem; font-weight: 800; letter-spacing: -0.03em; }
        .compare-card .label { font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
        .compare-card .sub { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.5rem; font-family: 'JetBrains Mono', monospace; }

        /* Radar chart container */
        .radar-container { width: 200px; height: 200px; margin: 1rem auto; }
        .radar-container svg { width: 100%; height: 100%; }

        /* Bar chart horizontal */
        .h-bar-chart { margin: 0.5rem 0; }
        .h-bar-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem; }
        .h-bar-label { width: 80px; font-size: 0.7rem; color: var(--text-dim); text-align: right; }
        .h-bar-track { flex: 1; height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden; }
        .h-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
        .h-bar-value { width: 50px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; color: var(--text); }

        /* Loading spinner */
        .spinner {
            width: 20px; height: 20px;
            border: 2px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: inline-block;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Confetti canvas */
        #confetti-canvas {
            position: fixed; inset: 0; pointer-events: none; z-index: 9999;
        }

        /* Empty state */
        .empty-state {
            text-align: center; padding: 4rem 2rem; color: var(--text-muted);
        }
        .empty-state .icon { font-size: 2.5rem; margin-bottom: 1rem; opacity: 0.3; }
        .empty-state p { font-size: 0.9rem; }

        /* Run page form */
        .run-form { max-width: 520px; }
        .run-form .form-group { margin-bottom: 1.25rem; }
        .run-form .form-group label { display: block; margin-bottom: 0.5rem; font-size: 0.8rem; color: var(--text-dim); font-weight: 500; }
        .run-form .form-group select, .run-form .form-group input {
            width: 100%; background: rgba(255,255,255,0.04); border: 1px solid var(--border);
            color: var(--text); padding: 0.6rem 0.85rem; border-radius: var(--radius-xs);
            font-size: 0.88rem; font-family: inherit;
            transition: all 0.2s ease;
        }
        .run-form .form-group select:focus, .run-form .form-group input:focus {
            outline: none; border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        .run-form .form-group select option { background: var(--surface-solid); }

        /* Engine detail page */
        .detail-header {
            display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem;
        }
        .detail-header h2 { font-size: 1.5rem; font-weight: 700; }
        .detail-header .back-btn {
            color: var(--text-muted); cursor: pointer; font-size: 0.85rem;
            display: flex; align-items: center; gap: 0.3rem;
            transition: color 0.2s;
        }
        .detail-header .back-btn:hover { color: var(--text); }

        /* Metric cards */
        .metric-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 1rem;
            text-align: center;
        }
        .metric-card .value { font-size: 1.5rem; font-weight: 700; }
        .metric-card .label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-top: 0.25rem; }

        /* Dataset cards */
        .dataset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
        .dataset-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.25rem;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .dataset-card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
        }
        .dataset-card h4 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; }
        .dataset-card .meta { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem; }
        .dataset-card .metrics { display: flex; gap: 1rem; }
        .dataset-card .metric-item { flex: 1; }
        .dataset-card .metric-item .val { font-size: 1rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        .dataset-card .metric-item .lbl { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; }

        /* Tabs */
        .tabs { display: flex; gap: 0.25rem; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0; }
        .tab {
            padding: 0.6rem 1rem;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text-muted);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        .tab:hover { color: var(--text-dim); }
        .tab.active { color: var(--text); border-bottom-color: var(--accent); }

        /* Checkbox for compare selection */
        .compare-checkbox {
            appearance: none;
            width: 16px;
            height: 16px;
            border: 1px solid var(--border);
            border-radius: 3px;
            background: rgba(255,255,255,0.04);
            cursor: pointer;
            position: relative;
            transition: all 0.2s;
        }
        .compare-checkbox:checked {
            background: var(--accent);
            border-color: var(--accent);
        }
        .compare-checkbox:checked::after {
            content: '✓';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 10px;
        }

        /* Compare floating bar */
        .compare-float {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: var(--surface-solid);
            border: 1px solid var(--border);
            backdrop-filter: blur(12px);
            border-radius: var(--radius);
            padding: 0.75rem 1.25rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            z-index: 150;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .compare-float.visible { transform: translateX(-50%) translateY(0); }
        .compare-float .count { font-size: 0.85rem; font-weight: 600; }
        .compare-float .selected { font-size: 0.75rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }

        /* Responsive */
        @media (max-width: 768px) {
            .container { padding: 1rem; }
            .header { padding: 0 1rem; }
            .nav { gap: 0; }
            .nav a { padding: 0.4rem 0.6rem; font-size: 0.7rem; }
            .filters-bar { flex-direction: column; align-items: stretch; }
            .filter-group { justify-content: space-between; }
        }
    </style>
</head>
<body>
    <canvas id="confetti-canvas"></canvas>

    <div class="header">
        <div class="header-brand" onclick="showPage('leaderboard')">
            <div class="logo">CP</div>
            <h1>CodeProvenance</h1>
        </div>
        <div class="nav">
            <a onclick="showPage('leaderboard')" class="active" id="nav-leaderboard">Leaderboard</a>
            <a onclick="showPage('compare')" id="nav-compare">Compare</a>
            <a onclick="showPage('run')" id="nav-run">Run</a>
            <a onclick="showPage('datasets')" id="nav-datasets">Datasets</a>
            <a onclick="showPage('reports')" id="nav-reports">Reports</a>
            <a onclick="showPage('plugins')" id="nav-plugins">Plugins</a>
        </div>
    </div>

    <div class="container">
        <!-- Leaderboard Page -->
        <div id="page-leaderboard" class="page active">
            <div class="hero-stats" id="hero-stats"></div>
            <div class="top-badges" id="top-badges"></div>
            <div class="filters-bar">
                <div class="filter-group">
                    <label>Engine</label>
                    <select id="filter-engine" onchange="renderLeaderboard()"><option value="">All</option></select>
                </div>
                <div class="filter-group">
                    <label>Dataset</label>
                    <select id="filter-dataset" onchange="renderLeaderboard()"><option value="">All</option></select>
                </div>
                <div class="filter-group">
                    <label>Sort</label>
                    <select id="filter-sort" onchange="renderLeaderboard()">
                        <option value="f1">F1 Score</option>
                        <option value="precision">Precision</option>
                        <option value="recall">Recall</option>
                        <option value="accuracy">Accuracy</option>
                        <option value="map_score">MAP</option>
                        <option value="mrr_score">MRR</option>
                        <option value="timestamp">Timestamp</option>
                    </select>
                </div>
                <button class="btn btn-outline btn-sm" onclick="loadLeaderboard()">
                    <span id="refresh-icon">↻</span>
                </button>
                <div style="margin-left:auto;display:flex;gap:0.4rem;align-items:center;">
                    <button class="btn btn-outline btn-sm" onclick="window.open('/api/export/csv','_blank')">↓ CSV</button>
                    <button class="btn btn-outline btn-sm" onclick="window.open('/api/export/markdown','_blank')">↓ MD</button>
                    <button class="btn btn-outline btn-sm" onclick="window.open('/api/export/json','_blank')">↓ JSON</button>
                    <button class="btn btn-sm" onclick="openRunModal()">
                        <span style="margin-right:0.3rem;">+</span> Run Benchmark
                    </button>
                </div>
            </div>
            <div class="table-container">
                <div class="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th style="width:40px;text-align:center;"><input type="checkbox" class="compare-checkbox" id="select-all" onchange="toggleSelectAll()"></th>
                                <th style="width:50px;text-align:center;">#</th>
                                <th onclick="sortBy('engine')">Engine <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('dataset')">Dataset <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('pairs')">Pairs <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('f1')" class="sorted">F1 Score <span class="sort-arrow">↓</span></th>
                                <th onclick="sortBy('precision')">Precision <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('recall')">Recall <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('accuracy')">Accuracy <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('map_score')">MAP <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('mrr_score')">MRR <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('threshold')">Threshold <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('timestamp')">Timestamp <span class="sort-arrow">↕</span></th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="leaderboard-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Compare Page -->
        <div id="page-compare" class="page">
            <div class="detail-header">
                <div class="back-btn" onclick="showPage('leaderboard')">← Back to Leaderboard</div>
                <h2>Engine Comparison</h2>
            </div>
            <div class="filters-bar">
                <div class="filter-group">
                    <label>Dataset</label>
                    <select id="compare-dataset"></select>
                </div>
                <div class="filter-group">
                    <label>Max Pairs</label>
                    <input type="number" id="compare-pairs" placeholder="All" style="width:100px;">
                </div>
                <button class="btn" id="compare-btn" onclick="startCompare()">Compare Selected</button>
                <span style="color:var(--text-muted);font-size:0.75rem;" id="compare-count">Select engines from the leaderboard</span>
            </div>
            <div id="compare-results"></div>
        </div>

        <!-- Engine Detail Page -->
        <div id="page-engine-detail" class="page">
            <div class="detail-header">
                <div class="back-btn" onclick="showPage('leaderboard')">← Back to Leaderboard</div>
                <h2 id="engine-detail-name"></h2>
            </div>
            <div class="metric-cards" id="engine-metric-cards"></div>
            <div class="tabs">
                <div class="tab active" onclick="showEngineTab('performance')">Performance</div>
                <div class="tab" onclick="showEngineTab('datasets')">By Dataset</div>
            </div>
            <div id="engine-tab-performance"></div>
            <div id="engine-tab-datasets" style="display:none;"></div>
        </div>

        <!-- Dataset Detail Page -->
        <div id="page-dataset-detail" class="page">
            <div class="detail-header">
                <div class="back-btn" onclick="showPage('datasets')">← Back to Datasets</div>
                <h2 id="dataset-detail-name"></h2>
            </div>
            <div id="dataset-detail-content"></div>
        </div>

        <!-- Run Page -->
        <div id="page-run" class="page">
            <div class="run-form">
                <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:1.5rem;">Run Benchmark</h2>
                <div class="form-group">
                    <label>Engine</label>
                    <select id="run-engine"></select>
                </div>
                <div class="form-group">
                    <label>Dataset</label>
                    <select id="run-dataset"></select>
                </div>
                <div class="form-group">
                    <label>Max Pairs</label>
                    <input type="number" id="run-pairs" placeholder="All">
                </div>
                <div class="form-group">
                    <label>Split</label>
                    <select id="run-split"><option value="test">test</option><option value="train">train</option></select>
                </div>
                <button class="btn" id="run-btn" onclick="startBenchmark()" style="width:100%;">Run Benchmark</button>
                <div id="run-status" style="margin-top:1.25rem;"></div>
            </div>
        </div>

        <!-- Datasets Page -->
        <div id="page-datasets" class="page">
            <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:1.5rem;">Datasets</h2>
            <div class="dataset-grid" id="dataset-grid"></div>
        </div>

        <!-- Reports Page -->
        <div id="page-reports" class="page">
            <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:1.5rem;">Reports</h2>
            <div class="table-container">
                <div class="table-scroll">
                    <table>
                        <thead><tr><th>Timestamp</th><th>File</th><th>Actions</th></tr></thead>
                        <tbody id="reports-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Plugins Page -->
        <div id="page-plugins" class="page">
            <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:1.5rem;">Plugins</h2>
            <div class="filters-bar" style="margin-bottom:1.5rem;">
                <div class="filter-group">
                    <button class="btn btn-outline btn-sm" onclick="loadPlugins()">↻ Refresh</button>
                </div>
                <p style="color:var(--text-muted);font-size:0.8rem;margin-left:0.5rem;">Drop <code style="background:var(--surface-2);padding:0.15rem 0.4rem;border-radius:4px;font-size:0.75rem;">.py</code> files in the <code style="background:var(--surface-2);padding:0.15rem 0.4rem;border-radius:4px;font-size:0.75rem;">plugins/</code> directory</p>
            </div>
            <div id="plugins-grid" class="compare-grid"></div>
        </div>
    </div>

    <!-- Run Modal -->
    <div class="modal-overlay" id="run-modal" onclick="if(event.target===this)closeRunModal()">
        <div class="modal" style="max-width:520px;">
            <h2>Run Benchmark</h2>
            <div class="form-group"><label>Engine</label><select id="modal-engine"></select></div>
            <div class="form-group"><label>Dataset</label><select id="modal-dataset"></select></div>
            <div class="form-group"><label>Max Pairs</label><input type="number" id="modal-pairs" placeholder="All"></div>
            <div class="form-group"><label>Split</label><select id="modal-split"><option value="test">test</option><option value="train">train</option></select></div>
            <div class="modal-actions">
                <button class="btn btn-outline" onclick="closeRunModal()">Cancel</button>
                <button class="btn" onclick="startBenchmarkFromModal()">Run</button>
            </div>
        </div>
    </div>

    <!-- Compare floating bar -->
    <div class="compare-float" id="compare-float">
        <span class="count" id="compare-float-count">0 selected</span>
        <span class="selected" id="compare-float-engines"></span>
        <button class="btn btn-sm" onclick="goToCompare()">Compare Now</button>
        <button class="btn btn-outline btn-sm" onclick="clearCompareSelection()">Clear</button>
    </div>

    <div id="toast"></div>

    <script>
        let currentSort = { key: 'f1', dir: 'desc' };
        let leaderboardData = [];
        let selectedEngines = new Set();
        let enginesList = [];
        let datasetsList = {};

        function showPage(page) {
            document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav a').forEach(el => el.classList.remove('active'));
            const el = document.getElementById('page-' + page);
            if (el) {
                el.classList.remove('active');
                void el.offsetWidth;
                el.classList.add('active');
            }
            const navEl = document.getElementById('nav-' + page);
            if (navEl) navEl.classList.add('active');
            if (page === 'leaderboard') loadLeaderboard();
            if (page === 'reports') loadReports();
            if (page === 'datasets') loadDatasets();
            if (page === 'plugins') loadPlugins();
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.textContent = msg; t.style.display = 'block';
            setTimeout(() => t.style.display = 'none', 3000);
        }

        function fmt(n) { return n != null ? n.toFixed(4) : '—'; }

        function sortBy(key) {
            if (currentSort.key === key) {
                currentSort.dir = currentSort.dir === 'desc' ? 'asc' : 'desc';
            } else {
                currentSort.key = key;
                currentSort.dir = 'desc';
            }
            renderLeaderboard();
        }

        function animateValue(el, start, end, duration, decimals = 0) {
            const range = end - start;
            const startTime = performance.now();
            function update(now) {
                const elapsed = now - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = start + range * eased;
                el.textContent = decimals > 0 ? current.toFixed(decimals) : Math.round(current);
                if (progress < 1) requestAnimationFrame(update);
            }
            requestAnimationFrame(update);
        }

        function sparklineSVG(values, color) {
            if (!values.length) return '';
            const w = 60, h = 24, pad = 2;
            const min = Math.min(...values), max = Math.max(...values);
            const range = max - min || 1;
            const points = values.map((v, i) => {
                const x = pad + (i / (values.length - 1 || 1)) * (w - pad * 2);
                const y = h - pad - ((v - min) / range) * (h - pad * 2);
                return `${x},${y}`;
            });
            const gradId = 'sg' + Math.random().toString(36).slice(2, 6);
            return `<svg class="sparkline" viewBox="0 0 ${w} ${h}">
                <defs><linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
                    <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
                </linearGradient></defs>
                <polygon points="${points.join(' ')} ${pad},${h-pad} ${w-pad},${h-pad}" fill="url(#${gradId})"/>
                <polyline points="${points.join(' ')}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>`;
        }

        function hBarChart(label, value, color, maxVal = 1) {
            const pct = Math.min(100, (value / maxVal) * 100);
            return `<div class="h-bar-row">
                <div class="h-bar-label">${label}</div>
                <div class="h-bar-track"><div class="h-bar-fill" style="width:${pct}%;background:${color};"></div></div>
                <div class="h-bar-value">${fmt(value)}</div>
            </div>`;
        }

        function radarSVG(metrics, color) {
            const keys = Object.keys(metrics);
            const n = keys.length;
            if (n === 0) return '';
            const cx = 100, cy = 100, r = 80;
            const angleStep = (2 * Math.PI) / n;
            const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0];
            
            let svg = `<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">`;
            
            // Grid
            for (const level of gridLevels) {
                let points = [];
                for (let i = 0; i < n; i++) {
                    const angle = i * angleStep - Math.PI / 2;
                    const x = cx + r * level * Math.cos(angle);
                    const y = cy + r * level * Math.sin(angle);
                    points.push(`${x},${y}`);
                }
                svg += `<polygon points="${points.join(' ')}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;
            }
            
            // Axes
            for (let i = 0; i < n; i++) {
                const angle = i * angleStep - Math.PI / 2;
                const x = cx + r * Math.cos(angle);
                const y = cy + r * Math.sin(angle);
                svg += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;
            }
            
            // Data
            let dataPoints = [];
            for (let i = 0; i < n; i++) {
                const angle = i * angleStep - Math.PI / 2;
                const val = Math.min(1, Math.max(0, metrics[keys[i]] || 0));
                const x = cx + r * val * Math.cos(angle);
                const y = cy + r * val * Math.sin(angle);
                dataPoints.push(`${x},${y}`);
            }
            svg += `<polygon points="${dataPoints.join(' ')}" fill="${color}" fill-opacity="0.2" stroke="${color}" stroke-width="2"/>`;
            
            // Labels
            for (let i = 0; i < n; i++) {
                const angle = i * angleStep - Math.PI / 2;
                const x = cx + (r + 12) * Math.cos(angle);
                const y = cy + (r + 12) * Math.sin(angle);
                const anchor = Math.abs(Math.cos(angle)) < 0.1 ? 'middle' : (Math.cos(angle) > 0 ? 'start' : 'end');
                svg += `<text x="${x}" y="${y}" fill="rgba(255,255,255,0.5)" font-size="8" text-anchor="${anchor}" dominant-baseline="middle">${keys[i].replace('_', ' ').toUpperCase()}</text>`;
            }
            
            svg += `</svg>`;
            return svg;
        }

        function launchConfetti() {
            const canvas = document.getElementById('confetti-canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const particles = [];
            const colors = ['#6366f1', '#22d3ee', '#34d399', '#fbbf24', '#f472b6', '#fb923c', '#818cf8'];
            for (let i = 0; i < 120; i++) {
                particles.push({
                    x: canvas.width / 2 + (Math.random() - 0.5) * 200,
                    y: canvas.height / 2,
                    vx: (Math.random() - 0.5) * 12,
                    vy: -Math.random() * 14 - 4,
                    color: colors[Math.floor(Math.random() * colors.length)],
                    size: Math.random() * 6 + 3,
                    rotation: Math.random() * 360,
                    rotSpeed: (Math.random() - 0.5) * 10,
                    life: 1,
                });
            }
            function animate() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                let alive = false;
                for (const p of particles) {
                    if (p.life <= 0) continue;
                    alive = true;
                    p.x += p.vx;
                    p.y += p.vy;
                    p.vy += 0.25;
                    p.rotation += p.rotSpeed;
                    p.life -= 0.008;
                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate(p.rotation * Math.PI / 180);
                    ctx.globalAlpha = p.life;
                    ctx.fillStyle = p.color;
                    ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
                    ctx.restore();
                }
                if (alive) requestAnimationFrame(animate);
                else ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            animate();
        }

        // Compare selection
        function toggleSelectAll() {
            const checked = document.getElementById('select-all').checked;
            document.querySelectorAll('.engine-select').forEach(cb => {
                cb.checked = checked;
                const engine = cb.dataset.engine;
                if (checked) selectedEngines.add(engine);
                else selectedEngines.delete(engine);
            });
            updateCompareFloat();
        }

        function toggleEngineSelect(checkbox) {
            const engine = checkbox.dataset.engine;
            if (checkbox.checked) selectedEngines.add(engine);
            else selectedEngines.delete(engine);
            updateCompareFloat();
        }

        function updateCompareFloat() {
            const float = document.getElementById('compare-float');
            const count = document.getElementById('compare-float-count');
            const engines = document.getElementById('compare-float-engines');
            if (selectedEngines.size > 0) {
                float.classList.add('visible');
                count.textContent = `${selectedEngines.size} selected`;
                engines.textContent = [...selectedEngines].join(', ');
            } else {
                float.classList.remove('visible');
            }
            document.getElementById('compare-count').textContent = 
                selectedEngines.size > 0 ? `${selectedEngines.size} engines selected` : 'Select engines from the leaderboard';
        }

        function clearCompareSelection() {
            selectedEngines.clear();
            document.querySelectorAll('.engine-select').forEach(cb => cb.checked = false);
            document.getElementById('select-all').checked = false;
            updateCompareFloat();
        }

        function goToCompare() {
            if (selectedEngines.size < 2) {
                showToast('Select at least 2 engines to compare');
                return;
            }
            document.getElementById('compare-engines').value = [...selectedEngines].join(', ');
            showPage('compare');
        }

        function renderLeaderboard() {
            const engineFilter = document.getElementById('filter-engine').value;
            const datasetFilter = document.getElementById('filter-dataset').value;
            const sortKey = document.getElementById('filter-sort').value;

            let data = [...leaderboardData];
            if (engineFilter) data = data.filter(d => d.engine === engineFilter);
            if (datasetFilter) data = data.filter(d => d.dataset === datasetFilter);

            data.sort((a, b) => {
                let va = a.metrics?.[sortKey] ?? a[sortKey] ?? 0;
                let vb = b.metrics?.[sortKey] ?? b[sortKey] ?? 0;
                if (sortKey === 'timestamp') { va = a.timestamp || ''; vb = b.timestamp || ''; }
                if (typeof va === 'string') return currentSort.dir === 'desc' ? vb.localeCompare(va) : va.localeCompare(vb);
                return currentSort.dir === 'desc' ? vb - va : va - vb;
            });

            const bestF1 = data.length ? Math.max(...data.map(d => d.metrics?.f1 || 0)) : 0;
            const f1Values = data.map(d => d.metrics?.f1 || 0);

            const tbody = document.getElementById('leaderboard-tbody');
            if (!data.length) {
                tbody.innerHTML = `<tr><td colspan="14"><div class="empty-state">
                    <div class="icon">📊</div>
                    <p>No benchmark results yet.<br><span style="color:var(--text-muted);font-size:0.8rem;">Click "+ Run Benchmark" to get started.</span></p>
                </div></td></tr>`;
                return;
            }

            tbody.innerHTML = data.map((d, i) => {
                const m = d.metrics || {};
                const rank = i + 1;
                const rankClass = rank === 1 ? 'top-1' : rank === 2 ? 'top-2' : rank === 3 ? 'top-3' : '';
                const f1Class = m.f1 === bestF1 && bestF1 > 0 ? 'best' : '';
                const statusClass = d.success ? 'success' : 'failed';
                const statusText = d.success ? '✓' : '✗';
                const sparkline = rank <= 5 ? sparklineSVG(f1Values.slice(0, Math.min(i + 1, 5)), 'var(--green)') : '';
                const checked = selectedEngines.has(d.engine) ? 'checked' : '';
                return `<tr style="animation: cardIn 0.3s ease ${i * 0.03}s both;">
                    <td style="text-align:center;"><input type="checkbox" class="compare-checkbox engine-select" data-engine="${d.engine}" ${checked} onchange="toggleEngineSelect(this)"></td>
                    <td class="cell-rank ${rankClass}">${rank <= 3 ? ['🥇','🥈','🥉'][rank-1] : rank}</td>
                    <td class="cell-engine" onclick="showEngineDetail('${d.engine}')">${d.engine}</td>
                    <td class="cell-dataset" onclick="showDatasetDetail('${d.dataset}')">${d.dataset}</td>
                    <td style="color:var(--text-dim);font-family:'JetBrains Mono',monospace;font-size:0.78rem;">${d.pairs || '—'}</td>
                    <td class="cell-metric ${f1Class}">${fmt(m.f1)}</td>
                    <td class="cell-metric">${fmt(m.precision)}</td>
                    <td class="cell-metric">${fmt(m.recall)}</td>
                    <td class="cell-metric">${fmt(m.accuracy)}</td>
                    <td class="cell-metric">${fmt(m.map_score)}</td>
                    <td class="cell-metric">${fmt(m.mrr_score)}</td>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:var(--text-dim);">${fmt(m.threshold)}</td>
                    <td style="color:var(--text-muted);font-size:0.75rem;">${d.timestamp ? d.timestamp.slice(0, 19).replace('T', ' ') : '—'}</td>
                    <td><span class="cell-status ${statusClass}">${statusText}</span></td>
                </tr>`;
            }).join('');
        }

        async function loadLeaderboard() {
            const icon = document.getElementById('refresh-icon');
            icon.style.animation = 'spin 0.8s linear';
            setTimeout(() => icon.style.animation = '', 800);

            const [lbRes, engRes, dsRes, histRes] = await Promise.all([
                fetch('/api/leaderboard'), fetch('/api/engines'), fetch('/api/datasets'), fetch('/api/benchmark/history')
            ]);
            const lb = await lbRes.json();
            const engines = await engRes.json();
            const datasets = await dsRes.json();
            const history = await histRes.json();

            enginesList = engines.engines.map(e => e.name);
            datasetsList = datasets.datasets;

            const entries = (lb.entries || []).map(e => ({
                engine: e.engine, dataset: e.dataset, pairs: null,
                metrics: { precision: e.precision, recall: e.recall, f1: e.f1, accuracy: e.accuracy, map_score: e.map_score || 0, mrr_score: e.mrr_score || 0, threshold: e.threshold },
                timestamp: e.timestamp, success: true,
            }));
            const histEntries = (history.results || []).map(r => ({
                engine: r.engine, dataset: r.dataset, pairs: r.pairs,
                metrics: r.metrics, timestamp: r.timestamp || new Date().toISOString(),
                success: r.success,
            }));
            leaderboardData = [...entries, ...histEntries];

            const totalRuns = leaderboardData.length;
            const bestF1 = leaderboardData.length ? Math.max(...leaderboardData.map(d => d.metrics?.f1 || 0)) : 0;
            const bestEntry = leaderboardData.find(d => d.metrics?.f1 === bestF1);

            document.getElementById('hero-stats').innerHTML = `
                <div class="hero-stat" onclick="showPage('run')"><div class="label">Total Runs</div><div class="value" id="hv-runs">0</div><div class="sub">benchmarks executed</div></div>
                <div class="hero-stat" onclick="showEngineDetail('${bestEntry?.engine || ''}')"><div class="label">Best F1 Score</div><div class="value green" id="hv-f1">—</div><div class="sub" id="hv-f1-sub"></div></div>
                <div class="hero-stat" onclick="showPage('plugins')"><div class="label">Engines</div><div class="value accent">${engines.engines.length}</div><div class="sub">registered</div></div>
                <div class="hero-stat" onclick="showPage('datasets')"><div class="label">Datasets</div><div class="value">${Object.keys(datasets.datasets).length}</div><div class="sub">available</div></div>
            `;
            const runsEl = document.getElementById('hv-runs');
            if (runsEl) animateValue(runsEl, 0, totalRuns, 800);
            const f1El = document.getElementById('hv-f1');
            if (f1El && bestF1 > 0) { f1El.textContent = bestF1.toFixed(4); }
            const subEl = document.getElementById('hv-f1-sub');
            if (subEl) { subEl.textContent = bestEntry ? bestEntry.engine + ' on ' + bestEntry.dataset : ''; }

            const byMetric = (key) => {
                const sorted = [...leaderboardData].filter(d => d.metrics?.[key]).sort((a, b) => b.metrics[key] - a.metrics[key]);
                return sorted.slice(0, 3).map((d, i) => `<span class="engine-tag ${i===0?'first':''}" onclick="showEngineDetail('${d.engine}')">${d.engine} (${d.metrics[key].toFixed(4)})</span>`).join('');
            };
            document.getElementById('top-badges').innerHTML = `
                <div class="top-badge"><div class="cat"><span class="dot f1"></span>Highest F1</div><div class="engines">${byMetric('f1')}</div></div>
                <div class="top-badge"><div class="cat"><span class="dot prec"></span>Highest Precision</div><div class="engines">${byMetric('precision')}</div></div>
                <div class="top-badge"><div class="cat"><span class="dot rec"></span>Highest Recall</div><div class="engines">${byMetric('recall')}</div></div>
            `;

            const allEngines = [...new Set(leaderboardData.map(d => d.engine))].sort();
            const allDatasets = [...new Set(leaderboardData.map(d => d.dataset))].sort();
            document.getElementById('filter-engine').innerHTML = '<option value="">All</option>' + allEngines.map(e => `<option value="${e}">${e}</option>`).join('');
            document.getElementById('filter-dataset').innerHTML = '<option value="">All</option>' + allDatasets.map(d => `<option value="${d}">${d}</option>`).join('');

            document.getElementById('run-engine').innerHTML = engines.engines.map(e => `<option value="${e.name}">${e.name}</option>`).join('');
            document.getElementById('modal-engine').innerHTML = engines.engines.map(e => `<option value="${e.name}">${e.name}</option>`).join('');
            const dsOpts = Object.keys(datasets.datasets).map(d => `<option value="${d}">${d} (${datasets.datasets[d].language})</option>`).join('');
            document.getElementById('run-dataset').innerHTML = dsOpts;
            document.getElementById('modal-dataset').innerHTML = dsOpts;
            document.getElementById('compare-dataset').innerHTML = dsOpts;

            renderLeaderboard();
        }

        async function loadReports() {
            const res = await fetch('/api/reports');
            const data = await res.json();
            const tbody = document.getElementById('reports-tbody');
            if (!data.reports.length) {
                tbody.innerHTML = `<tr><td colspan="3"><div class="empty-state"><div class="icon">📄</div><p>No reports generated yet</p></div></td></tr>`;
            } else {
                tbody.innerHTML = data.reports.map((r, i) => `<tr style="animation: cardIn 0.3s ease ${i*0.05}s both;">
                    <td style="color:var(--text-muted);font-size:0.8rem;font-family:'JetBrains Mono',monospace;">${r.timestamp}</td>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;">${r.file}</td>
                    <td><a href="/reports/${r.file}" target="_blank" style="color:var(--accent-light);text-decoration:none;font-size:0.8rem;font-weight:500;">View →</a></td>
                </tr>`).join('');
            }
        }

        async function loadDatasets() {
            const res = await fetch('/api/datasets');
            const data = await res.json();
            const grid = document.getElementById('dataset-grid');
            const lb = await (await fetch('/api/leaderboard')).json();
            const entries = lb.entries || [];
            
            let html = '';
            for (const [name, info] of Object.entries(data.datasets)) {
                const datasetEntries = entries.filter(e => e.dataset === name);
                const bestF1 = datasetEntries.length ? Math.max(...datasetEntries.map(e => e.f1 || 0)) : 0;
                const bestEngine = datasetEntries.find(e => e.f1 === bestF1)?.engine || '—';
                const avgF1 = datasetEntries.length ? datasetEntries.reduce((s, e) => s + (e.f1 || 0), 0) / datasetEntries.length : 0;
                
                html += `<div class="dataset-card" onclick="showDatasetDetail('${name}')">
                    <h4>${name}</h4>
                    <div class="meta">${info.language} · ${info.description}</div>
                    <div class="metrics">
                        <div class="metric-item"><div class="val" style="color:var(--green);">${bestF1 > 0 ? bestF1.toFixed(4) : '—'}</div><div class="lbl">Best F1</div></div>
                        <div class="metric-item"><div class="val" style="color:var(--blue);">${avgF1 > 0 ? avgF1.toFixed(4) : '—'}</div><div class="lbl">Avg F1</div></div>
                        <div class="metric-item"><div class="val" style="color:var(--text-dim);">${datasetEntries.length}</div><div class="lbl">Runs</div></div>
                    </div>
                </div>`;
            }
            grid.innerHTML = html || '<div class="empty-state"><div class="icon">📁</div><p>No datasets available</p></div>';
        }

        async function loadPlugins() {
            const res = await fetch('/api/plugins');
            const data = await res.json();
            const grid = document.getElementById('plugins-grid');

            const v4 = [...data.plugin_engines, ...data.builtin_engines].find(e => e.name === 'codeprovenance_v4');

            if (!v4) {
                grid.innerHTML = '<div class="empty-state"><div class="icon">🔌</div><p>CodeProvenance v4 not found</p></div>';
                return;
            }

            grid.innerHTML = `<div class="compare-card" style="border-color:rgba(52,211,153,0.3);">
                <div style="position:absolute;top:12px;right:12px;background:rgba(52,211,153,0.15);color:var(--green);font-size:0.6rem;font-weight:700;padding:0.2rem 0.5rem;border-radius:12px;text-transform:uppercase;letter-spacing:0.05em;">Latest</div>
                <h4 style="color:var(--green);cursor:pointer;font-size:1.1rem;" onclick="showEngineDetail('${v4.name}')">${v4.name}</h4>
                <div class="label" style="margin-top:0.75rem;">${v4.description || 'CodeProvenance v4 — PRL v3 / Multi-Judge System'}</div>
                <div class="sub" style="margin-top:0.75rem;">Class: ${v4.class}</div>
                <div style="margin-top:1.25rem;display:flex;gap:0.5rem;justify-content:center;flex-wrap:wrap;">
                    <button class="btn btn-sm" onclick="document.getElementById('modal-engine').value='${v4.name}';openRunModal()">Run Benchmark</button>
                    <button class="btn btn-outline btn-sm" onclick="showEngineDetail('${v4.name}')">View Details</button>
                </div>
            </div>`;
        }

        async function showEngineDetail(name) {
            showPage('engine-detail');
            document.getElementById('engine-detail-name').textContent = name;
            
            try {
                const res = await fetch(`/api/engine/${name}`);
                const data = await res.json();
                
                if (data.error) {
                    document.getElementById('engine-metric-cards').innerHTML = `<div class="empty-state"><p>No data available for ${name}</p></div>`;
                    return;
                }
                
                const avg = data.average_metrics || {};
                document.getElementById('engine-metric-cards').innerHTML = `
                    <div class="metric-card"><div class="value" style="color:var(--green);">${fmt(avg.f1)}</div><div class="label">Avg F1</div></div>
                    <div class="metric-card"><div class="value" style="color:var(--blue);">${fmt(avg.precision)}</div><div class="label">Avg Precision</div></div>
                    <div class="metric-card"><div class="value" style="color:var(--orange);">${fmt(avg.recall)}</div><div class="label">Avg Recall</div></div>
                    <div class="metric-card"><div class="value" style="color:var(--cyan);">${fmt(avg.accuracy)}</div><div class="label">Avg Accuracy</div></div>
                    <div class="metric-card"><div class="value" style="color:var(--accent-light);">${data.total_runs}</div><div class="label">Total Runs</div></div>
                `;
                
                // Performance tab - radar chart
                const radar = radarSVG(avg, 'rgba(99,102,241,0.6)');
                let perfHtml = `<div style="display:flex;gap:2rem;align-items:center;flex-wrap:wrap;">
                    <div class="radar-container">${radar}</div>
                    <div style="flex:1;min-width:250px;">`;
                perfHtml += hBarChart('F1', avg.f1 || 0, 'var(--green)');
                perfHtml += hBarChart('Precision', avg.precision || 0, 'var(--blue)');
                perfHtml += hBarChart('Recall', avg.recall || 0, 'var(--orange)');
                perfHtml += hBarChart('Accuracy', avg.accuracy || 0, 'var(--cyan)');
                perfHtml += hBarChart('MAP', avg.map_score || 0, 'var(--accent-light)');
                perfHtml += hBarChart('MRR', avg.mrr_score || 0, 'var(--pink)');
                perfHtml += `</div></div>`;
                document.getElementById('engine-tab-performance').innerHTML = perfHtml;
                
                // Datasets tab
                let dsHtml = '<div class="dataset-grid">';
                for (const [ds, metrics] of Object.entries(data.datasets || {})) {
                    dsHtml += `<div class="dataset-card" onclick="showDatasetDetail('${ds}')">
                        <h4>${ds}</h4>
                        <div class="metrics">
                            <div class="metric-item"><div class="val" style="color:var(--green);">${fmt(metrics.f1)}</div><div class="lbl">F1</div></div>
                            <div class="metric-item"><div class="val" style="color:var(--blue);">${fmt(metrics.precision)}</div><div class="lbl">Precision</div></div>
                            <div class="metric-item"><div class="val" style="color:var(--orange);">${fmt(metrics.recall)}</div><div class="lbl">Recall</div></div>
                        </div>
                    </div>`;
                }
                dsHtml += '</div>';
                document.getElementById('engine-tab-datasets').innerHTML = dsHtml;
                
            } catch (e) {
                document.getElementById('engine-metric-cards').innerHTML = `<div class="empty-state"><p>Error loading engine details</p></div>`;
            }
        }

        function showEngineTab(tab) {
            document.querySelectorAll('#page-engine-detail .tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('engine-tab-performance').style.display = tab === 'performance' ? 'block' : 'none';
            document.getElementById('engine-tab-datasets').style.display = tab === 'datasets' ? 'block' : 'none';
        }

        async function showDatasetDetail(name) {
            showPage('dataset-detail');
            document.getElementById('dataset-detail-name').textContent = name;
            
            try {
                const res = await fetch(`/api/dataset/${name}`);
                const data = await res.json();
                
                if (data.error) {
                    document.getElementById('dataset-detail-content').innerHTML = `<div class="empty-state"><p>No data available for ${name}</p></div>`;
                    return;
                }
                
                const dsInfo = datasetsList[name] || { language: 'Unknown', description: '' };
                
                let html = `<div style="margin-bottom:1.5rem;">
                    <p style="color:var(--text-dim);font-size:0.85rem;">${dsInfo.language} · ${dsInfo.description}</p>
                    <p style="color:var(--text-muted);font-size:0.75rem;margin-top:0.25rem;">${data.total_runs} benchmark runs</p>
                </div>`;
                
                html += '<div class="compare-grid">';
                const colors = ['var(--green)', 'var(--blue)', 'var(--orange)', 'var(--cyan)', 'var(--pink)', 'var(--accent-light)'];
                let idx = 0;
                for (const [engine, metrics] of Object.entries(data.engines || {})) {
                    const c = colors[idx % colors.length];
                    html += `<div class="compare-card" style="animation-delay:${idx*0.1}s">
                        <h4 style="cursor:pointer;color:${c};" onclick="showEngineDetail('${engine}')">${engine}</h4>
                        <div class="metric" style="color:${c};">${fmt(metrics.f1)}</div>
                        <div class="label">F1 Score</div>
                        <div class="sub">P: ${fmt(metrics.precision)} · R: ${fmt(metrics.recall)}</div>
                        <div class="sub">A: ${fmt(metrics.accuracy)} · MAP: ${fmt(metrics.map_score)}</div>
                    </div>`;
                    idx++;
                }
                html += '</div>';
                
                document.getElementById('dataset-detail-content').innerHTML = html;
            } catch (e) {
                document.getElementById('dataset-detail-content').innerHTML = `<div class="empty-state"><p>Error loading dataset details</p></div>`;
            }
        }

        function openRunModal() { document.getElementById('run-modal').classList.add('show'); }
        function closeRunModal() { document.getElementById('run-modal').classList.remove('show'); }

        async function startBenchmark() {
            const btn = document.getElementById('run-btn');
            btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:1.5px;margin-right:0.4rem;vertical-align:middle;"></span> Running...';
            const status = document.getElementById('run-status');
            status.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem;"><span class="spinner" style="width:12px;height:12px;border-width:1.5px;margin-right:0.4rem;vertical-align:middle;"></span> Benchmark running in background...</p>';
            await _doRun(
                document.getElementById('run-engine').value,
                document.getElementById('run-dataset').value,
                document.getElementById('run-pairs').value || null,
                document.getElementById('run-split').value,
                btn, status, true
            );
        }

        async function startBenchmarkFromModal() {
            closeRunModal();
            showPage('run');
            const btn = document.getElementById('run-btn');
            btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:1.5px;margin-right:0.4rem;vertical-align:middle;"></span> Running...';
            const status = document.getElementById('run-status');
            status.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem;"><span class="spinner" style="width:12px;height:12px;border-width:1.5px;margin-right:0.4rem;vertical-align:middle;"></span> Benchmark running in background...</p>';
            await _doRun(
                document.getElementById('modal-engine').value,
                document.getElementById('modal-dataset').value,
                document.getElementById('modal-pairs').value || null,
                document.getElementById('modal-split').value, btn, status, true
            );
        }

        async function _doRun(engine, dataset, pairs, split, btn, status, poll) {
            try {
                const res = await fetch('/api/benchmark/run', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ engine, dataset, pairs, split }),
                });
                const data = await res.json();
                const taskId = data.task_id;
                if (!poll) return;
                const pollInterval = setInterval(async () => {
                    const sRes = await fetch(`/api/benchmark/status/${taskId}`);
                    const sData = await sRes.json();
                    if (sData.status === 'completed') {
                        clearInterval(pollInterval);
                        btn.disabled = false; btn.textContent = 'Run Benchmark';
                        if (sData.result.success) {
                            const m = sData.result.metrics;
                            status.innerHTML = `
                                <div class="compare-grid">
                                    <div class="compare-card" style="animation-delay:0s"><h4>F1 Score</h4><div class="metric" style="color:var(--green);">${m.f1.toFixed(4)}</div><div class="label">F1</div></div>
                                    <div class="compare-card" style="animation-delay:0.1s"><h4>Precision</h4><div class="metric" style="color:var(--blue);">${m.precision.toFixed(4)}</div><div class="label">Precision</div></div>
                                    <div class="compare-card" style="animation-delay:0.2s"><h4>Recall</h4><div class="metric" style="color:var(--orange);">${m.recall.toFixed(4)}</div><div class="label">Recall</div></div>
                                    <div class="compare-card" style="animation-delay:0.3s"><h4>Accuracy</h4><div class="metric" style="color:var(--cyan);">${m.accuracy.toFixed(4)}</div><div class="label">Accuracy</div></div>
                                </div>
                                <p style="margin-top:1rem;font-size:0.78rem;color:var(--text-muted);font-family:'JetBrains Mono',monospace;">TP: ${m.tp} · FP: ${m.fp} · TN: ${m.tn} · FN: ${m.fn} · τ: ${m.threshold.toFixed(4)}</p>`;
                            showToast('✓ Benchmark completed!');
                            launchConfetti();
                            loadLeaderboard();
                        } else {
                            status.innerHTML = `<p style="color:var(--red);">✗ Failed: ${sData.result.error}</p>`;
                            showToast('Benchmark failed');
                        }
                    } else if (sData.status === 'failed') {
                        clearInterval(pollInterval);
                        btn.disabled = false; btn.textContent = 'Run Benchmark';
                        status.innerHTML = `<p style="color:var(--red);">✗ Error: ${sData.error}</p>`;
                        showToast('Benchmark failed');
                    }
                }, 2000);
            } catch (e) {
                btn.disabled = false; btn.textContent = 'Run Benchmark';
                status.innerHTML = `<p style="color:var(--red);">✗ Error: ${e.message}</p>`;
            }
        }

        async function startCompare() {
            const btn = document.getElementById('compare-btn');
            btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:1.5px;margin-right:0.4rem;vertical-align:middle;"></span> Comparing...';
            const results = document.getElementById('compare-results');
            results.innerHTML = '<p style="color:var(--text-dim);text-align:center;padding:2rem;"><span class="spinner" style="width:16px;height:16px;border-width:2px;margin-right:0.5rem;vertical-align:middle;"></span> Running comparison...</p>';

            const body = {
                engines: document.getElementById('compare-engines')?.value?.split(',').map(s => s.trim()) || [...selectedEngines],
                dataset: document.getElementById('compare-dataset').value,
                pairs: document.getElementById('compare-pairs').value || null,
            };

            try {
                const res = await fetch('/api/compare', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body),
                });
                const data = await res.json();
                btn.disabled = false; btn.textContent = 'Compare Selected';

                if (data.results) {
                    const colors = ['var(--green)', 'var(--blue)', 'var(--orange)', 'var(--cyan)', 'var(--pink)', 'var(--accent-light)'];
                    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem;margin-top:1.5rem;">';
                    let idx = 0;
                    for (const [engine, r] of Object.entries(data.results)) {
                        if (r.success && r.metrics) {
                            const m = r.metrics;
                            const c = colors[idx % colors.length];
                            const radar = radarSVG({f1: m.f1, precision: m.precision, recall: m.recall, accuracy: m.accuracy, map: m.map_score, mrr: m.mrr_score}, c);
                            html += `<div class="compare-card" style="animation-delay:${idx*0.1}s;padding:2rem;">
                                <h4 style="color:${c};font-size:1rem;">${engine}</h4>
                                <div class="radar-container" style="width:180px;height:180px;">${radar}</div>
                                <div style="margin-top:1rem;">${hBarChart('F1', m.f1, 'var(--green)')}${hBarChart('Precision', m.precision, 'var(--blue)')}${hBarChart('Recall', m.recall, 'var(--orange)')}${hBarChart('Accuracy', m.accuracy, 'var(--cyan)')}</div>
                                <div class="sub" style="margin-top:0.75rem;">τ: ${m.threshold.toFixed(4)} · TP: ${m.tp} · FP: ${m.fp} · TN: ${m.tn} · FN: ${m.fn}</div>
                            </div>`;
                        } else {
                            html += `<div class="compare-card" style="animation-delay:${idx*0.1}s;border-color:rgba(248,113,113,0.3);">
                                <h4>${engine}</h4>
                                <div class="metric" style="color:var(--red);">Failed</div>
                                <div class="sub">${r.error}</div>
                            </div>`;
                        }
                        idx++;
                    }
                    html += '</div>';
                    results.innerHTML = html;
                }
            } catch (e) {
                btn.disabled = false; btn.textContent = 'Compare Selected';
                results.innerHTML = `<p style="color:var(--red);">Error: ${e.message}</p>`;
            }
        }

        // Auto-refresh leaderboard every 10s
        setInterval(() => {
            if (document.getElementById('page-leaderboard').classList.contains('active')) {
                loadLeaderboard();
            }
        }, 10000);

        // Initialize
        loadLeaderboard();
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"Starting dashboard at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
