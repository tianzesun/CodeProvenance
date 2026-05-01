"""Professor-facing detection profiles.

Professors choose assignment type and simple sensitivity controls. This module
maps those choices to internal evidence weights and policy flags while keeping
engine coefficients hidden from the normal UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


ASSIGNMENT_TYPE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "auto_detect": {
        "token": 0.18,
        "ast": 0.24,
        "cfg_dfg": 0.22,
        "runtime": 0.22,
        "history": 0.14,
    },
    "intro_programming": {
        "token": 0.32,
        "ast": 0.18,
        "cfg_dfg": 0.08,
        "runtime": 0.28,
        "history": 0.14,
    },
    "structured_logic": {
        "token": 0.13,
        "ast": 0.26,
        "cfg_dfg": 0.30,
        "runtime": 0.23,
        "history": 0.08,
    },
    "project_multi_file": {
        "token": 0.12,
        "ast": 0.18,
        "cfg_dfg": 0.18,
        "runtime": 0.08,
        "history": 0.44,
    },
    "notebook_data_analysis": {
        "token": 0.20,
        "ast": 0.08,
        "cfg_dfg": 0.06,
        "runtime": 0.22,
        "history": 0.44,
    },
    "custom_advanced": {
        "token": 0.20,
        "ast": 0.20,
        "cfg_dfg": 0.20,
        "runtime": 0.20,
        "history": 0.20,
    },
}

ASSIGNMENT_TYPE_ALIASES: Dict[str, str] = {
    "data_structures": "structured_logic",
    "algorithms": "structured_logic",
    "web_project": "project_multi_file",
    "group_project": "project_multi_file",
    "project_software_engineering": "project_multi_file",
    "data_analysis_notebook": "notebook_data_analysis",
    "notebook_data_analysis_ai": "notebook_data_analysis",
}


@dataclass(frozen=True)
class AssignmentSignals:
    """Signals used to infer the professor-facing assignment profile."""

    language: str = ""
    file_count: int = 1
    average_lines_of_code: int = 0
    class_count: int = 0
    function_count: int = 0
    notebook_present: bool = False
    starter_code_similarity: float = 0.0
    test_files_present: bool = False


@dataclass(frozen=True)
class ProfessorProfile:
    """Simple settings selected by a professor or administrator."""

    assignment_type: str = "auto_detect"
    sensitivity: str = "balanced"
    starter_code_handling: str = "student_written_only"
    previous_term_matching: str = "same_course_only"
    ai_rewrite_detection: str = "balanced"
    result_volume: str = "top_25"


@dataclass(frozen=True)
class AppliedProfessorProfile:
    """Internal policy derived from professor settings."""

    profile: ProfessorProfile
    weights: Dict[str, float]
    threshold: float
    result_limit: int | None
    policy: Dict[str, Any]
    summary: str
    recommendation: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the applied profile for APIs and UI."""
        return {
            "profile": self.profile.__dict__,
            "weights": dict(self.weights),
            "threshold": self.threshold,
            "result_limit": self.result_limit,
            "policy": dict(self.policy),
            "summary": self.summary,
            "recommendation": self.recommendation,
            "warnings": list(self.warnings),
        }


def professor_profile_catalog() -> Dict[str, Any]:
    """Return professor-facing option catalog."""
    return {
        "assignment_types": [
            {
                "id": "auto_detect",
                "label": "Auto Detect",
                "description": "Recommended. Infer the best profile from files, language, structure, starter code, and tests.",
            },
            {
                "id": "intro_programming",
                "label": "Intro Programming",
                "description": "Small CS1/CS2 programs where shared starter code is common.",
            },
            {
                "id": "structured_logic",
                "label": "Structured Logic",
                "description": "Data structures, OOP, recursion, algorithms, control flow, and edge cases.",
            },
            {
                "id": "project_multi_file",
                "label": "Project / Multi-file",
                "description": "Multi-file apps, team projects, capstones, and framework-heavy work.",
            },
            {
                "id": "notebook_data_analysis",
                "label": "Notebook / Data Analysis",
                "description": "Jupyter, R, pandas, plotting, and ML homework with notebook noise.",
            },
            {
                "id": "custom_advanced",
                "label": "Custom Advanced",
                "description": "Use administrator-controlled engine weights and thresholds.",
            },
        ],
        "review_modes": [
            {
                "id": "conservative",
                "label": "Conservative",
                "description": "Fewer false positives, best for formal investigation.",
            },
            {
                "id": "balanced",
                "label": "Balanced",
                "description": "Recommended default for normal review queues.",
            },
            {
                "id": "strict",
                "label": "Strict",
                "description": "Shows more potentially suspicious cases for early triage.",
            },
        ],
        "sensitivities": [
            {
                "id": "conservative",
                "label": "Conservative",
                "description": "Fewer false positives, best for formal investigation.",
            },
            {
                "id": "balanced",
                "label": "Balanced",
                "description": "Recommended default for normal review queues.",
            },
            {
                "id": "strict",
                "label": "Strict",
                "description": "Shows more potentially suspicious cases for early triage.",
            },
        ],
        "starter_code_handling": [
            {"id": "ignore_starter_code", "label": "Ignore starter code"},
            {
                "id": "student_written_only",
                "label": "Compare only student-written code",
            },
            {"id": "include_starter_code", "label": "Include starter code"},
        ],
        "previous_term_matching": [
            {"id": "off", "label": "Off"},
            {"id": "same_course_only", "label": "Same course only"},
            {"id": "all_historical_courses", "label": "All historical courses"},
        ],
        "ai_rewrite_detection": [
            {"id": "off", "label": "Off"},
            {"id": "balanced", "label": "Balanced"},
            {"id": "aggressive", "label": "Aggressive"},
        ],
        "result_volume": [
            {"id": "top_10", "label": "Show top 10", "limit": 10},
            {"id": "top_25", "label": "Show top 25", "limit": 25},
            {"id": "top_50", "label": "Show top 50", "limit": 50},
        ],
    }


def apply_professor_profile(raw: Dict[str, Any] | None) -> AppliedProfessorProfile:
    """Convert persisted professor settings into internal detection policy."""
    raw = raw or {}
    profile = ProfessorProfile(
        assignment_type=_assignment_type(
            raw.get("assignment_type"),
        ),
        sensitivity=_valid(
            raw.get("sensitivity"),
            {"conservative": 1, "balanced": 1, "strict": 1},
            "balanced",
        ),
        starter_code_handling=_valid(
            raw.get("starter_code_handling"),
            {
                "ignore_starter_code": 1,
                "student_written_only": 1,
                "include_starter_code": 1,
            },
            "student_written_only",
        ),
        previous_term_matching=_valid(
            raw.get("previous_term_matching"),
            {"off": 1, "same_course_only": 1, "all_historical_courses": 1},
            "same_course_only",
        ),
        ai_rewrite_detection=_valid(
            raw.get("ai_rewrite_detection"),
            {"off": 1, "balanced": 1, "aggressive": 1},
            "balanced",
        ),
        result_volume=_valid(
            raw.get("result_volume"),
            {"top_10": 1, "top_25": 1, "top_50": 1, "all": 1},
            "top_25",
        ),
    )

    weights = dict(ASSIGNMENT_TYPE_WEIGHTS[profile.assignment_type])
    threshold = {"conservative": 0.84, "balanced": 0.75, "strict": 0.64}[
        profile.sensitivity
    ]
    if profile.ai_rewrite_detection == "aggressive":
        weights["cfg_dfg"] += 0.03
        weights["ast"] += 0.02
        weights["token"] = max(0.0, weights["token"] - 0.05)
    elif profile.ai_rewrite_detection == "off":
        threshold += 0.02

    weights = _normalize_weights(weights)
    result_limit = {"top_10": 10, "top_25": 25, "top_50": 50, "all": None}[
        profile.result_volume
    ]
    policy = {
        "starter_code": profile.starter_code_handling,
        "previous_terms": profile.previous_term_matching,
        "ai_rewrite_label": "Possible AI-assisted rewrite",
        "auto_assignment_detection": profile.assignment_type == "auto_detect",
        "per_assignment_calibration": True,
        "threshold_strategy": "distribution_outliers_and_score_gaps",
        "false_positive_suppression": [
            "starter_code",
            "public_template",
            "common_solution",
            "library_code",
            "instructor_tests",
            "lms_packaging_files",
        ],
        "show_engine_weights_to_professor": False,
        "high_risk_requires_concrete_evidence": True,
        **_assignment_policy(profile.assignment_type),
    }
    warnings = []
    if profile.starter_code_handling == "include_starter_code":
        warnings.append("Including starter code can increase false positives.")
    if profile.previous_term_matching == "off":
        warnings.append("Previous-term reuse will not be checked.")

    return AppliedProfessorProfile(
        profile=profile,
        weights=weights,
        threshold=round(threshold, 3),
        result_limit=result_limit,
        policy=policy,
        summary=_summary(profile),
        recommendation=_recommendation(profile),
        warnings=warnings,
    )


def infer_assignment_profile(signals: AssignmentSignals | Dict[str, Any]) -> str:
    """Infer the simple assignment profile from assignment-level metadata."""
    if isinstance(signals, dict):
        allowed = AssignmentSignals.__dataclass_fields__
        signals = AssignmentSignals(
            **{key: value for key, value in signals.items() if key in allowed}
        )

    language = signals.language.lower()
    if signals.notebook_present or language in {"ipynb", "notebook", "r"}:
        return "notebook_data_analysis"
    if signals.file_count >= 6 or signals.test_files_present:
        return "project_multi_file"
    if signals.class_count >= 2 or signals.function_count >= 4:
        return "structured_logic"
    if signals.average_lines_of_code >= 120:
        return "structured_logic"
    return "intro_programming"


def professor_profile_to_engine_weights(
    applied: AppliedProfessorProfile,
) -> Dict[str, float]:
    """Map professor evidence weights to current engine-weight keys."""
    weights = applied.weights
    return _normalize_weights(
        {
            "token": weights["token"] * 0.55,
            "winnowing": weights["token"] * 0.45,
            "ast": weights["ast"],
            "graph": weights["cfg_dfg"] * 0.60,
            "execution": weights["runtime"] + weights["cfg_dfg"] * 0.40,
            "embedding": weights["history"] * 0.45,
            "llm": 0.02 if applied.profile.ai_rewrite_detection != "off" else 0.0,
        }
    )


def _valid(value: Any, allowed: Dict[str, Any], fallback: str) -> str:
    candidate = str(value or "")
    return candidate if candidate in allowed else fallback


def _assignment_type(value: Any) -> str:
    candidate = str(value or "")
    candidate = ASSIGNMENT_TYPE_ALIASES.get(candidate, candidate)
    return candidate if candidate in ASSIGNMENT_TYPE_WEIGHTS else "auto_detect"


def _assignment_policy(assignment_type: str) -> Dict[str, Any]:
    base = {
        "starter_code_removal": "strong",
        "common_solution_discount": True,
        "same_bug_detection": True,
        "student_style_shift_is_standalone_evidence": False,
    }
    policies = {
        "intro_programming": {
            "token_normalization": "strong",
            "identifier_literal_normalization": "strong",
            "same_wrong_answer_boost": "strong",
        },
        "structured_logic": {
            "structure_evidence": "strong",
            "control_flow_evidence": "strong",
            "data_flow_evidence": "strong",
            "edge_case_behavior": "strong",
            "loop_and_branch_order": "strong",
            "helper_function_pattern": "strong",
        },
        "auto_detect": {
            "auto_engine_selection": True,
            "auto_threshold_calibration": True,
            "rare_pattern_boost": True,
            "control_flow_evidence": "strong",
            "data_flow_evidence": "strong",
            "edge_case_behavior": "strong",
        },
        "project_multi_file": {
            "module_level_compare": True,
            "dependency_aware_compare": True,
            "framework_template_discount": "strong",
            "token_noise_discount": "strong",
        },
        "notebook_data_analysis": {
            "cell_aware_compare": True,
            "ignore_import_cells": True,
            "ignore_markdown_noise": True,
            "compare_custom_logic_only": True,
        },
        "custom_advanced": {
            "admin_controlled_weights": True,
            "advanced_settings_visible": True,
        },
    }
    return {**base, **policies.get(assignment_type, {})}


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(0.0, float(value)) for value in weights.values())
    if total <= 0:
        return dict(weights)
    return {key: max(0.0, float(value)) / total for key, value in weights.items()}


def _summary(profile: ProfessorProfile) -> str:
    labels = {
        "auto_detect": "Auto Detect",
        "intro_programming": "Intro Programming",
        "structured_logic": "Structured Logic",
        "project_multi_file": "Project / Multi-file",
        "notebook_data_analysis": "Notebook / Data Analysis",
        "custom_advanced": "Custom Advanced",
    }
    return f"{labels[profile.assignment_type]} / {profile.sensitivity.title()} profile applied."


def _recommendation(profile: ProfessorProfile) -> str:
    if profile.assignment_type == "auto_detect":
        return "Recommended profile applied: assignment type, engine weights, thresholds, and false-positive filters are selected automatically."
    if profile.assignment_type == "structured_logic":
        return "Better for renamed variables, reordered functions, control flow, and shared edge-case bugs."
    if profile.assignment_type == "project_multi_file":
        return "Better for multi-file projects, dependency-aware comparison, and previous-term reuse."
    if profile.assignment_type == "notebook_data_analysis":
        return "Better for notebooks by ignoring imports and comparing custom analysis logic."
    if profile.assignment_type == "custom_advanced":
        return "Advanced profile applied: administrator-controlled weights are used."
    return "Better for simple copying, starter-code removal, and shared wrong answers."
