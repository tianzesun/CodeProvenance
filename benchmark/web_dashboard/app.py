"""Web dashboard for benchmark results visualization.

Flask-based web app that reads benchmark JSON reports and displays them
with interactive charts using Chart.js.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates", static_folder="static")
REPORTS_DIR = Path(__file__).parent.parent.parent / "reports" / "json"


def load_reports() -> List[Dict[str, Any]]:
    """Load all benchmark reports from JSON files."""
    reports = []
    if not REPORTS_DIR.exists():
        return reports

    for json_file in sorted(REPORTS_DIR.glob("benchmark_*.json"), reverse=True):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            data["_filename"] = json_file.name
            data["_filepath"] = str(json_file)
            data["_timestamp_parsed"] = parse_timestamp(data.get("timestamp", ""))
            reports.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return reports


def parse_timestamp(ts: str) -> str:
    """Parse ISO timestamp for display."""
    if not ts:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts


def get_engine_names(reports: List[Dict[str, Any]]) -> List[str]:
    """Get unique engine names from reports."""
    engines = set()
    for r in reports:
        if "engine" in r:
            engines.add(r["engine"])
    # If no engine in top level, check metadata
    if not engines:
        for r in reports:
            meta = r.get("metadata", {})
            if "engine" in meta:
                engines.add(meta["engine"])
    return sorted(engines)


def get_latest_per_engine(reports: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Get latest report for each engine."""
    latest: Dict[str, Dict[str, Any]] = {}
    for r in reports:
        engine = r.get("engine", "unknown")
        if engine not in latest:
            latest[engine] = r
    return latest


@app.route("/")
def index():
    return render_template("index.html")


def extract_metrics(report: dict) -> dict:
    """Extract metrics from report, handling nested structure."""
    results = report.get("results", {})
    metadata = report.get("metadata", {})
    return {
        "filename": report.get("_filename", ""),
        "timestamp": report.get("_timestamp_parsed", ""),
        "engine": report.get("engine", metadata.get("engine", "unknown")),
        "dataset": report.get("dataset", metadata.get("dataset", "synthetic")),
        "precision": results.get("precision", 0),
        "recall": results.get("recall", 0),
        "f1": results.get("f1", 0),
        "accuracy": results.get("accuracy", 0),
        "threshold": results.get("threshold", metadata.get("threshold", 0)),
        "tp": results.get("tp", 0),
        "fp": results.get("fp", 0),
        "tn": results.get("tn", 0),
        "fn": results.get("fn", 0),
    }

@app.route("/api/reports", methods=["GET"])
def api_reports():
    reports = load_reports()
    return jsonify([extract_metrics(r) for r in reports])


@app.route("/api/comparison", methods=["GET"])
def api_comparison():
    """Get latest results comparison per engine."""
    reports = load_reports()
    latest: Dict[str, Dict[str, Any]] = {}
    for r in reports:
        meta = extract_metrics(r)
        engine = meta["engine"]
        if engine not in latest:
            latest[engine] = meta
    comparison = list(latest.values())
    comparison.sort(key=lambda x: x.get("f1", 0), reverse=True)
    return jsonify(comparison)


@app.route("/api/history/<engine>", methods=["GET"])
def api_history(engine: str):
    """Get history for a specific engine."""
    reports = load_reports()
    history = []
    for r in reports:
        meta = extract_metrics(r)
        if meta["engine"] == engine:
            history.append({
                "timestamp": meta["timestamp"],
                "precision": meta["precision"],
                "recall": meta["recall"],
                "f1": meta["f1"],
                "accuracy": meta["accuracy"],
                "threshold": meta["threshold"],
            })
    return jsonify(history)


def create_app():
    return app


if __name__ == "__main__":
    app.run(debug=True, port=8080)