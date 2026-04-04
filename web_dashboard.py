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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from flask import Flask, jsonify, render_template_string, request

from benchmark.pipeline import BenchmarkRunner, BenchmarkConfig
from benchmark.pipeline.config import EngineConfig, OutputConfig, ThresholdConfig
from benchmark.pipeline.external_loader import ExternalDatasetLoader
from benchmark.registry import registry

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
                "threshold": result.metrics.threshold,
            } if result.success else None,
        }
    return jsonify({"results": results, "dataset": dataset, "pairs": len(ds.pairs)})


# ---- HTML Template (Artificial Analysis style) ----

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeProvenance — Benchmark Leaderboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0a0a0f;
            --surface: #12121a;
            --surface-2: #1a1a26;
            --surface-3: #22222e;
            --border: #2a2a38;
            --text: #e4e4ed;
            --text-dim: #8888a0;
            --text-muted: #55556a;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --green: #22c55e;
            --green-dim: #16a34a;
            --red: #ef4444;
            --yellow: #eab308;
            --blue: #3b82f6;
            --orange: #f97316;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

        /* Header */
        .header {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 0 2rem;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-brand { display: flex; align-items: center; gap: 0.75rem; }
        .header-brand h1 { font-size: 1rem; font-weight: 700; letter-spacing: -0.02em; }
        .header-brand span { color: var(--accent-light); }
        .nav { display: flex; gap: 0.25rem; }
        .nav a {
            color: var(--text-dim); text-decoration: none; padding: 0.5rem 1rem;
            border-radius: 6px; font-size: 0.85rem; font-weight: 500; cursor: pointer;
            transition: all 0.15s;
        }
        .nav a:hover { color: var(--text); background: var(--surface-2); }
        .nav a.active { color: var(--text); background: var(--surface-3); }

        /* Main */
        .container { max-width: 1600px; margin: 0 auto; padding: 1.5rem 2rem; }

        /* Hero stats */
        .hero-stats {
            display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap;
        }
        .hero-stat {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem 1.25rem;
            flex: 1;
            min-width: 160px;
        }
        .hero-stat .label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
        .hero-stat .value { font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }
        .hero-stat .sub { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.15rem; }

        /* Filters bar */
        .filters-bar {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.75rem 1.25rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .filter-group { display: flex; align-items: center; gap: 0.5rem; }
        .filter-group label { font-size: 0.8rem; color: var(--text-dim); font-weight: 500; white-space: nowrap; }
        .filter-group select, .filter-group input {
            background: var(--surface-2);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 0.4rem 0.75rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-family: inherit;
        }
        .filter-group select:focus, .filter-group input:focus { outline: none; border-color: var(--accent); }
        .btn {
            background: var(--accent);
            color: white;
            border: none;
            padding: 0.5rem 1.25rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 600;
            font-family: inherit;
            transition: background 0.15s;
        }
        .btn:hover { background: var(--accent-light); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-sm { padding: 0.35rem 0.75rem; font-size: 0.75rem; }
        .btn-outline {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-dim);
        }
        .btn-outline:hover { background: var(--surface-2); color: var(--text); }

        /* Table */
        .table-container {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
        }
        .table-scroll { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; min-width: 900px; }
        thead th {
            background: var(--surface-2);
            padding: 0.75rem 1rem;
            text-align: left;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
            position: relative;
        }
        thead th:hover { color: var(--text-dim); }
        thead th .sort-arrow { margin-left: 0.25rem; opacity: 0.4; }
        thead th.sorted .sort-arrow { opacity: 1; color: var(--accent-light); }
        tbody tr { border-bottom: 1px solid var(--border); transition: background 0.1s; }
        tbody tr:hover { background: var(--surface-2); }
        tbody tr:last-child { border-bottom: none; }
        tbody td { padding: 0.75rem 1rem; font-size: 0.85rem; white-space: nowrap; }

        /* Cell styles */
        .cell-rank { font-weight: 700; color: var(--text-muted); width: 40px; text-align: center; }
        .cell-rank.top-1 { color: #fbbf24; }
        .cell-rank.top-2 { color: #94a3b8; }
        .cell-rank.top-3 { color: #b45309; }
        .cell-engine { font-weight: 600; }
        .cell-dataset { color: var(--text-dim); }
        .cell-metric { font-weight: 600; font-variant-numeric: tabular-nums; }
        .cell-metric.best { color: var(--green); }
        .cell-status { font-size: 0.7rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 4px; }
        .cell-status.success { background: rgba(34,197,94,0.15); color: var(--green); }
        .cell-status.failed { background: rgba(239,68,68,0.15); color: var(--red); }
        .cell-status.running { background: rgba(59,130,246,0.15); color: var(--blue); }
        .cell-status.queued { background: rgba(234,179,8,0.15); color: var(--yellow); }

        /* Modal */
        .modal-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6);
            display: none; align-items: center; justify-content: center; z-index: 200;
        }
        .modal-overlay.show { display: flex; }
        .modal {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        .modal h2 { font-size: 1rem; margin-bottom: 1rem; }
        .modal .form-group { margin-bottom: 1rem; }
        .modal .form-group label { display: block; margin-bottom: 0.4rem; font-size: 0.8rem; color: var(--text-dim); font-weight: 500; }
        .modal .form-group select, .modal .form-group input {
            width: 100%; background: var(--surface-2); border: 1px solid var(--border);
            color: var(--text); padding: 0.5rem 0.75rem; border-radius: 6px;
            font-size: 0.85rem; font-family: inherit;
        }
        .modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1.25rem; }

        /* Toast */
        #toast {
            position: fixed; bottom: 20px; right: 20px;
            background: var(--surface-3); border: 1px solid var(--border);
            color: var(--text); padding: 0.75rem 1.25rem; border-radius: 8px;
            display: none; z-index: 300; font-size: 0.85rem;
        }

        /* Hidden pages */
        .page { display: none; }
        .page.active { display: block; }

        /* Compare cards */
        .compare-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 1rem; }
        .compare-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
            padding: 1.25rem; text-align: center; position: relative; overflow: hidden;
        }
        .compare-card::before {
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: var(--accent);
        }
        .compare-card h4 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; }
        .compare-card .metric { font-size: 2rem; font-weight: 700; }
        .compare-card .label { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }
        .compare-card .sub { font-size: 0.75rem; color: var(--text-dim); margin-top: 0.5rem; }

        /* Leaderboard badges */
        .top-badges { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
        .top-badge {
            background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
            padding: 1rem 1.25rem; flex: 1; min-width: 200px;
        }
        .top-badge .cat { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
        .top-badge .engines { display: flex; gap: 0.5rem; margin-top: 0.5rem; flex-wrap: wrap; }
        .top-badge .engine-tag {
            background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px;
            padding: 0.3rem 0.6rem; font-size: 0.75rem; font-weight: 500;
        }
        .top-badge .engine-tag.first { border-color: var(--green); color: var(--green); }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-brand">
            <h1><span>Code</span>Provenance</h1>
        </div>
        <div class="nav">
            <a onclick="showPage('leaderboard')" class="active" id="nav-leaderboard">Leaderboard</a>
            <a onclick="showPage('compare')" id="nav-compare">Compare</a>
            <a onclick="showPage('run')" id="nav-run">Run Benchmark</a>
            <a onclick="showPage('reports')" id="nav-reports">Reports</a>
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
                    <select id="filter-engine"><option value="">All</option></select>
                </div>
                <div class="filter-group">
                    <label>Dataset</label>
                    <select id="filter-dataset"><option value="">All</option></select>
                </div>
                <div class="filter-group">
                    <label>Sort by</label>
                    <select id="filter-sort">
                        <option value="f1">F1 Score</option>
                        <option value="precision">Precision</option>
                        <option value="recall">Recall</option>
                        <option value="accuracy">Accuracy</option>
                        <option value="timestamp">Timestamp</option>
                    </select>
                </div>
                <button class="btn btn-outline btn-sm" onclick="loadLeaderboard()">Refresh</button>
                <button class="btn btn-sm" onclick="openRunModal()" style="margin-left:auto;">+ Run Benchmark</button>
            </div>
            <div class="table-container">
                <div class="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th style="width:50px;text-align:center;">#</th>
                                <th onclick="sortBy('engine')">Engine <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('dataset')">Dataset <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('pairs')">Pairs <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('f1')" class="sorted">F1 Score <span class="sort-arrow">↓</span></th>
                                <th onclick="sortBy('precision')">Precision <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('recall')">Recall <span class="sort-arrow">↕</span></th>
                                <th onclick="sortBy('accuracy')">Accuracy <span class="sort-arrow">↕</span></th>
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
            <div class="filters-bar">
                <div class="filter-group">
                    <label>Engines</label>
                    <input type="text" id="compare-engines" placeholder="hybrid,token_winnowing" style="width:300px;">
                </div>
                <div class="filter-group">
                    <label>Dataset</label>
                    <select id="compare-dataset"></select>
                </div>
                <div class="filter-group">
                    <label>Pairs</label>
                    <input type="number" id="compare-pairs" placeholder="All" style="width:80px;">
                </div>
                <button class="btn" id="compare-btn" onclick="startCompare()">Compare</button>
            </div>
            <div id="compare-results"></div>
        </div>

        <!-- Run Page -->
        <div id="page-run" class="page">
            <div class="modal" style="max-width:100%;border:none;background:transparent;padding:0;">
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
                <button class="btn" id="run-btn" onclick="startBenchmark()">Run Benchmark</button>
                <div id="run-status" style="margin-top:1rem;"></div>
            </div>
        </div>

        <!-- Reports Page -->
        <div id="page-reports" class="page">
            <div class="table-container">
                <div class="table-scroll">
                    <table>
                        <thead><tr><th>Timestamp</th><th>File</th><th>Actions</th></tr></thead>
                        <tbody id="reports-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Run Modal -->
    <div class="modal-overlay" id="run-modal">
        <div class="modal">
            <h2>Run Benchmark</h2>
            <div class="form-group"><label>Engine</label><select id="modal-engine"></select></div>
            <div class="form-group"><label>Dataset</label><select id="modal-dataset"></select></div>
            <div class="form-group"><label>Max Pairs</label><input type="number" id="modal-pairs" placeholder="All"></div>
            <div class="modal-actions">
                <button class="btn btn-outline" onclick="closeRunModal()">Cancel</button>
                <button class="btn" onclick="startBenchmarkFromModal()">Run</button>
            </div>
        </div>
    </div>

    <div id="toast"></div>

    <script>
        let currentSort = { key: 'f1', dir: 'desc' };
        let leaderboardData = [];

        function showPage(page) {
            document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav a').forEach(el => el.classList.remove('active'));
            document.getElementById('page-' + page).classList.add('active');
            document.getElementById('nav-' + page).classList.add('active');
            if (page === 'leaderboard') loadLeaderboard();
            if (page === 'reports') loadReports();
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
                currentSort.dir = key === 'timestamp' ? 'desc' : 'desc';
            }
            renderLeaderboard();
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

            // Find best values for highlighting
            const bestF1 = data.length ? Math.max(...data.map(d => d.metrics?.f1 || 0)) : 0;

            const tbody = document.getElementById('leaderboard-tbody');
            if (!data.length) {
                tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--text-muted);padding:3rem;">No benchmark results yet. Click "+ Run Benchmark" to get started.</td></tr>';
                return;
            }

            tbody.innerHTML = data.map((d, i) => {
                const m = d.metrics || {};
                const rank = i + 1;
                const rankClass = rank === 1 ? 'top-1' : rank === 2 ? 'top-2' : rank === 3 ? 'top-3' : '';
                const f1Class = m.f1 === bestF1 && bestF1 > 0 ? 'best' : '';
                const statusClass = d.success ? 'success' : 'failed';
                const statusText = d.success ? 'Success' : 'Failed';
                return `<tr>
                    <td class="cell-rank ${rankClass}">${rank}</td>
                    <td class="cell-engine">${d.engine}</td>
                    <td class="cell-dataset">${d.dataset}</td>
                    <td>${d.pairs || '—'}</td>
                    <td class="cell-metric ${f1Class}">${fmt(m.f1)}</td>
                    <td class="cell-metric">${fmt(m.precision)}</td>
                    <td class="cell-metric">${fmt(m.recall)}</td>
                    <td class="cell-metric">${fmt(m.accuracy)}</td>
                    <td>${fmt(m.threshold)}</td>
                    <td style="color:var(--text-dim);font-size:0.8rem;">${d.timestamp || '—'}</td>
                    <td><span class="cell-status ${statusClass}">${statusText}</span></td>
                </tr>`;
            }).join('');
        }

        async function loadLeaderboard() {
            const [lbRes, engRes, dsRes, histRes] = await Promise.all([
                fetch('/api/leaderboard'), fetch('/api/engines'), fetch('/api/datasets'), fetch('/api/benchmark/history')
            ]);
            const lb = await lbRes.json();
            const engines = await engRes.json();
            const datasets = await dsRes.json();
            const history = await histRes.json();

            // Merge leaderboard entries with history results
            const entries = (lb.entries || []).map(e => ({
                engine: e.engine, dataset: e.dataset, pairs: null,
                metrics: { precision: e.precision, recall: e.recall, f1: e.f1, accuracy: e.accuracy, threshold: e.threshold },
                timestamp: e.timestamp, success: true,
            }));
            const histEntries = (history.results || []).map(r => ({
                engine: r.engine, dataset: r.dataset, pairs: r.pairs,
                metrics: r.metrics, timestamp: r.timestamp || new Date().toISOString(),
                success: r.success,
            }));
            leaderboardData = [...entries, ...histEntries];

            // Hero stats
            const totalRuns = leaderboardData.length;
            const bestF1 = leaderboardData.length ? Math.max(...leaderboardData.map(d => d.metrics?.f1 || 0)) : 0;
            const bestEntry = leaderboardData.find(d => d.metrics?.f1 === bestF1);
            document.getElementById('hero-stats').innerHTML = `
                <div class="hero-stat"><div class="label">Total Runs</div><div class="value">${totalRuns}</div><div class="sub">benchmarks executed</div></div>
                <div class="hero-stat"><div class="label">Best F1 Score</div><div class="value" style="color:var(--green);">${bestF1 ? bestF1.toFixed(4) : '—'}</div><div class="sub">${bestEntry ? bestEntry.engine + ' on ' + bestEntry.dataset : ''}</div></div>
                <div class="hero-stat"><div class="label">Engines</div><div class="value">${engines.engines.length}</div><div class="sub">registered</div></div>
                <div class="hero-stat"><div class="label">Datasets</div><div class="value">${Object.keys(datasets.datasets).length}</div><div class="sub">available</div></div>
            `;

            // Top badges
            const byMetric = (key) => {
                const sorted = [...leaderboardData].filter(d => d.metrics?.[key]).sort((a, b) => b.metrics[key] - a.metrics[key]);
                return sorted.slice(0, 3);
            };
            document.getElementById('top-badges').innerHTML = `
                <div class="top-badge"><div class="cat">Highest F1</div><div class="engines">${byMetric('f1').map((d, i) => `<span class="engine-tag ${i===0?'first':''}">${d.engine} (${d.metrics.f1.toFixed(4)})</span>`).join('')}</div></div>
                <div class="top-badge"><div class="cat">Highest Precision</div><div class="engines">${byMetric('precision').map((d, i) => `<span class="engine-tag ${i===0?'first':''}">${d.engine} (${d.metrics.precision.toFixed(4)})</span>`).join('')}</div></div>
                <div class="top-badge"><div class="cat">Highest Recall</div><div class="engines">${byMetric('recall').map((d, i) => `<span class="engine-tag ${i===0?'first':''}">${d.engine} (${d.metrics.recall.toFixed(4)})</span>`).join('')}</div></div>
            `;

            // Populate filters
            const allEngines = [...new Set(leaderboardData.map(d => d.engine))].sort();
            const allDatasets = [...new Set(leaderboardData.map(d => d.dataset))].sort();
            document.getElementById('filter-engine').innerHTML = '<option value="">All</option>' + allEngines.map(e => `<option value="${e}">${e}</option>`).join('');
            document.getElementById('filter-dataset').innerHTML = '<option value="">All</option>' + allDatasets.map(d => `<option value="${d}">${d}</option>`).join('');

            // Populate dropdowns
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
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:3rem;">No reports yet</td></tr>';
            } else {
                tbody.innerHTML = data.reports.map(r => `<tr>
                    <td style="color:var(--text-dim);font-size:0.85rem;">${r.timestamp}</td>
                    <td style="font-family:monospace;font-size:0.85rem;">${r.file}</td>
                    <td><a href="/reports/${r.file}" target="_blank" style="color:var(--accent-light);text-decoration:none;font-size:0.85rem;">View JSON →</a></td>
                </tr>`).join('');
            }
        }

        function openRunModal() { document.getElementById('run-modal').classList.add('show'); }
        function closeRunModal() { document.getElementById('run-modal').classList.remove('show'); }

        async function startBenchmark() {
            const btn = document.getElementById('run-btn');
            btn.disabled = true; btn.textContent = 'Running...';
            const status = document.getElementById('run-status');
            status.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem;">Benchmark running in background...</p>';
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
            btn.disabled = true; btn.textContent = 'Running...';
            const status = document.getElementById('run-status');
            status.innerHTML = '<p style="color:var(--text-dim);font-size:0.85rem;">Benchmark running in background...</p>';
            await _doRun(
                document.getElementById('modal-engine').value,
                document.getElementById('modal-dataset').value,
                document.getElementById('modal-pairs').value || null,
                'test', btn, status, true
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
                                    <div class="compare-card"><h4>F1 Score</h4><div class="metric" style="color:var(--green);">${m.f1.toFixed(4)}</div></div>
                                    <div class="compare-card"><h4>Precision</h4><div class="metric">${m.precision.toFixed(4)}</div></div>
                                    <div class="compare-card"><h4>Recall</h4><div class="metric">${m.recall.toFixed(4)}</div></div>
                                    <div class="compare-card"><h4>Accuracy</h4><div class="metric">${m.accuracy.toFixed(4)}</div></div>
                                </div>
                                <p style="margin-top:1rem;font-size:0.8rem;color:var(--text-dim);">TP: ${m.tp} | FP: ${m.fp} | TN: ${m.tn} | FN: ${m.fn} | Threshold: ${m.threshold.toFixed(4)}</p>`;
                            showToast('Benchmark completed!');
                            loadLeaderboard();
                        } else {
                            status.innerHTML = `<p style="color:var(--red);">Failed: ${sData.result.error}</p>`;
                            showToast('Benchmark failed');
                        }
                    } else if (sData.status === 'failed') {
                        clearInterval(pollInterval);
                        btn.disabled = false; btn.textContent = 'Run Benchmark';
                        status.innerHTML = `<p style="color:var(--red);">Error: ${sData.error}</p>`;
                        showToast('Benchmark failed');
                    }
                }, 2000);
            } catch (e) {
                btn.disabled = false; btn.textContent = 'Run Benchmark';
                status.innerHTML = `<p style="color:var(--red);">Error: ${e.message}</p>`;
            }
        }

        async function startCompare() {
            const btn = document.getElementById('compare-btn');
            btn.disabled = true; btn.textContent = 'Comparing...';
            const results = document.getElementById('compare-results');
            results.innerHTML = '<p style="color:var(--text-dim);">Running comparison...</p>';

            const body = {
                engines: document.getElementById('compare-engines').value.split(',').map(s => s.trim()),
                dataset: document.getElementById('compare-dataset').value,
                pairs: document.getElementById('compare-pairs').value || null,
            };

            try {
                const res = await fetch('/api/compare', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body),
                });
                const data = await res.json();
                btn.disabled = false; btn.textContent = 'Compare';

                if (data.results) {
                    let html = '<div class="compare-grid">';
                    for (const [engine, r] of Object.entries(data.results)) {
                        if (r.success && r.metrics) {
                            const m = r.metrics;
                            html += `<div class="compare-card"><h4>${engine}</h4>
                                <div class="metric" style="color:var(--green);">${m.f1.toFixed(4)}</div><div class="label">F1 Score</div>
                                <div class="sub">P: ${m.precision.toFixed(4)} | R: ${m.recall.toFixed(4)} | Acc: ${m.accuracy.toFixed(4)}</div>
                                <div class="sub">Threshold: ${m.threshold.toFixed(4)}</div>
                            </div>`;
                        } else {
                            html += `<div class="compare-card" style="border-color:var(--red);"><h4>${engine}</h4><div class="metric" style="color:var(--red);">Failed</div><div class="sub">${r.error}</div></div>`;
                        }
                    }
                    html += '</div>';
                    results.innerHTML = html;
                }
            } catch (e) {
                btn.disabled = false; btn.textContent = 'Compare';
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
