"""Unit tests for the Turnitin-style AI score bands in the report generator."""

from src.backend.infrastructure.ai_report_generator import (
    _band_interpretation_table,
    _score_band,
    build_ai_originality_report_html,
)


def _job(highest: float, average: float = 0.0) -> dict:
    """Build a minimal ai_detector job dict for report rendering."""
    return {
        "id": "job-1",
        "assignment_name": "HW1",
        "course_name": "CS101",
        "ai_detection": {
            "total_files": 1,
            "flagged_count": 1 if highest >= 0.5 else 0,
            "highest_score": highest,
            "average_score": average,
            "submissions": [],
        },
    }


class TestScoreBands:
    """Band selection follows the Turnitin 0 / 1-19 / 20-49 / 50-79 / 80-100 split."""

    def test_zero_maps_to_no_patterns(self) -> None:
        band = _score_band(0.0)
        assert band["label"] == "No AI patterns detected"
        assert band["display"] == "0%"

    def test_faint_range_uses_asterisk_display(self) -> None:
        for score in (0.01, 0.07, 0.19):
            band = _score_band(score)
            assert band["label"] == "Faint AI patterns"
            assert band["display"] == "*%"

    def test_mixed_band(self) -> None:
        band = _score_band(0.35)
        assert band["label"] == "Mixed \u2014 possibly AI-assisted"
        assert band["display"] == "35%"

    def test_substantial_band(self) -> None:
        band = _score_band(0.65)
        assert band["label"] == "Substantial AI involvement"
        assert band["display"] == "65%"

    def test_likely_band(self) -> None:
        band = _score_band(0.92)
        assert band["label"] == "Likely AI-generated"
        assert band["display"] == "92%"

    def test_scores_clamped(self) -> None:
        assert _score_band(-0.5)["label"] == "No AI patterns detected"
        assert _score_band(1.5)["display"] == "100%"


class TestReportRendering:
    """The HTML report surfaces the headline score the Turnitin way."""

    def test_report_shows_band_interpretation_table(self) -> None:
        html = build_ai_originality_report_html(_job(0.86, 0.61))
        assert "How to Read This Score" in html
        assert "THIS REPORT" in html
        assert "Likely AI-generated" in html

    def test_report_headline_uses_asterisk_for_faint_scores(self) -> None:
        html = build_ai_originality_report_html(_job(0.07))
        assert "AI-Generated Code Score: *%" in html
        assert "false-positive protection" in html

    def test_zero_score_report(self) -> None:
        html = build_ai_originality_report_html(_job(0.0))
        assert "AI-Generated Code Score: 0%" in html
        assert "No AI patterns detected" in html


class TestInterpretationTable:
    """The band table highlights only the active row."""

    def test_single_active_row(self) -> None:
        html = _band_interpretation_table("Substantial AI involvement")
        assert html.count("THIS REPORT") == 1
        assert "50\u201379%" in html
        assert "80\u2013100%" in html

    def test_all_five_bands_present(self) -> None:
        html = _band_interpretation_table("Faint AI patterns")
        for label in (
            "Likely AI-generated",
            "Substantial AI involvement",
            "Mixed \u2014 possibly AI-assisted",
            "Faint AI patterns",
            "No AI patterns detected",
        ):
            assert label in html
