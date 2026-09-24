"""Unit tests for real (server-reported) upload analysis progress."""

import math

from src.backend.api import server
from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
)

SUBMISSIONS = {
    "A.py": "def solve_a(x):\n    return x + 1\n",
    "B.py": "def solve_b(x):\n    return x + 2\n",
    "C.py": "def solve_c(x):\n    return x * 3\n",
    "D.py": "def solve_d(x):\n    return x - 4\n",
}


class TestCompareAllPairsProgressCallback:
    """``compare_all_pairs`` reports every finished pair when asked to."""

    def test_callback_receives_every_pair_in_order(self) -> None:
        ticks: list[tuple[int, int, str, str]] = []

        results = BatchDetectionService(threshold=0.99).compare_all_pairs(
            SUBMISSIONS,
            progress_callback=lambda done, total, a, b: ticks.append(
                (done, total, a, b)
            ),
        )

        assert len(results) == 6
        assert [tick[0] for tick in ticks] == [1, 2, 3, 4, 5, 6]
        assert {tick[1] for tick in ticks} == {6}
        assert ticks[0][2:] == ("A.py", "B.py")
        assert ticks[-1][2:] == ("C.py", "D.py")

    def test_callback_failure_does_not_abort_the_comparison(self) -> None:
        def exploding_callback(done: int, total: int, file_a: str, file_b: str) -> None:
            raise RuntimeError("progress sink unavailable")

        results = BatchDetectionService(threshold=0.99).compare_all_pairs(
            SUBMISSIONS, progress_callback=exploding_callback
        )

        assert len(results) == 6


class TestJobProgressPayload:
    """The payload polled by the upload page describes the live work item."""

    def _seed_job(self, job_id: str) -> None:
        server._jobs[job_id] = {"id": job_id, "status": "analyzing"}

    def test_pair_callback_publishes_pair_and_percentage(self, monkeypatch) -> None:
        persisted: list[str] = []
        monkeypatch.setattr(
            server, "_persist_job", lambda job_id: persisted.append(job_id)
        )
        job_id = "progress-unit-test"
        self._seed_job(job_id)
        try:
            server._pair_progress_callback(job_id)(3, 6, "alice.py", "bob.py")

            progress = server._jobs[job_id]["progress"]
            assert progress["stage"] == "comparing_submissions"
            assert progress["label"] == "Comparing submissions"
            assert progress["detail"] == "alice.py vs bob.py"
            assert progress["completed_units"] == 3
            assert progress["total_units"] == 6
            assert progress["unit"] == "pairs"
            assert progress["current_pair"] == {
                "file_a": "alice.py",
                "file_b": "bob.py",
            }
            midpoint = (
                server.COMPARISON_PERCENT_FLOOR + server.COMPARISON_PERCENT_CEILING
            ) / 2
            assert math.isclose(progress["percent"], midpoint, rel_tol=1e-3)
            assert persisted == [job_id]
        finally:
            server._jobs.pop(job_id, None)

    def test_stage_change_without_percent_keeps_previous_value(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(server, "_persist_job", lambda job_id: None)
        job_id = "progress-unit-test-stage"
        self._seed_job(job_id)
        try:
            server._set_job_progress(
                job_id, "comparing_submissions", percent=0.42, detail="A.py vs B.py"
            )
            server._set_job_progress(
                job_id, "generating_reports", detail="Writing HTML, JSON reports"
            )

            progress = server._jobs[job_id]["progress"]
            assert progress["stage"] == "generating_reports"
            assert progress["percent"] == 0.42
            assert progress["current_pair"] is None
            assert progress["completed_units"] is None
        finally:
            server._jobs.pop(job_id, None)

    def test_progress_for_unknown_job_is_ignored(self) -> None:
        server._set_job_progress("missing-job", "comparing_submissions", percent=0.5)

        assert "missing-job" not in server._jobs

    def test_stage_plan_only_lists_enabled_stages(self) -> None:
        minimal = [
            stage["stage"] for stage in server._analysis_progress_plan(False, False)
        ]
        assert minimal == [
            "reading_submissions",
            "building_pairs",
            "comparing_submissions",
            "ai_detection",
            "generating_reports",
        ]

        full = [stage["stage"] for stage in server._analysis_progress_plan(True, True)]
        assert full == [
            "reading_submissions",
            "building_pairs",
            "external_tools",
            "comparing_submissions",
            "ai_detection",
            "external_scan",
            "generating_reports",
        ]
