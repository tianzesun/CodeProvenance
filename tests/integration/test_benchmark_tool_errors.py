"""Integration test: PAN benchmark tool errors with ground truth.

Lives in the integration suite because ``POST /api/benchmark`` persists
benchmark job state to the database; without one it fails on connection,
which is what broke the CI unit job until this move.
"""

import json

from fastapi.testclient import TestClient

from src.backend.api import server


def test_pan_benchmark_reports_tool_errors_with_ground_truth(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "synthetic"
    dataset_dir.mkdir()
    (dataset_dir / "generated_pairs.jsonl").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "case_001",
                        "code_a": "def add(a, b):\n    return a + b\n",
                        "code_b": "def sum_numbers(x, y):\n    return x + y\n",
                        "label": 1,
                        "clone_type": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from src.backend.benchmark.runners.external_tool_runner import ExternalToolRunner

    def failing_tool(self, tool, submissions, pairs, progress_cb=None):
        raise RuntimeError(f"{tool} failed before scoring")

    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)
    monkeypatch.setattr(ExternalToolRunner, "run_tool", failing_tool)

    client = TestClient(server.app)
    response = client.post(
        "/api/benchmark",
        data={
            "benchmark_type": "pan_optimization",
            "dataset": "synthetic",
            "tools": ["moss"],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["has_ground_truth"] is True
    assert payload["tool_scores"]["moss"]["pairs"] == 0
    assert payload["tool_scores"]["moss"]["error"] == "moss failed before scoring"
    assert "evaluation" not in payload
