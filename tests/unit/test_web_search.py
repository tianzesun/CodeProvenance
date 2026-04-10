"""Unit tests for web search scoring behavior."""

from src.infrastructure.indexing.web_search import WebSearchService


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_score_match_uses_overlap_not_placeholder() -> None:
    service = WebSearchService()
    strong = service._score_match(
        "def calculate_sum(values): return sum(values)",
        "calculate_sum values return sum helper python",
    )
    weak = service._score_match(
        "def calculate_sum(values): return sum(values)",
        "binary tree traversal graph search",
    )
    assert 0.0 <= weak <= 1.0
    assert 0.0 <= strong <= 1.0
    assert strong > weak


def test_perform_full_web_scan_sorts_by_computed_similarity(monkeypatch) -> None:
    service = WebSearchService(github_token="token")

    def fake_get(url, headers=None, params=None, timeout=None):
        if "github" in url:
            return _MockResponse(
                {
                    "items": [
                        {
                            "sha": "1",
                            "name": "sum_helper.py",
                            "path": "helpers/sum_helper.py",
                            "html_url": "https://example.com/gh/1",
                            "repository": {"full_name": "org/repo-a"},
                        }
                    ]
                }
            )
        return _MockResponse(
            {
                "items": [
                    {
                        "question_id": 2,
                        "title": "graph traversal question",
                        "excerpt": "depth first search adjacency list",
                    }
                ]
            }
        )

    monkeypatch.setattr("src.infrastructure.indexing.web_search.requests.get", fake_get)
    result = service.perform_full_web_scan(
        "def calculate_sum(values): return sum(values)",
        "python",
    )

    assert result["web_results"][0]["source"] == "github"
    assert result["web_results"][0]["similarity"] >= result["web_results"][-1]["similarity"]
