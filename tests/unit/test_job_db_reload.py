"""A job rebuilt from the database must match what the live job showed."""

import uuid

from src.backend.api import server
from src.backend.config.database import SessionLocal
from src.backend.models.database import Job, SimilarityResult


def _seed(
    job_id: str, tenant_id: str, scores: list[float], statuses: dict[int, str]
) -> None:
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                tenant_id=tenant_id,
                name="db reload test",
                status="completed",
                threshold=0.5,
            )
        )
        db.flush()
        for index, score in enumerate(scores):
            db.add(
                SimilarityResult(
                    job_id=job_id,
                    submission_a_id=f"a{index:03d}.py",
                    submission_b_id=f"b{index:03d}.py",
                    similarity_score=score,
                    review_status=statuses.get(index),
                )
            )
        db.commit()


def _delete(job_id: str) -> None:
    with SessionLocal() as db:
        db.query(SimilarityResult).filter(SimilarityResult.job_id == job_id).delete()
        db.query(Job).filter(Job.id == job_id).delete()
        db.commit()


def test_reloaded_job_counts_the_whole_cohort_and_keeps_decisions(
    job_tenant_id,
) -> None:
    job_id = str(uuid.uuid4())
    # 210 pairs (more than the 200-row page), 205 at or above the 0.5 threshold.
    scores = [0.9] * 5 + [0.66] * 200 + [0.2] * 5
    _seed(job_id, job_tenant_id, scores, {0: "confirmed", 1: "dismissed"})
    try:
        job = server._load_job_from_db(job_id)

        assert job["summary"]["total_pairs"] == 210
        assert job["summary"]["suspicious_pairs"] == 205
        assert job["review_status"] == "confirmed"
        labels = {r["score"]: r["risk_level"] for r in job["results"]}
        assert labels[0.66] == server._risk_level(0.66) == "HIGH"
    finally:
        _delete(job_id)
