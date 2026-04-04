"""Web Dashboard for CodeProvenance Benchmark Framework.

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
        files = sorted(glob.glob(os.path.join(json_dir, "*.json")), reverse=True)
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


# ---- Routes ----

@app.route("/")
def dashboard():
    """Main dashboard page."""
    return render_template_string(DASHBOARD_TEMPLATE)


@app.route("/api/engines")
def api_engines():
    """List available engines."""
    engines = registry.list_engines()
    return jsonify({
        "engines": [
            {"name": name, "class": cls.__name__}
            for name, cls in sorted(engines.items())
        ]
    })


@app.route("/api/datasets")
def api_datasets():
    """List available datasets."""
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
    """Get leaderboard data."""
    return jsonify(_load_leaderboard())


@app.route("/api/reports")
def api_reports():
    """Get recent reports."""
    reports = _load_recent_reports()
    return jsonify({"reports": reports})


@app.route("/api/benchmark/run", methods=["POST"])
def api_run_benchmark():
    """Start a benchmark run."""
    data = request.get_json()
    engine = data.get("engine", "hybrid")
    dataset = data.get("dataset")
    pairs = data.get("pairs")
    split = data.get("split", "test")

    if not dataset:
        return jsonify({"error": "Dataset is required"}), 400

    task_id = f"task_{int(time.time() * 1000)}"
    _running_benchmarks[task_id] = {
        "task_id": task_id,
        "engine": engine,
        "dataset": dataset,
        "status": "queued",
        "started_at": datetime.now().isoformat(),
    }

    thread = threading.Thread(
        target=_run_benchmark_task,
        args=(task_id, engine, dataset, pairs, split),
    )
    thread.daemon = True
    thread.start()

    return jsonify({"task_id": task_id, "status": "queued"})


@app.route("/api/benchmark/status/<task_id>")
def api_benchmark_status(task_id):
    """Get benchmark task status."""
    if task_id not in _running_benchmarks:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(_running_benchmarks[task_id])


@app.route("/api/benchmark/history")
def api_benchmark_history():
    """Get benchmark history."""
    return jsonify({"results": _benchmark_results[-50:]})


@app.route("/api/compare", methods=["POST"])
def api_compare():
    """Compare multiple engines."""
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
            "success": result.success,
            "error": result.error,
            "metrics": {
                "precision": result.metrics.precision,
                "recall": result.metrics.recall,
                "f1": result.metrics.f1,
                "accuracy": result.metrics.accuracy,
                "threshold": result.metrics.threshold,
            } if result.success else None,
        }

    return jsonify({"results": results, "dataset": dataset, "pairs": len(ds.pairs)})


DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeProvenance Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; }
        .header { background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.4rem; font-weight: 600; }
        .nav { display: flex; gap: 1rem; }
        .nav a { color: #a0a0c0; text-decoration: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
        .nav a:hover, .nav a.active { background: #16213e; color: white; }
        .container { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }
        .card { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card h2 { font-size: 1.1rem; margin-bottom: 1rem; color: #1a1a2e; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
        .stat-card { background: white; border-radius: 8px; padding: 1.2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #4361ee; }
        .stat-card h3 { font-size: 0.85rem; color: #666; margin-bottom: 0.5rem; }
        .stat-card .value { font-size: 1.8rem; font-weight: 700; color: #1a1a2e; }
        .stat-card .sub { font-size: 0.8rem; color: #999; margin-top: 0.3rem; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; font-size: 0.85rem; color: #555; }
        td { font-size: 0.9rem; }
        .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-error { background: #f8d7da; color: #721c24; }
        .badge-running { background: #cce5ff; color: #004085; }
        .badge-queued { background: #fff3cd; color: #856404; }
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; margin-bottom: 0.4rem; font-weight: 500; font-size: 0.9rem; }
        .form-group select, .form-group input { width: 100%; padding: 0.6rem; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9rem; }
        .btn { background: #4361ee; color: white; border: none; padding: 0.7rem 1.5rem; border-radius: 4px; cursor: pointer; font-size: 0.9rem; font-weight: 500; }
        .btn:hover { background: #3a56d4; }
        .btn:disabled { background: #a0a0c0; cursor: not-allowed; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #5a6268; }
        .hidden { display: none; }
        .progress-bar { height: 4px; background: #e9ecef; border-radius: 2px; overflow: hidden; }
        .progress-bar .fill { height: 100%; background: #4361ee; transition: width 0.3s; }
        .comparison-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
        .comparison-card { background: #f8f9fa; border-radius: 8px; padding: 1rem; text-align: center; }
        .comparison-card h4 { margin-bottom: 0.5rem; color: #1a1a2e; }
        .comparison-card .metric { font-size: 1.5rem; font-weight: 700; }
        .comparison-card .label { font-size: 0.8rem; color: #666; }
        #toast { position: fixed; bottom: 20px; right: 20px; background: #333; color: white; padding: 1rem 1.5rem; border-radius: 8px; display: none; z-index: 1000; }
    </style>
</head>
<body>
    <div class="header">
        <h1>CodeProvenance</h1>
        <div class="nav">
            <a onclick="showPage('dashboard')" class="active" id="nav-dashboard">Dashboard</a>
            <a onclick="showPage('run')" id="nav-run">Run Benchmark</a>
            <a onclick="showPage('compare')" id="nav-compare">Compare</a>
            <a onclick="showPage('leaderboard')" id="nav-leaderboard">Leaderboard</a>
            <a onclick="showPage('reports')" id="nav-reports">Reports</a>
        </div>
    </div>

    <div class="container">
        <!-- Dashboard Page -->
        <div id="page-dashboard">
            <div class="grid" id="stats-grid"></div>
            <div class="card">
                <h2>Recent Benchmarks</h2>
                <table>
                    <thead><tr><th>Engine</th><th>Dataset</th><th>Pairs</th><th>F1</th><th>Precision</th><th>Recall</th><th>Status</th></tr></thead>
                    <tbody id="recent-table"></tbody>
                </table>
            </div>
            <div class="card">
                <h2>Active Tasks</h2>
                <table>
                    <thead><tr><th>Task ID</th><th>Engine</th><th>Dataset</th><th>Started</th><th>Status</th></tr></thead>
                    <tbody id="tasks-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Run Benchmark Page -->
        <div id="page-run" class="hidden">
            <div class="card" style="max-width: 600px;">
                <h2>Run Benchmark</h2>
                <div class="form-group">
                    <label>Engine</label>
                    <select id="run-engine"></select>
                </div>
                <div class="form-group">
                    <label>Dataset</label>
                    <select id="run-dataset"></select>
                </div>
                <div class="form-group">
                    <label>Max Pairs (optional)</label>
                    <input type="number" id="run-pairs" placeholder="All">
                </div>
                <div class="form-group">
                    <label>Split</label>
                    <select id="run-split"><option value="test">test</option><option value="train">train</option><option value="validation">validation</option></select>
                </div>
                <button class="btn" id="run-btn" onclick="startBenchmark()">Run Benchmark</button>
                <div id="run-status" style="margin-top: 1rem;"></div>
            </div>
        </div>

        <!-- Compare Page -->
        <div id="page-compare" class="hidden">
            <div class="card" style="max-width: 600px;">
                <h2>Compare Engines</h2>
                <div class="form-group">
                    <label>Engines (comma-separated)</label>
                    <input type="text" id="compare-engines" placeholder="hybrid,token_winnowing">
                </div>
                <div class="form-group">
                    <label>Dataset</label>
                    <select id="compare-dataset"></select>
                </div>
                <div class="form-group">
                    <label>Max Pairs (optional)</label>
                    <input type="number" id="compare-pairs" placeholder="All">
                </div>
                <button class="btn" id="compare-btn" onclick="startCompare()">Compare</button>
                <div id="compare-results" style="margin-top: 1rem;"></div>
            </div>
        </div>

        <!-- Leaderboard Page -->
        <div id="page-leaderboard" class="hidden">
            <div class="card">
                <h2>Leaderboard</h2>
                <table>
                    <thead><tr><th>Engine</th><th>Dataset</th><th>Precision</th><th>Recall</th><th>F1</th><th>Timestamp</th></tr></thead>
                    <tbody id="leaderboard-table"></tbody>
                </table>
            </div>
        </div>

        <!-- Reports Page -->
        <div id="page-reports" class="hidden">
            <div class="card">
                <h2>Recent Reports</h2>
                <table>
                    <thead><tr><th>Timestamp</th><th>File</th><th>Actions</th></tr></thead>
                    <tbody id="reports-table"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="toast"></div>

    <script>
        function showPage(page) {
            document.querySelectorAll('[id^="page-"]').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.nav a').forEach(el => el.classList.remove('active'));
            document.getElementById('page-' + page).classList.remove('hidden');
            document.getElementById('nav-' + page).classList.add('active');
            if (page === 'dashboard') loadDashboard();
            if (page === 'leaderboard') loadLeaderboard();
            if (page === 'reports') loadReports();
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.textContent = msg; t.style.display = 'block';
            setTimeout(() => t.style.display = 'none', 3000);
        }

        async function loadDashboard() {
            // Load engines and datasets for stats
            const [engRes, dsRes, histRes] = await Promise.all([
                fetch('/api/engines'), fetch('/api/datasets'), fetch('/api/benchmark/history')
            ]);
            const engines = await engRes.json();
            const datasets = await dsRes.json();
            const history = await histRes.json();

            document.getElementById('stats-grid').innerHTML = `
                <div class="stat-card"><h3>Engines</h3><div class="value">${engines.engines.length}</div><div class="sub">registered</div></div>
                <div class="stat-card"><h3>Datasets</h3><div class="value">${Object.keys(datasets.datasets).length}</div><div class="sub">available</div></div>
                <div class="stat-card"><h3>Benchmarks Run</h3><div class="value">${history.results.length}</div><div class="sub">total runs</div></div>
                <div class="stat-card" style="border-left-color: #28a745;"><h3>Best F1</h3><div class="value">${history.results.length ? Math.max(...history.results.map(r => r.metrics?.f1 || 0)).toFixed(4) : 'N/A'}</div><div class="sub">across all runs</div></div>
            `;

            const tbody = document.getElementById('recent-table');
            const recent = history.results.slice(-20).reverse();
            if (!recent.length) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#999;">No benchmarks run yet</td></tr>';
            } else {
                tbody.innerHTML = recent.map(r => `<tr>
                    <td>${r.engine}</td><td>${r.dataset}</td><td>${r.pairs}</td>
                    <td><strong>${r.metrics?.f1?.toFixed(4) || 'N/A'}</strong></td>
                    <td>${r.metrics?.precision?.toFixed(4) || 'N/A'}</td>
                    <td>${r.metrics?.recall?.toFixed(4) || 'N/A'}</td>
                    <td><span class="badge ${r.success ? 'badge-success' : 'badge-error'}">${r.success ? 'Success' : 'Failed'}</span></td>
                </tr>`).join('');
            }
        }

        async function loadLeaderboard() {
            const res = await fetch('/api/leaderboard');
            const data = await res.json();
            const tbody = document.getElementById('leaderboard-table');
            const entries = (data.entries || []).slice().reverse();
            if (!entries.length) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#999;">No entries yet</td></tr>';
            } else {
                tbody.innerHTML = entries.map(e => `<tr>
                    <td>${e.engine}</td><td>${e.dataset}</td>
                    <td>${e.precision?.toFixed(4) || 'N/A'}</td>
                    <td>${e.recall?.toFixed(4) || 'N/A'}</td>
                    <td><strong>${e.f1?.toFixed(4) || 'N/A'}</strong></td>
                    <td>${e.timestamp || 'N/A'}</td>
                </tr>`).join('');
            }
        }

        async function loadReports() {
            const res = await fetch('/api/reports');
            const data = await res.json();
            const tbody = document.getElementById('reports-table');
            if (!data.reports.length) {
                tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#999;">No reports yet</td></tr>';
            } else {
                tbody.innerHTML = data.reports.map(r => `<tr>
                    <td>${r.timestamp}</td><td>${r.file}</td>
                    <td><a href="/reports/${r.file}" target="_blank">View JSON</a></td>
                </tr>`).join('');
            }
        }

        async function populateSelects() {
            const [engRes, dsRes] = await Promise.all([fetch('/api/engines'), fetch('/api/datasets')]);
            const engines = await engRes.json();
            const datasets = await dsRes.json();

            ['run-engine', 'compare-engines'].forEach(id => {
                // For run-engine, use select; for compare, it's a text input
            });
            document.getElementById('run-engine').innerHTML = engines.engines.map(e => `<option value="${e.name}">${e.name}</option>`).join('');
            const dsOptions = Object.keys(datasets.datasets).map(d => `<option value="${d}">${d} (${datasets.datasets[d].language})</option>`).join('');
            document.getElementById('run-dataset').innerHTML = dsOptions;
            document.getElementById('compare-dataset').innerHTML = dsOptions;
        }

        async function startBenchmark() {
            const btn = document.getElementById('run-btn');
            btn.disabled = true; btn.textContent = 'Running...';
            const status = document.getElementById('run-status');
            status.innerHTML = '<div class="progress-bar"><div class="fill" style="width:100%;animation: pulse 1s infinite;"></div></div><p style="margin-top:0.5rem;font-size:0.9rem;color:#666;">Benchmark running...</p>';

            const body = {
                engine: document.getElementById('run-engine').value,
                dataset: document.getElementById('run-dataset').value,
                pairs: document.getElementById('run-pairs').value || null,
                split: document.getElementById('run-split').value,
            };

            try {
                const res = await fetch('/api/benchmark/run', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body),
                });
                const data = await res.json();
                const taskId = data.task_id;

                const poll = setInterval(async () => {
                    const sRes = await fetch(`/api/benchmark/status/${taskId}`);
                    const sData = await sRes.json();
                    if (sData.status === 'completed') {
                        clearInterval(poll);
                        btn.disabled = false; btn.textContent = 'Run Benchmark';
                        if (sData.result.success) {
                            const m = sData.result.metrics;
                            status.innerHTML = `<div class="card" style="margin-top:1rem;"><h2>Results</h2>
                                <div class="comparison-grid">
                                    <div class="comparison-card"><h4>F1 Score</h4><div class="metric">${m.f1.toFixed(4)}</div></div>
                                    <div class="comparison-card"><h4>Precision</h4><div class="metric">${m.precision.toFixed(4)}</div></div>
                                    <div class="comparison-card"><h4>Recall</h4><div class="metric">${m.recall.toFixed(4)}</div></div>
                                    <div class="comparison-card"><h4>Accuracy</h4><div class="metric">${m.accuracy.toFixed(4)}</div></div>
                                </div>
                                <p style="margin-top:1rem;font-size:0.85rem;color:#666;">TP: ${m.tp} | FP: ${m.fp} | TN: ${m.tn} | FN: ${m.fn} | Threshold: ${m.threshold.toFixed(4)}</p>
                            </div>`;
                            showToast('Benchmark completed!');
                        } else {
                            status.innerHTML = `<p style="color:#dc3545;">Failed: ${sData.result.error}</p>`;
                            showToast('Benchmark failed');
                        }
                    } else if (sData.status === 'failed') {
                        clearInterval(poll);
                        btn.disabled = false; btn.textContent = 'Run Benchmark';
                        status.innerHTML = `<p style="color:#dc3545;">Error: ${sData.error}</p>`;
                        showToast('Benchmark failed');
                    }
                }, 2000);
            } catch (e) {
                btn.disabled = false; btn.textContent = 'Run Benchmark';
                status.innerHTML = `<p style="color:#dc3545;">Error: ${e.message}</p>`;
            }
        }

        async function startCompare() {
            const btn = document.getElementById('compare-btn');
            btn.disabled = true; btn.textContent = 'Comparing...';
            const results = document.getElementById('compare-results');
            results.innerHTML = '<p style="color:#666;">Running comparison...</p>';

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
                    let html = '<div class="comparison-grid">';
                    for (const [engine, r] of Object.entries(data.results)) {
                        if (r.success && r.metrics) {
                            const m = r.metrics;
                            html += `<div class="comparison-card"><h4>${engine}</h4>
                                <div class="metric">${m.f1.toFixed(4)}</div><div class="label">F1 Score</div>
                                <div style="margin-top:0.5rem;font-size:0.8rem;color:#666;">P: ${m.precision.toFixed(4)} | R: ${m.recall.toFixed(4)}</div>
                            </div>`;
                        } else {
                            html += `<div class="comparison-card"><h4>${engine}</h4><div class="metric" style="color:#dc3545;">Failed</div><div class="label">${r.error}</div></div>`;
                        }
                    }
                    html += '</div>';
                    results.innerHTML = html;
                }
            } catch (e) {
                btn.disabled = false; btn.textContent = 'Compare';
                results.innerHTML = `<p style="color:#dc3545;">Error: ${e.message}</p>`;
            }
        }

        // Initialize
        populateSelects();
        loadDashboard();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"Starting dashboard at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
