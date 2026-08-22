"""Unit tests for web search scoring behavior."""

from src.backend.infrastructure.indexing.web_search import WebSearchService

SUBMISSION = """import os
import sys


def main():
    if __name__ == "__main__":
        pass


def compute_weighted_average(scores, weights):
    return sum(s * w for s, w in zip(scores, weights)) / sum(weights)
"""


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


def test_code_similarity_measures_containment() -> None:
    service = WebSearchService()
    query = "def compute_weighted_average(scores, weights):\n    return total / count"
    identical = service._code_similarity(query, query)
    disjoint = service._code_similarity(
        query, "class BinaryTree:\n    def insert(self)"
    )
    partial = service._code_similarity(
        query, "def compute_weighted_average(scores, weights):\n    return ratio"
    )

    assert identical == 1.0
    assert disjoint == 0.0
    assert 0.0 < partial < 1.0


def test_extract_probe_queries_skips_boilerplate() -> None:
    service = WebSearchService()
    probes = service._extract_probe_queries(SUBMISSION)

    assert probes
    for probe in probes:
        assert "import" not in probe
        assert "__main__" not in probe
        assert "__name__" not in probe
    assert any("compute_weighted_average" in probe for probe in probes)


def test_search_github_without_token_returns_empty(monkeypatch) -> None:
    def fail_get(*args, **kwargs):
        raise AssertionError("network must not be touched without a token")

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fail_get
    )
    assert WebSearchService().search_github(SUBMISSION, "python") == []


def test_search_github_scores_content_fragments_not_metadata(monkeypatch) -> None:
    service = WebSearchService(github_token="token")

    def fake_get(url, headers=None, params=None, timeout=None):
        assert params["q"].startswith("def compute_weighted_average")
        return _MockResponse(
            {
                "items": [
                    {
                        "sha": "1",
                        "name": "stats.py",
                        "path": "src/stats.py",
                        "html_url": "https://github.com/org/repo/blob/1/src/stats.py",
                        "repository": {"full_name": "org/repo"},
                        "text_matches": [
                            {
                                "fragment": (
                                    "def compute_weighted_average(scores, weights):\n"
                                    "    return sum(s * w for s, w in zip(scores, "
                                    "weights)) / sum(weights)"
                                )
                            }
                        ],
                    },
                    {
                        "sha": "2",
                        "name": "unrelated.py",
                        "path": "unrelated.py",
                        "html_url": "https://github.com/org/repo/blob/2/unrelated.py",
                        "repository": {"full_name": "org/repo"},
                        "text_matches": [],
                    },
                ]
            }
        )

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fake_get
    )
    results = service.search_github(SUBMISSION, "python")

    assert [result["url"] for result in results] == [
        "https://github.com/org/repo/blob/1/src/stats.py"
    ]
    assert results[0]["source"] == "github"
    assert results[0]["similarity"] > 0.5


def test_search_github_network_failure_returns_empty(monkeypatch) -> None:
    service = WebSearchService(github_token="token")

    def fail_get(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fail_get
    )
    assert service.search_github(SUBMISSION, "python") == []


def test_search_stackoverflow_scores_answer_code_blocks(monkeypatch) -> None:
    service = WebSearchService()
    answer_code = (
        "def compute_weighted_average(scores, weights):\n"
        "    return sum(s * w for s, w in zip(scores, weights)) / sum(weights)"
    )

    def fake_get(url, headers=None, params=None, timeout=None):
        if "search/excerpts" in url:
            assert params["q"].startswith("def compute_weighted_average")
            return _MockResponse(
                {
                    "items": [
                        {
                            "question_id": 101,
                            "title": "Weighted average of two lists",
                            "excerpt": "how to compute weighted average",
                        }
                    ]
                }
            )
        assert "questions/101/answers" in url
        assert params["filter"] == "withbody"
        return _MockResponse(
            {
                "items": [
                    {
                        "question_id": 101,
                        "body": (
                            "<p>You can use zip:</p>"
                            f"<pre><code>{answer_code}</code></pre>"
                        ),
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fake_get
    )
    results = service.search_stackoverflow(SUBMISSION)

    assert len(results) == 1
    assert results[0]["url"] == "https://stackoverflow.com/questions/101"
    assert results[0]["name"] == "Weighted average of two lists"
    assert results[0]["similarity"] > 0.5


def test_search_stackoverflow_without_probe_returns_empty(monkeypatch) -> None:
    def fail_get(*args, **kwargs):
        raise AssertionError("no probe should mean no request")

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fail_get
    )
    assert WebSearchService().search_stackoverflow("# just a comment") == []


def test_scan_public_sources_merges_and_reports_skipped(monkeypatch) -> None:
    service = WebSearchService()  # no github token -> github skipped

    def fake_get(url, headers=None, params=None, timeout=None):
        if "stackexchange" in url and "answers" not in url:
            return _MockResponse(
                {
                    "items": [
                        {
                            "question_id": 7,
                            "title": "weighted average",
                            "excerpt": "compute weighted average python",
                        }
                    ]
                }
            )
        if "answers" in url:
            return _MockResponse(
                {
                    "items": [
                        {
                            "question_id": 7,
                            "body": (
                                "<pre><code>def compute_weighted_average(scores, "
                                "weights):\n    return weighted_total / total"
                                "</code></pre>"
                            ),
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fake_get
    )
    result = service.scan_public_sources(SUBMISSION, "python", [])

    assert result["skipped_sources"] == ["github"]
    assert "stackoverflow" in result["source_counts"]
    assert result["web_results"]
    assert result["max_web_similarity"] == result["web_results"][0]["similarity"]


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
                            "text_matches": [
                                {
                                    "fragment": (
                                        "def calculate_sum(values): "
                                        "return sum(values)"
                                    )
                                }
                            ],
                        }
                    ]
                }
            )
        if "search/excerpts" in url:
            return _MockResponse({"items": []})
        return _MockResponse({"items": []})

    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.requests.get", fake_get
    )
    result = service.perform_full_web_scan(
        "def calculate_sum(values): return sum(values)",
        "python",
    )

    assert result["web_results"][0]["source"] == "github"
    assert (
        result["web_results"][0]["similarity"]
        >= result["web_results"][-1]["similarity"]
    )
