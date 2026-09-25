"""Regression tests for benchmark PDF export authentication rules."""

from fastapi.testclient import TestClient

from src.backend.api import server


def test_benchmark_pdf_export_requires_authentication() -> None:
    """Compute-heavy benchmark endpoints must require an authenticated user."""
    assert server._should_require_auth("/api/benchmark") is True
    assert server._should_require_auth("/api/benchmark/export-pdf") is True


def test_benchmark_pdf_export_endpoint_rejects_anonymous_requests() -> None:
    """Benchmark PDF export should return 401 without a session or API key."""
    client = TestClient(server.app)

    response = client.post(
        "/api/benchmark/export-pdf",
        json={
            "datasetName": "Smoke Benchmark",
            "summary": {"tools_compared": 1, "pairs_tested": 1},
            "pair_results": [
                {
                    "label": "Pair 1",
                    "file_a": "a.py",
                    "file_b": "b.py",
                    "tool_results": [{"tool": "integritydesk", "score": 0.91}],
                }
            ],
        },
    )

    assert response.status_code == 401
