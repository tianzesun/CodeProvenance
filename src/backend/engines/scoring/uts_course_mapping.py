"""
UTSC Computer Science Course to Assignment Mode Mapping.

Maps UTSC CSC course codes to the most appropriate assignment mode for
similarity detection engine weighting. Based on the 2024-2026 UTSC Calendar.

Only modes with explicit YAML weights in engine_weights.yaml are used:
- foundations_code (intro CS)
- algorithmic_code (data structures/algorithms)
- systems_projects (systems/programming projects)
- sql_data_logic (database/SQL)
- notebook_ai (ML/data science/notebooks)
- reports_proofs (text/theory/reports)
"""

from __future__ import annotations

# Mapping from UTSC course code to assignment mode ID with explicit YAML weights
UTSC_COURSE_MODE_MAP: dict[str, str] = {
    # A-level (introductory) -> foundations_code
    "CSCA08H3": "foundations_code",      # Introduction to Computer Science I
    "CSCA48H3": "foundations_code",      # Introduction to Computer Science II
    "CSCA20H3": "foundations_code",      # Introduction to Programming (non-major)

    # A-level theory -> reports_proofs (proof-heavy)
    "CSCA67H3": "reports_proofs",        # Discrete Mathematics (proof-heavy)

    # B-level
    "CSCB07H3": "systems_projects",      # Software Design -> systems project
    "CSCB09H3": "systems_projects",      # Software Tools and Systems Programming
    "CSCB58H3": "systems_projects",      # Computer Organization
    "CSCB63H3": "algorithmic_code",      # Design and Analysis of Data Structures
    "CSCB20H3": "sql_data_logic",        # Introduction to Database and Web Applications
    "CSCB36H3": "reports_proofs",        # Theory of Computation (proof-heavy)

    # C-level
    "CSCC01H3": "systems_projects",      # Introduction to Software Engineering
    "CSCC09H3": "notebook_ai",           # Programming on the Web (modern web = notebook-like)
    "CSCC10H3": "notebook_ai",           # Human-Computer Interaction
    "CSCC11H3": "notebook_ai",           # Introduction to Machine Learning and Data Mining
    "CSCC24H3": "reports_proofs",        # Principles of Programming Languages (theory)
    "CSCC37H3": "algorithmic_code",      # Numerical Algorithms for Computational Mathematics
    "CSCC43H3": "sql_data_logic",        # Introduction to Databases
    "CSCC46H3": "notebook_ai",           # Social and Information Networks
    "CSCC63H3": "reports_proofs",        # Computability and Computational Complexity
    "CSCC69H3": "systems_projects",      # Operating Systems
    "CSCC73H3": "algorithmic_code",      # Algorithm Design and Analysis
    "CSCC85H3": "systems_projects",      # Fundamentals of Robotics and Automated Systems

    # D-level
    "CSCD01H3": "systems_projects",      # Engineering Large Software Systems
    "CSCD03H3": "reports_proofs",        # Social Impact of Information Technology (text)
    "CSCD18H3": "algorithmic_code",      # Computer Graphics
    "CSCD25H3": "notebook_ai",           # Advanced Data Science
    "CSCD27H3": "systems_projects",      # Computer and Network Security
    "CSCD37H3": "algorithmic_code",      # Analysis of Numerical Algorithms
    "CSCD43H3": "sql_data_logic",        # Database System Technology
    "CSCD58H3": "systems_projects",      # Computer Networks
    "CSCD70H3": "systems_projects",      # Compiler Optimization
    "CSCD84H3": "notebook_ai",           # Artificial Intelligence
    "CSCD90H3": "systems_projects",      # The Startup Sandbox
    "CSCD92H3": "reports_proofs",        # Readings in Computer Science
    "CSCD94H3": "systems_projects",      # Computer Science Project
    "CSCD95H3": "systems_projects",      # Computer Science Project
}


def get_mode_for_course(course_code: str) -> str | None:
    """
    Return the assignment mode ID for a given UTSC course code.

    Args:
        course_code: UTSC course code (e.g., "CSCA08H3")

    Returns:
        Assignment mode ID, or None if not found.
    """
    return UTSC_COURSE_MODE_MAP.get(course_code.upper())


def get_all_mapped_courses() -> list[str]:
    """Return a sorted list of all mapped course codes."""
    return sorted(UTSC_COURSE_MODE_MAP.keys())