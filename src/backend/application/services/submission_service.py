"""Submission Service - API entry orchestration."""

from src.backend.application.services.detection_service import (
    SubmissionService as DetSvc,
)


class SubmissionService:
    """Orchestrates submission processing end-to-end."""

    def __init__(self, weights=None, threshold=0.5):
        self.detection = DetSvc(weights, threshold)

    def process(self, submissions: dict[str, dict[str, str]]) -> list[dict]:
        return self.detection.detect(submissions)
