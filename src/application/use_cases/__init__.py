"""Application Layer - Use Cases (Clean Architecture).

This is the MOST important production layer.
API and Workers call application use cases ONLY.
"""
from src.application.use_cases.detect_submission import DetectSubmission
