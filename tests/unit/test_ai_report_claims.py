"""Guard the factual claims printed in the AI originality report.

Every number in the report must trace to a reproducible artifact:
the fingerprint library in ``ai_detection.py`` and the measured
false-positive baseline in ``docs/HUMAN_FP_BASELINE.md`` /
``human_fp_baseline.json``.
"""

import json
from pathlib import Path

from src.backend.engines.similarity.ai_detection import _ALL_LLM_PATTERNS
from src.backend.infrastructure.ai_report_generator import (
    build_ai_originality_report_html,
)

_BASELINE_PATH = Path("src/backend/engines/ai/human_fp_baseline.json")


def _job() -> dict:
    """Build a minimal ai_detector job dict for report rendering."""
    return {
        "id": "job-1",
        "assignment_name": "HW1",
        "course_name": "CS101",
        "ai_detection": {
            "total_files": 1,
            "flagged_count": 1,
            "highest_score": 0.86,
            "average_score": 0.61,
            "submissions": [],
        },
    }


class TestFingerprintCountClaim:
    """The methodology card's pattern count matches the engine's library."""

    def test_pattern_count_matches_engine(self) -> None:
        """Report claims exactly as many fingerprints as the engine has."""
        html = build_ai_originality_report_html(_job())
        assert len(_ALL_LLM_PATTERNS) == 19
        assert f"{len(_ALL_LLM_PATTERNS)} curated regex fingerprints" in html

    def test_stale_40_plus_claim_removed(self) -> None:
        """The pre-recalibration '40+ patterns' claim must not resurface."""
        html = build_ai_originality_report_html(_job())
        assert "40+ regex patterns" not in html


class TestConfidentEvidenceBlocks:
    """The report carries measured FP evidence and the code-native scope note."""

    def test_measured_fp_evidence_present(self) -> None:
        """The post-recalibration human-FP numbers are stated in the report."""
        html = build_ai_originality_report_html(_job())
        assert "Measured, not asserted" in html
        assert "2.3%" in html
        assert "9.8%" in html
        assert "174" in html

    def test_turnitin_scope_note_present(self) -> None:
        """The report states why a code-native detector beats a prose one."""
        html = build_ai_originality_report_html(_job())
        assert "Built for source code" in html
        assert "may not be accurately analyzed" in html

    def test_decision_support_discipline_intact(self) -> None:
        """New confidence copy never weakens the decision-support framing."""
        html = build_ai_originality_report_html(_job())
        assert "not proof of misconduct" in html
        assert "standalone misconduct findings" in html


class TestBaselineArtifactMatchesDoc:
    """human_fp_baseline.json serves the post-recalibration numbers."""

    def test_recalibrated_flag_rates(self) -> None:
        """Flag rates match docs/HUMAN_FP_BASELINE.md § Recalibration."""
        data = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        student = data["corpora"]["kaggle_student_code"]
        assert data["measured_at"].startswith("2026-09-21")
        assert student["fp_at_0.70"] == 0.023
        assert student["fp_at_0.50"] == 0.034
        assert student["fp_at_0.40"] == 0.098

    def test_control_corpora_stay_clean(self) -> None:
        """Community/expert human code still flags 0% at every band."""
        data = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        for name in ("ir_plag_originals", "poolc_sample"):
            corpus = data["corpora"][name]
            assert corpus["fp_at_0.40"] == 0.0
            assert corpus["fp_at_0.70"] == 0.0
