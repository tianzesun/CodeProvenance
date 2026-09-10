"""Tests for UTSC course to assignment mode mapping."""

from src.backend.engines.scoring.uts_course_mapping import (
    UTSC_COURSE_MODE_MAP,
    get_mode_for_course,
    get_all_mapped_courses,
)


def test_mapping_contains_expected_courses() -> None:
    """Ensure key UTSC courses are mapped."""
    assert "CSCA08H3" in UTSC_COURSE_MODE_MAP
    assert "CSCA48H3" in UTSC_COURSE_MODE_MAP
    assert "CSCB63H3" in UTSC_COURSE_MODE_MAP
    assert "CSCC73H3" in UTSC_COURSE_MODE_MAP
    assert "CSCD01H3" in UTSC_COURSE_MODE_MAP


def test_mapping_values_are_valid_modes() -> None:
    """All mapped modes should be known assignment mode IDs."""
    from src.backend.engines.scoring.assignment_modes import get_assignment_modes

    valid_modes = set(get_assignment_modes().keys())
    for mode in UTSC_COURSE_MODE_MAP.values():
        assert mode in valid_modes, f"Mode {mode} not in assignment modes catalog"


def test_get_mode_for_course_case_insensitive() -> None:
    """Lookup should be case-insensitive."""
    assert get_mode_for_course("csca08h3") == "foundations_code"
    assert get_mode_for_course("CSCA08H3") == "foundations_code"
    assert get_mode_for_course("CsCa08H3") == "foundations_code"


def test_get_mode_for_course_unknown_returns_none() -> None:
    """Unknown course codes return None."""
    assert get_mode_for_course("INVALID") is None
    assert get_mode_for_course("") is None


def test_get_all_mapped_courses_sorted() -> None:
    """Returned list should be sorted alphabetically."""
    courses = get_all_mapped_courses()
    assert courses == sorted(courses)
    assert len(courses) == len(UTSC_COURSE_MODE_MAP)


def test_introductory_courses_map_to_foundations_code() -> None:
    """First-year courses should map to foundations_code."""
    assert get_mode_for_course("CSCA08H3") == "foundations_code"
    assert get_mode_for_course("CSCA48H3") == "foundations_code"
    assert get_mode_for_course("CSCA20H3") == "foundations_code"


def test_data_structures_course_maps_to_algorithmic_code() -> None:
    """CSCB63H3 (Design and Analysis of Data Structures) -> algorithmic_code."""
    assert get_mode_for_course("CSCB63H3") == "algorithmic_code"


def test_algorithm_course_maps_to_algorithmic_code() -> None:
    """CSCC73H3 (Algorithm Design and Analysis) -> algorithmic_code."""
    assert get_mode_for_course("CSCC73H3") == "algorithmic_code"


def test_systems_courses_map_to_systems_projects() -> None:
    """Systems courses map to systems_projects (has explicit YAML weights)."""
    assert get_mode_for_course("CSCB09H3") == "systems_projects"
    assert get_mode_for_course("CSCB58H3") == "systems_projects"
    assert get_mode_for_course("CSCC69H3") == "systems_projects"
    assert get_mode_for_course("CSCD58H3") == "systems_projects"
    assert get_mode_for_course("CSCD01H3") == "systems_projects"
    assert get_mode_for_course("CSCD27H3") == "systems_projects"
    assert get_mode_for_course("CSCD70H3") == "systems_projects"
    assert get_mode_for_course("CSCD90H3") == "systems_projects"
    assert get_mode_for_course("CSCD94H3") == "systems_projects"
    assert get_mode_for_course("CSCD95H3") == "systems_projects"
    assert get_mode_for_course("CSCC01H3") == "systems_projects"
    assert get_mode_for_course("CSCC85H3") == "systems_projects"


def test_database_courses_map_to_sql_data_logic() -> None:
    """Database courses map to sql_data_logic (has explicit YAML weights)."""
    assert get_mode_for_course("CSCB20H3") == "sql_data_logic"
    assert get_mode_for_course("CSCC43H3") == "sql_data_logic"
    assert get_mode_for_course("CSCD43H3") == "sql_data_logic"


def test_ml_courses_map_to_notebook_ai() -> None:
    """Machine learning courses map to notebook_ai (has explicit YAML weights)."""
    assert get_mode_for_course("CSCC11H3") == "notebook_ai"
    assert get_mode_for_course("CSCD25H3") == "notebook_ai"
    assert get_mode_for_course("CSCD84H3") == "notebook_ai"
    assert get_mode_for_course("CSCC46H3") == "notebook_ai"
    assert get_mode_for_course("CSCC09H3") == "notebook_ai"
    assert get_mode_for_course("CSCC10H3") == "notebook_ai"


def test_web_courses_map_to_notebook_ai() -> None:
    """Web development courses map to notebook_ai (modern web = notebook-like)."""
    assert get_mode_for_course("CSCC09H3") == "notebook_ai"
    assert get_mode_for_course("CSCC10H3") == "notebook_ai"


def test_theory_courses_map_to_reports_proofs() -> None:
    """Theory/proof courses map to reports_proofs (has explicit YAML weights)."""
    assert get_mode_for_course("CSCA67H3") == "reports_proofs"
    assert get_mode_for_course("CSCB36H3") == "reports_proofs"
    assert get_mode_for_course("CSCC24H3") == "reports_proofs"
    assert get_mode_for_course("CSCC63H3") == "reports_proofs"
    assert get_mode_for_course("CSCD03H3") == "reports_proofs"
    assert get_mode_for_course("CSCD92H3") == "reports_proofs"