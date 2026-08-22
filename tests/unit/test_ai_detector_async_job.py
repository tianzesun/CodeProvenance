"""Unit tests for the async AI-detection job and the code-LM cache."""

from src.backend.api import server
from src.backend.engines.ai.perplexity import (
    PerplexityScorer,
    _TRANSFORMER_CACHE,
    _load_cached_transformer,
)


class TestTransformerCache:
    """Loaded code LMs are cached process-wide and shared across scorers."""

    def test_cache_hit_returns_same_objects_without_reload(self) -> None:
        sentinel_tokenizer = object()
        sentinel_model = object()
        _TRANSFORMER_CACHE["cache/test-model"] = (sentinel_tokenizer, sentinel_model)
        try:
            loaded = _load_cached_transformer("cache/test-model")
            assert loaded == (sentinel_tokenizer, sentinel_model)
        finally:
            del _TRANSFORMER_CACHE["cache/test-model"]

    def test_scorers_share_the_cached_model(self) -> None:
        sentinel_tokenizer = object()
        sentinel_model = object()
        _TRANSFORMER_CACHE["cache/test-model"] = (sentinel_tokenizer, sentinel_model)
        try:
            first = PerplexityScorer(model_path="cache/test-model")
            second = PerplexityScorer(model_path="cache/test-model")
            assert first._transformer_available
            assert second._transformer_available
            assert first._huggingface is sentinel_model
            assert second._huggingface is sentinel_model
            assert first._tokenizer is sentinel_tokenizer
        finally:
            del _TRANSFORMER_CACHE["cache/test-model"]


class TestFinalizeAIDetectionJob:
    """The background finalizer drives the ai_detector job lifecycle."""

    def _seed_job(self, job_id: str) -> None:
        server._jobs[job_id] = {
            "id": job_id,
            "job_type": "ai_detector",
            "status": "processing",
            "summary": {
                "total_files": 1,
                "flagged_files": 0,
                "highest_ai_probability": 0.0,
                "average_ai_probability": 0.0,
            },
        }

    def test_completed_job_populates_summary_and_ai_detection(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(server, "_persist_job", lambda job_id: None)
        monkeypatch.setattr(
            server, "_persist_ai_detection_results", lambda job_id, summary: None
        )
        monkeypatch.setattr(
            server,
            "_build_ai_detection_summary",
            lambda submissions: {
                "flagged_count": 1,
                "highest_score": 0.9,
                "average_score": 0.6,
            },
        )
        self._seed_job("job-ok")
        try:
            server._finalize_ai_detection_job("job-ok", {"student.py": "x = 1\n" * 30})
            job = server._jobs["job-ok"]
            assert job["status"] == "completed"
            assert job["summary"]["flagged_files"] == 1
            assert job["summary"]["highest_ai_probability"] == 0.9
            assert job["ai_detection"]["average_score"] == 0.6
        finally:
            server._jobs.pop("job-ok", None)

    def test_failure_marks_job_failed(self, monkeypatch) -> None:
        monkeypatch.setattr(server, "_persist_job", lambda job_id: None)

        def boom(submissions):
            raise RuntimeError("model exploded")

        monkeypatch.setattr(server, "_build_ai_detection_summary", boom)
        self._seed_job("job-bad")
        try:
            server._finalize_ai_detection_job("job-bad", {"student.py": "x = 1\n" * 30})
            assert server._jobs["job-bad"]["status"] == "failed"
        finally:
            server._jobs.pop("job-bad", None)
