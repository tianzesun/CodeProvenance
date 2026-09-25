"""Tests for professor-facing assignment mode policy."""

from __future__ import annotations

from src.backend.engines.scoring.assignment_modes import (
    ASSIGNMENT_TYPE_MODE_MAP,
    DEFAULT_ASSIGNMENT_MODE_ID,
    assignment_modes_payload,
    get_assignment_mode,
    get_assignment_modes,
    recommend_assignment_mode,
    recommend_mode_for_assignment_type,
    universal_preprocessing_policy,
)
from src.backend.engines.scoring.fusion_engine import load_engine_config


def test_universal_preprocessing_is_mandatory_and_comment_policy_is_explicit() -> None:
    """Every mode must inherit a documented preprocessing contract."""
    policy = universal_preprocessing_policy()
    stage_ids = {stage["id"] for stage in policy.stages}

    assert stage_ids == {
        "encoding_normalization",
        "whitespace_normalization",
        "comment_handling",
        "metadata_stripping",
        "file_tree_normalization",
    }
    assert policy.comment_policy["token_engine"] == "preserve"
    assert policy.comment_policy["structural_engines"] == "exclude"
    assert "encoding_changes" in policy.required_logs


def test_assignment_catalog_contains_professor_modes() -> None:
    """The catalog should expose the standard modes, overlay, and custom mode."""
    modes = get_assignment_modes()

    assert set(modes) == {
        "intro_programming",
        "data_structures_algorithms",
        "systems_programming",
        "database_sql",
        "software_engineering_large_project",
        "ml_data_science",
        "web_development",
        "theory_proofs",
        "research_report_essay",
        "exam_mode",
        "custom",
        "notebook_ai",
        "sql_data_logic",
        "systems_projects",
        "reports_proofs",
        "foundations_code",
        "algorithmic_code",
    }


def test_intro_mode_requires_starter_code_warning_and_class_baseline() -> None:
    """Intro programming needs starter-code and class-baseline safeguards."""
    mode = get_assignment_mode("intro_programming")

    assert "starter_files_recommended" in mode.required_inputs
    assert any("No starter code provided" in warning for warning in mode.warnings)
    assert "compute_class_baseline_before_pair_scoring" in mode.calibration
    assert mode.detection_passes[0]["name"] == "normalized_token_comparison"


def test_exam_mode_is_overlay_not_standalone_engine_policy() -> None:
    """Exam mode should modify time interpretation without replacing base mode logic."""
    mode = get_assignment_mode("exam_mode")

    assert mode.overlay is True
    assert mode.base_mode_required is True
    assert "base_mode_required" in mode.required_inputs
    assert "keep base-mode engine weights" in mode.calibration


def test_custom_mode_is_advanced_and_warns_about_unvalidated_results() -> None:
    """Custom mode should be clearly separated from validated standard modes."""
    mode = get_assignment_mode("custom")

    assert mode.access == "advanced"
    assert "explicit_advanced_opt_in" in mode.required_inputs
    assert any("not been validated" in warning for warning in mode.warnings)


def test_assignment_modes_payload_includes_cross_mode_policy() -> None:
    """The API payload should include system-level decisions for future features."""
    payload = assignment_modes_payload()

    assert payload["default_mode_id"] == DEFAULT_ASSIGNMENT_MODE_ID
    assert len(payload["modes"]) == 17  # Current mode count
    assert "universal_preprocessing" in payload
    assert "professor_feedback_loop" in payload["cross_mode_policy"]


def test_engine_config_publishes_assignment_modes() -> None:
    """Engine configuration should expose mode policy to settings and reports."""
    config = load_engine_config()

    assert config["assignment_modes"]["default_mode_id"] == DEFAULT_ASSIGNMENT_MODE_ID
    assert len(config["assignment_modes"]["modes"]) == 17  # Current mode count


def test_mode_recommender_detects_sql_assignment_from_content_hints() -> None:
    """Professors should get mode suggestions from assignment metadata."""
    recommendation = recommend_assignment_mode(
        assignment_name="Complex SQL joins and schema design",
        filenames=["answers.sql", "schema.sql"],
    )

    assert recommendation["recommended_mode_id"] == "database_sql"
    assert recommendation["confidence"] > 0.5
    assert recommendation["reasons"]


def test_mode_recommender_detects_notebook_assignment() -> None:
    """Notebook-heavy assignments should map to ML/Data Science mode."""
    recommendation = recommend_assignment_mode(
        assignment_name="Kaggle model report",
        filenames=["analysis.ipynb", "README.md"],
        content_samples=[
            "import pandas as pd\nfrom sklearn.model_selection import train_test_split"
        ],
    )

    assert recommendation["recommended_mode_id"] == "ml_data_science"


def test_stored_assignment_types_map_to_modes_with_engine_weights() -> None:
    """Stored assignment types must resolve to catalog modes that carry engines."""
    known_modes = set(get_assignment_modes())

    assert set(ASSIGNMENT_TYPE_MODE_MAP.values()) <= known_modes
    for stored_type in ASSIGNMENT_TYPE_MODE_MAP:
        recommendation = recommend_mode_for_assignment_type(stored_type)

        assert recommendation["matched"] is True
        assert recommendation["mode_id"] in known_modes
        assert recommendation["mode_name"]
        assert recommendation["engine_weights"]
        assert 0 < len(recommendation["top_engines"]) <= 3

    assert recommend_mode_for_assignment_type("programming")["mode_id"] == "algorithmic_code"
    assert recommend_mode_for_assignment_type("Project")["mode_id"] == "systems_projects"


def test_unmapped_assignment_type_returns_no_recommendation() -> None:
    """Unmapped stored types must not invent a mode or engine weights."""
    for stored_type in (None, "", "   ", "mystery_type"):
        recommendation = recommend_mode_for_assignment_type(stored_type)

        assert recommendation["matched"] is False
        assert recommendation["mode_id"] is None
        assert recommendation["mode_name"] is None
        assert recommendation["engine_weights"] == {}
        assert recommendation["top_engines"] == []
        assert recommendation["reason"]
