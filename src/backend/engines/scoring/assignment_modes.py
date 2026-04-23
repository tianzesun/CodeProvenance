"""Versioned professor-facing assignment modes.

The mode catalog is product policy, not engine math. It tells the upload flow,
results UI, and reports which preprocessing gates are mandatory, which signals
matter for each assignment type, and which evidence views should be surfaced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


MODE_CATALOG_VERSION = "2026.04.phase2"
DEFAULT_ASSIGNMENT_MODE_ID = "intro_programming"


@dataclass(frozen=True)
class UniversalPreprocessingPolicy:
    """Mandatory preprocessing applied before any mode-specific analysis."""

    version: str
    stages: List[Dict[str, Any]]
    comment_policy: Dict[str, Any]
    required_logs: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the universal preprocessing policy."""
        return {
            "version": self.version,
            "stages": list(self.stages),
            "comment_policy": dict(self.comment_policy),
            "required_logs": list(self.required_logs),
        }


@dataclass(frozen=True)
class AssignmentMode:
    """Professor-selectable assignment mode with scoring and evidence policy."""

    mode_id: str
    version: str
    name: str
    category: str
    access: str
    context: str
    preprocessing: List[str]
    required_inputs: List[str]
    detection_passes: List[Dict[str, Any]]
    calibration: List[str]
    evidence_surfaces: List[str]
    edge_case_policies: List[str]
    warnings: List[str] = field(default_factory=list)
    pipelines: List[str] = field(default_factory=lambda: ["code"])
    overlay: bool = False
    base_mode_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the mode for APIs and persisted job metadata."""
        return {
            "id": self.mode_id,
            "version": self.version,
            "name": self.name,
            "category": self.category,
            "access": self.access,
            "context": self.context,
            "preprocessing": list(self.preprocessing),
            "required_inputs": list(self.required_inputs),
            "detection_passes": list(self.detection_passes),
            "calibration": list(self.calibration),
            "evidence_surfaces": list(self.evidence_surfaces),
            "edge_case_policies": list(self.edge_case_policies),
            "warnings": list(self.warnings),
            "pipelines": list(self.pipelines),
            "overlay": self.overlay,
            "base_mode_required": self.base_mode_required,
        }


def universal_preprocessing_policy() -> UniversalPreprocessingPolicy:
    """Return the mandatory preprocessing contract for every mode."""
    return UniversalPreprocessingPolicy(
        version=MODE_CATALOG_VERSION,
        stages=[
            {
                "id": "encoding_normalization",
                "name": "Encoding normalization",
                "action": "Convert all submissions to UTF-8 before parsing.",
                "log_when": "source encoding is not UTF-8 or contains unusual characters",
            },
            {
                "id": "whitespace_normalization",
                "name": "Whitespace normalization",
                "action": "Normalize indentation, trailing spaces, blank lines, and line endings.",
                "log_when": "normalization changes comparable content",
            },
            {
                "id": "comment_handling",
                "name": "Comment handling",
                "action": (
                    "Preserve comments for token evidence, exclude them from structural "
                    "engines, and surface identical comment blocks separately."
                ),
                "log_when": "identical comment blocks appear across submissions",
            },
            {
                "id": "metadata_stripping",
                "name": "Metadata stripping",
                "action": "Remove names, IDs, timestamps, and other identifying metadata.",
                "log_when": "identity-like metadata is removed",
            },
            {
                "id": "file_tree_normalization",
                "name": "File tree normalization",
                "action": "Canonicalize multi-file project roots and folder names.",
                "log_when": "project roots or folder labels are rewritten",
            },
        ],
        comment_policy={
            "token_engine": "preserve",
            "structural_engines": "exclude",
            "evidence_layer": "surface_identical_comment_blocks_as_secondary_signal",
        },
        required_logs=[
            "encoding_changes",
            "metadata_stripped",
            "comment_block_matches",
            "file_tree_rewrites",
        ],
    )


def get_assignment_modes() -> Dict[str, AssignmentMode]:
    """Return the complete professor-facing mode catalog."""
    modes = [
        AssignmentMode(
            mode_id="intro_programming",
            version="1.0.0",
            name="Introductory Programming",
            category="coding",
            access="standard",
            context="CS1 and CS2 assignments with high legitimate convergence risk.",
            preprocessing=[
                "starter_code_elimination_required_at_assignment_creation",
                "identifier_normalization",
                "dead_code_comment_cross_check",
                "canonical_intro_algorithm_matching",
            ],
            required_inputs=["starter_files_recommended"],
            detection_passes=[
                _pass("normalized_token_comparison", "highest"),
                _pass("raw_token_comparison", "high"),
                _pass("control_flow_sequence_comparison", "medium"),
            ],
            calibration=[
                "compute_class_baseline_before_pair_scoring",
                "normalize pair scores relative to class average",
                "surface class baseline in results",
            ],
            evidence_surfaces=[
                "side_by_side_normalized_view",
                "side_by_side_raw_view",
                "matching_segment_coverage",
                "identical_comment_blocks",
                "submission_timestamp_pairing",
            ],
            edge_case_policies=[
                "canonical algorithm matches are warnings, not flags",
                "elevate online tutorial/source matching for this mode",
                "warn before results if no starter code was provided",
            ],
            warnings=[
                "No starter code provided. Similarity scores may be inflated by shared template content."
            ],
        ),
        AssignmentMode(
            mode_id="data_structures_algorithms",
            version="1.0.0",
            name="Data Structures & Algorithms",
            category="coding",
            access="standard",
            context="Algorithmic assignments where correctness and similarity are correlated.",
            preprocessing=[
                "mandatory_ast_construction",
                "dead_code_and_scaffolding_strip",
                "function_level_segmentation",
                "algorithm_family_classification",
            ],
            required_inputs=["starter_files_recommended", "algorithm_family_optional"],
            detection_passes=[
                _pass("ast_structural_isomorphism", "highest"),
                _pass("control_flow_graph_comparison", "high"),
                _pass("complexity_signature_matching", "medium"),
                _pass("identifier_semantic_analysis", "low_supplementary"),
            ],
            calibration=[
                "use_algorithm_family_specific_thresholds",
                "downweight canonical textbook implementation matches",
                "prioritize public repository source matches when found",
            ],
            evidence_surfaces=[
                "ast_visualization_side_by_side",
                "function_level_breakdown",
                "public_repository_match",
                "complexity_profile_table",
            ],
            edge_case_policies=[
                "strip professor-provided skeleton and pseudocode-informed scaffold",
                "manual review flag for cross-language batches without structural support",
            ],
        ),
        AssignmentMode(
            mode_id="systems_programming",
            version="1.0.0",
            name="Systems Programming",
            category="coding",
            access="standard",
            context="Low-level projects with constrained API usage and high design variance.",
            preprocessing=[
                "system_call_suppression",
                "standard_error_handling_pattern_suppression",
                "header_include_normalization",
                "multi_file_project_assembly",
            ],
            required_inputs=["reference_implementations_as_starter_code_optional"],
            detection_passes=[
                _pass("inter_system_call_logic_comparison", "highest"),
                _pass("data_structure_design_comparison", "high"),
                _pass("memory_management_pattern_comparison", "high"),
                _pass("concurrency_pattern_comparison", "medium"),
            ],
            calibration=[
                "score independent design decision overlap",
                "separate API usage from authored logic",
                "elevate online tutorial matching",
            ],
            evidence_surfaces=[
                "design_decision_comparison_table",
                "inter_system_call_logic_diff",
                "tutorial_or_blog_source_match",
            ],
            edge_case_policies=[
                "treat provided reference implementations as starter code",
                "manual review for assembly language if no assembly engine is available",
            ],
        ),
        AssignmentMode(
            mode_id="database_sql",
            version="1.0.0",
            name="Database & SQL",
            category="database",
            access="standard",
            context="SQL assignments where semantic equivalence matters more than syntax.",
            preprocessing=[
                "sql_keyword_case_normalization",
                "sql_comment_stripping",
                "alias_normalization",
                "commutative_clause_canonicalization",
                "schema_aware_processing_when_schema_is_provided",
            ],
            required_inputs=["database_schema_recommended"],
            detection_passes=[
                _pass("normalized_string_identity", "highest"),
                _pass("query_plan_equivalence", "high"),
                _pass("clause_level_similarity", "medium"),
                _pass(
                    "relationship_topology_for_schema_design",
                    "highest_when_schema_design",
                ),
            ],
            calibration=[
                "simple_select_queries_use_very_high_threshold",
                "complex_multi_join_queries_use_moderate_threshold",
                "stored_procedures_also_run_code_pipeline",
            ],
            evidence_surfaces=[
                "normalized_query_side_by_side",
                "raw_query_side_by_side",
                "er_diagram_comparison",
                "query_plan_visualization",
            ],
            edge_case_policies=[
                "canonical textbook query patterns are warnings, not flags",
                "normalize MySQL, PostgreSQL, and SQLite dialect differences",
            ],
        ),
        AssignmentMode(
            mode_id="software_engineering_large_project",
            version="1.0.0",
            name="Software Engineering & Large Projects",
            category="project",
            access="standard",
            context="Large multi-file projects with framework boilerplate and group dynamics.",
            preprocessing=[
                "framework_scaffolding_suppression",
                "dependency_file_exclusion_by_default",
                "build_artifact_exclusion",
                "language_detection_per_file",
                "cross_semester_policy_gate",
            ],
            required_inputs=["group_roster_optional", "cross_semester_opt_in_optional"],
            detection_passes=[
                _pass("project_architecture_comparison", "high"),
                _pass("module_level_semantic_comparison", "highest"),
                _pass("function_level_cross_file_comparison", "high"),
                _pass("commit_history_analysis", "supplementary"),
                _pass("github_project_matching", "high_external"),
            ],
            calibration=[
                "report overall similarity, max module similarity, and architecture match",
                "exclude within-group pairs from cross-group plagiarism scoring",
                "use coverage-based scoring for copied functional logic",
            ],
            evidence_surfaces=[
                "project_architecture_diff",
                "module_similarity_breakdown",
                "function_match_list",
                "commit_history_summary",
                "github_match_with_file_list",
            ],
            edge_case_policies=[
                "declared reuse is separated from undeclared reuse",
                "credited open-source matches are surfaced differently from unattributed matches",
            ],
        ),
        AssignmentMode(
            mode_id="ml_data_science",
            version="1.0.0",
            name="Machine Learning & Data Science",
            category="notebook",
            access="standard",
            context="Notebook-heavy work with separate code, narrative, and AI-risk streams.",
            preprocessing=[
                "notebook_decomposition",
                "output_cell_stripping",
                "ml_library_boilerplate_suppression",
                "starter_notebook_elimination",
                "random_seed_standardization_notes",
            ],
            required_inputs=["starter_notebook_recommended", "dataset_source_optional"],
            detection_passes=[
                _pass("model_architecture_comparison", "highest_code"),
                _pass("data_pipeline_comparison", "high_code"),
                _pass("suppressed_token_logic_comparison", "medium_code"),
                _pass("markdown_ai_detection", "highest_text"),
                _pass("markdown_text_similarity", "high_text"),
                _pass("kaggle_huggingface_kernel_matching", "high_external"),
            ],
            calibration=[
                "report code and markdown scores separately",
                "apply class baseline normalization to code stream",
                "use clean, uncertain, and flag bands for AI detection",
            ],
            evidence_surfaces=[
                "separate_code_and_markdown_tabs",
                "passage_level_ai_confidence",
                "model_architecture_diagram",
                "kaggle_kernel_cell_match",
            ],
            edge_case_policies=[
                "strip declared shared exploration notebooks",
                "do not let output divergence mask code similarity",
            ],
            pipelines=["code", "text", "ai_detection"],
        ),
        AssignmentMode(
            mode_id="web_development",
            version="1.0.0",
            name="Web Development",
            category="web",
            access="standard",
            context="HTML, CSS, and JavaScript projects with high framework boilerplate.",
            preprocessing=[
                "html_css_javascript_layer_separation",
                "framework_boilerplate_suppression_per_layer",
                "minification_reversal",
                "dependency_audit_as_supplementary_signal",
                "framework_detection",
            ],
            required_inputs=["framework_optional"],
            detection_passes=[
                _pass("html_semantic_structure_comparison", "medium"),
                _pass("custom_css_rule_comparison", "medium"),
                _pass("javascript_logic_flow_comparison", "highest"),
                _pass("component_structure_comparison", "high"),
                _pass("event_handling_pattern_comparison", "medium"),
                _pass("template_theme_matching", "high_external"),
            ],
            calibration=[
                "adapt thresholds to detected framework",
                "suppress standard responsive breakpoint patterns",
                "treat visual similarity as evidence, not the only score",
            ],
            evidence_surfaces=[
                "html_css_javascript_tabs",
                "template_three_way_comparison",
                "visual_rendering_comparison",
            ],
            edge_case_policies=[
                "respect declared shared component libraries for groups",
                "use framework-version-aware normalization",
            ],
        ),
        AssignmentMode(
            mode_id="theory_proofs",
            version="1.0.0",
            name="Theory & Proofs",
            category="text",
            access="standard",
            context="Mathematical proofs where canonical structures are common.",
            preprocessing=[
                "mathematical_notation_normalization",
                "proof_type_classification",
                "named_theorem_reference_normalization",
            ],
            required_inputs=["proof_domain_optional"],
            detection_passes=[
                _pass("proof_structure_comparison", "highest"),
                _pass("logical_dependency_graph_comparison", "high"),
                _pass("surface_text_comparison", "medium"),
                _pass("proof_ai_detection", "elevated"),
            ],
            calibration=[
                "flag only when structural and surface text similarity both exceed threshold",
                "surface canonical proof matches without implying wrongdoing",
                "use the most conservative flagging policy",
            ],
            evidence_surfaces=[
                "logical_structure_comparison",
                "prose_similarity_view",
                "canonical_proof_match",
            ],
            edge_case_policies=[
                "compare within proof approach when multiple valid approaches exist",
                "detect partial proof copying even with length imbalance",
            ],
            pipelines=["text", "ai_detection"],
        ),
        AssignmentMode(
            mode_id="research_report_essay",
            version="1.0.0",
            name="Research Report & Essay",
            category="text",
            access="standard",
            context="Reports and essays with direct-copy, paraphrase, AI, and humanizer risk.",
            preprocessing=[
                "citation_reference_secondary_signal",
                "proper_quote_detection_and_exclusion",
                "section_structure_identification",
                "linguistic_unicode_normalization",
            ],
            required_inputs=["ai_policy_optional", "field_optional"],
            detection_passes=[
                _pass("semantic_paraphrase_detection", "highest"),
                _pass("per_section_ai_generation_detection", "highest"),
                _pass("humanizer_detection", "high"),
                _pass("argument_structure_comparison", "medium"),
                _pass("cross_semester_self_plagiarism", "high"),
                _pass("academic_database_matching", "high_external"),
            ],
            calibration=[
                "report text, AI, and humanizer scores separately",
                "use passage-level AI confidence bands",
                "surface AI calibration date in reports",
                "document CS-writing calibration scope",
            ],
            evidence_surfaces=[
                "document_summary_by_signal",
                "annotated_similarity_document",
                "ai_heatmap_document",
                "academic_source_citation_match",
            ],
            edge_case_policies=[
                "support AI-permitted-with-disclosure setting",
                "show ESL caution note for borderline AI results",
                "respect group assignment configuration",
            ],
            warnings=[
                "AI detection is probabilistic and requires manual review for borderline cases.",
                "AI detection accuracy may vary for submissions not written by native English speakers.",
            ],
            pipelines=["text", "ai_detection", "external_sources"],
        ),
        AssignmentMode(
            mode_id="exam_mode",
            version="1.0.0",
            name="Exam Mode",
            category="overlay",
            access="standard_overlay",
            context="Time-aware overlay applied on top of another assignment mode.",
            preprocessing=[
                "submission_timestamp_verification",
                "exam_window_validation",
                "sequential_submission_detection",
            ],
            required_inputs=["base_mode_required", "exam_window_required"],
            detection_passes=[
                _pass("time_adjusted_thresholding", "overlay"),
                _pass("communication_pattern_cluster_analysis", "supplementary"),
                _pass("identical_error_detection", "high"),
            ],
            calibration=[
                "keep base-mode engine weights",
                "use stricter thresholds during exam window",
                "interpret temporal proximity as evidence, not proof",
            ],
            evidence_surfaces=[
                "submission_timeline_visualization",
                "flagged_pair_connectors",
            ],
            edge_case_policies=[
                "late submissions are integrity flags separate from similarity",
                "cluster flags are separate from pairwise flags",
            ],
            overlay=True,
            base_mode_required=True,
        ),
        AssignmentMode(
            mode_id="custom",
            version="1.0.0",
            name="Custom",
            category="advanced",
            access="advanced",
            context="Power-user mode for unusual assignments and unvalidated configurations.",
            preprocessing=[
                "professor_selected_engine_set",
                "custom_suppression_list_upload",
                "custom_threshold_zones",
                "custom_external_source_settings",
                "custom_ai_detection_sensitivity",
            ],
            required_inputs=["explicit_advanced_opt_in"],
            detection_passes=[_pass("professor_configured_pipeline", "custom")],
            calibration=[
                "require weights to sum to 100 percent",
                "show benchmark false-positive estimates beside thresholds",
                "stamp reports with custom-mode warning",
            ],
            evidence_surfaces=[
                "custom_configuration_summary",
                "persistent_unvalidated_configuration_warning",
                "exportable_importable_configuration",
            ],
            edge_case_policies=[
                "do not present custom mode as a peer to validated standard modes",
                "collect successful custom configs for future preset promotion",
            ],
            warnings=[
                "This analysis used a custom configuration that has not been validated against standardized benchmarks. Results should be interpreted with additional caution."
            ],
        ),
    ]
    return {mode.mode_id: mode for mode in modes}


def assignment_modes_payload(include_advanced: bool = True) -> Dict[str, Any]:
    """Return the mode catalog and shared cross-mode decisions."""
    modes = [
        mode.to_dict()
        for mode in get_assignment_modes().values()
        if include_advanced or mode.access != "advanced"
    ]
    return {
        "catalog_version": MODE_CATALOG_VERSION,
        "default_mode_id": DEFAULT_ASSIGNMENT_MODE_ID,
        "universal_preprocessing": universal_preprocessing_policy().to_dict(),
        "modes": modes,
        "cross_mode_policy": {
            "mode_versioning": "Every report stores mode ID and version.",
            "performance_dashboard": (
                "Precision and recall are tracked per mode for internal calibration."
            ),
            "professor_feedback_loop": (
                "Result feedback supports confirmed plagiarism, false positive, and uncertain."
            ),
            "recommendation_engine_ready": (
                "Assignment metadata should support future automatic mode recommendations."
            ),
        },
    }


def get_assignment_mode(mode_id: Optional[str]) -> AssignmentMode:
    """Return a mode by ID, falling back to the default mode."""
    modes = get_assignment_modes()
    if mode_id and mode_id in modes:
        return modes[mode_id]
    return modes[DEFAULT_ASSIGNMENT_MODE_ID]


def recommend_assignment_mode(
    assignment_name: str = "",
    course_name: str = "",
    filenames: Optional[List[str]] = None,
    content_samples: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Suggest the most likely assignment mode from metadata and content hints."""
    filenames = filenames or []
    content_samples = content_samples or []
    haystack = " ".join(
        [assignment_name, course_name, *filenames, *content_samples]
    ).lower()
    extensions = {
        f".{name.lower().rsplit('.', 1)[-1]}" for name in filenames if "." in name
    }

    scores = {
        DEFAULT_ASSIGNMENT_MODE_ID: 1.0,
        "data_structures_algorithms": 0.0,
        "systems_programming": 0.0,
        "database_sql": 0.0,
        "software_engineering_large_project": 0.0,
        "ml_data_science": 0.0,
        "web_development": 0.0,
        "theory_proofs": 0.0,
        "research_report_essay": 0.0,
    }
    reasons: Dict[str, List[str]] = {mode_id: [] for mode_id in scores}

    _score_keywords(
        haystack,
        scores,
        reasons,
        "data_structures_algorithms",
        [
            "tree",
            "graph",
            "heap",
            "hash",
            "sort",
            "search",
            "dynamic programming",
            "algorithm",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "systems_programming",
        [
            "malloc",
            "shell",
            "socket",
            "pthread",
            "kernel",
            "fork",
            "exec",
            "allocator",
            "posix",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "database_sql",
        [
            "sql",
            "select",
            "join",
            "schema",
            "database",
            "query",
            "trigger",
            "stored procedure",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "software_engineering_large_project",
        [
            "spring",
            "django",
            "express",
            "api",
            "microservice",
            "project",
            "group",
            "software engineering",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "ml_data_science",
        [
            "notebook",
            "jupyter",
            "pandas",
            "sklearn",
            "tensorflow",
            "torch",
            "model",
            "kaggle",
            "dataset",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "web_development",
        [
            "html",
            "css",
            "react",
            "next.js",
            "vue",
            "angular",
            "frontend",
            "website",
            "web app",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "theory_proofs",
        [
            "proof",
            "theorem",
            "lemma",
            "induction",
            "contradiction",
            "automata",
            "complexity theory",
        ],
    )
    _score_keywords(
        haystack,
        scores,
        reasons,
        "research_report_essay",
        [
            "essay",
            "report",
            "research",
            "paper",
            "abstract",
            "bibliography",
            "references",
            "literature",
        ],
    )

    extension_rules = {
        "database_sql": {".sql"},
        "ml_data_science": {".ipynb", ".rmd"},
        "web_development": {".html", ".css", ".jsx", ".tsx", ".vue"},
        "research_report_essay": {".md", ".txt", ".docx", ".pdf"},
        "software_engineering_large_project": {
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".gradle",
        },
    }
    for mode_id, mode_extensions in extension_rules.items():
        matched = sorted(extensions.intersection(mode_extensions))
        if matched:
            scores[mode_id] += 2.0
            reasons[mode_id].append(f"matched file types: {', '.join(matched)}")

    if len(extensions) >= 4:
        scores["software_engineering_large_project"] += 1.5
        reasons["software_engineering_large_project"].append(
            "multiple languages or project file types"
        )

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    mode_id, score = ranked[0]
    mode = get_assignment_mode(mode_id)
    confidence = min(0.95, max(0.35, score / max(3.0, score + ranked[1][1])))

    return {
        "recommended_mode_id": mode.mode_id,
        "recommended_mode_name": mode.name,
        "confidence": round(confidence, 2),
        "reasons": reasons.get(mode.mode_id)
        or ["default mode for general programming checks"],
        "alternatives": [
            {
                "mode_id": alt_id,
                "mode_name": get_assignment_mode(alt_id).name,
                "score": round(alt_score, 2),
                "reasons": reasons.get(alt_id, [])[:2],
            }
            for alt_id, alt_score in ranked[1:4]
            if alt_score > 0
        ],
    }


def _pass(name: str, weight: str) -> Dict[str, str]:
    """Build a compact detection-pass declaration."""
    return {"name": name, "weight": weight}


def _score_keywords(
    haystack: str,
    scores: Dict[str, float],
    reasons: Dict[str, List[str]],
    mode_id: str,
    keywords: List[str],
) -> None:
    """Increase a mode score for matching assignment/content keywords."""
    matched = [keyword for keyword in keywords if keyword in haystack]
    if not matched:
        return
    scores[mode_id] += float(len(matched))
    reasons[mode_id].append(f"matched keywords: {', '.join(matched[:4])}")
