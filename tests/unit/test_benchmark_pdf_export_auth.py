"""Regression tests for benchmark PDF export authentication rules."""

from fastapi.testclient import TestClient

from src.backend.api import server


def test_benchmark_pdf_export_matches_public_benchmark_auth_policy() -> None:
    """Benchmark PDF export should be available for public benchmark runs."""
    assert server._should_require_auth("/api/benchmark") is False
    assert server._should_require_auth("/api/benchmark/export-pdf") is False


def test_benchmark_pdf_export_endpoint_does_not_require_auth() -> None:
    """Benchmark PDF export endpoint should return an export file without a session."""
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

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(("application/pdf", "text/html"))
    assert "attachment;" in response.headers["content-disposition"]
