"""Tests for professor-facing detection profiles."""

from src.backend.engines.scoring.professor_profiles import (
    AssignmentSignals,
    apply_professor_profile,
    professor_profile_catalog,
    professor_profile_to_engine_weights,
    infer_assignment_profile,
)


def test_default_professor_profile_is_auto_balanced_top_25() -> None:
    """Defaults should match the recommended simple professor setup."""
    applied = apply_professor_profile({})

    assert applied.profile.assignment_type == "auto_detect"
    assert applied.profile.sensitivity == "balanced"
    assert applied.profile.starter_code_handling == "student_written_only"
    assert applied.profile.previous_term_matching == "same_course_only"
    assert applied.profile.result_volume == "top_25"
    assert applied.result_limit == 25
    assert applied.threshold == 0.75
    assert applied.policy["auto_assignment_detection"] is True
    assert applied.policy["per_assignment_calibration"] is True


def test_structured_logic_profile_emphasizes_ast_cfg_and_runtime() -> None:
    """Structured logic should shift weight toward structure and program flow."""
    applied = apply_professor_profile(
        {
            "assignment_type": "structured_logic",
            "sensitivity": "balanced",
        }
    )

    assert applied.weights["ast"] > applied.weights["token"]
    assert applied.weights["cfg_dfg"] > applied.weights["token"]
    assert applied.weights["runtime"] > applied.weights["history"]
    assert "control flow" in applied.recommendation


def test_project_profile_prioritizes_history_and_module_level_compare() -> None:
    """Project profile should prioritize history and module-level comparison."""
    applied = apply_professor_profile(
        {
            "assignment_type": "project_multi_file",
            "previous_term_matching": "all_historical_courses",
        }
    )

    assert applied.weights["history"] > applied.weights["token"]
    assert applied.policy["module_level_compare"] is True
    assert applied.policy["dependency_aware_compare"] is True
    assert applied.profile.previous_term_matching == "all_historical_courses"


def test_legacy_assignment_profile_ids_are_mapped_to_five_profile_model() -> None:
    """Stored six-profile settings should keep working after profile consolidation."""
    data_structures = apply_professor_profile({"assignment_type": "data_structures"})
    algorithms = apply_professor_profile({"assignment_type": "algorithms"})
    web = apply_professor_profile({"assignment_type": "web_project"})
    group = apply_professor_profile({"assignment_type": "group_project"})
    notebook = apply_professor_profile({"assignment_type": "data_analysis_notebook"})

    assert data_structures.profile.assignment_type == "structured_logic"
    assert algorithms.profile.assignment_type == "structured_logic"
    assert web.profile.assignment_type == "project_multi_file"
    assert group.profile.assignment_type == "project_multi_file"
    assert notebook.profile.assignment_type == "notebook_data_analysis"


def test_notebook_profile_uses_cell_aware_custom_logic_policy() -> None:
    """Notebook assignments should suppress notebook boilerplate and import noise."""
    applied = apply_professor_profile({"assignment_type": "notebook_data_analysis"})

    assert applied.weights["history"] > applied.weights["ast"]
    assert applied.policy["cell_aware_compare"] is True
    assert applied.policy["ignore_import_cells"] is True
    assert applied.policy["compare_custom_logic_only"] is True


def test_assignment_profile_inference_uses_assignment_shape_signals() -> None:
    """Auto-detect should infer broad assignment shape from available metadata."""
    assert (
        infer_assignment_profile(AssignmentSignals(notebook_present=True))
        == "notebook_data_analysis"
    )
    assert (
        infer_assignment_profile(
            AssignmentSignals(file_count=8, test_files_present=True)
        )
        == "project_multi_file"
    )
    assert (
        infer_assignment_profile(AssignmentSignals(function_count=5))
        == "structured_logic"
    )
    assert (
        infer_assignment_profile(AssignmentSignals(file_count=1)) == "intro_programming"
    )


def test_sensitivity_changes_threshold_without_exposing_raw_threshold_setting() -> None:
    """Conservative should be stricter than strict mode internally."""
    conservative = apply_professor_profile({"sensitivity": "conservative"})
    strict = apply_professor_profile({"sensitivity": "strict"})

    assert conservative.threshold > strict.threshold


def test_professor_profile_to_engine_weights_returns_normalized_engine_keys() -> None:
    """Simple profile weights should map to current engine weights."""
    applied = apply_professor_profile({"assignment_type": "structured_logic"})
    engine_weights = professor_profile_to_engine_weights(applied)

    assert round(sum(engine_weights.values()), 4) == 1.0
    assert engine_weights["ast"] > 0
    assert engine_weights["graph"] > 0
    assert engine_weights["execution"] > 0


def test_catalog_contains_all_simple_settings() -> None:
    """API catalog must expose the simple settings UI needs."""
    catalog = professor_profile_catalog()

    assert [item["id"] for item in catalog["assignment_types"]] == [
        "auto_detect",
        "intro_programming",
        "structured_logic",
        "project_multi_file",
        "notebook_data_analysis",
        "custom_advanced",
    ]
    assert {item["id"] for item in catalog["review_modes"]} == {
        "conservative",
        "balanced",
        "strict",
    }
    assert any(
        item["id"] == "student_written_only"
        for item in catalog["starter_code_handling"]
    )
