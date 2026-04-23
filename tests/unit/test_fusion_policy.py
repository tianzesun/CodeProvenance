"""Tests for fusion normalization, presets, and weight governance."""

from __future__ import annotations

from src.backend.engines.scoring.fusion_engine import FusionEngine, load_engine_config
from src.backend.engines.scoring.fusion_policy import (
    default_score_normalizer,
    evaluate_weight_change_governance,
    get_fusion_presets,
)


def test_external_tool_scores_are_normalized_to_common_unit_scale() -> None:
    """External tool percentages must normalize before any weighted fusion."""
    normalizer = default_score_normalizer()

    assert normalizer.normalize("moss", 87) == 0.87
    assert normalizer.normalize("jplag", 0.42) == 0.42
    assert normalizer.normalize("dolos", 142) == 1.0
    assert normalizer.normalize("sherlock", -3) == 0.0
    assert normalizer.normalize("ast", 0.8) == 0.8


def test_normalize_many_preserves_engine_ids() -> None:
    """Batch normalization should keep per-engine contribution names intact."""
    normalized = default_score_normalizer().normalize_many(
        {"moss": 91, "jplag": 72.5, "semantic": 0.61}
    )

    assert normalized == {"moss": 0.91, "jplag": 0.725, "semantic": 0.61}


def test_assignment_presets_cover_required_modes_and_evidence() -> None:
    """Fusion presets must cover the four benchmark/use-case modes."""
    presets = get_fusion_presets()

    assert set(presets) == {
        "algorithm_data_structure",
        "open_ended_coding",
        "essay_report",
        "mixed_submission",
    }
    assert (
        "hard_negative_context" in presets["algorithm_data_structure"].evidence_surfaces
    )
    assert "ai_detection" in presets["essay_report"].evidence_surfaces
    assert presets["essay_report"].pipelines == ["text"]
    assert presets["mixed_submission"].pipelines == ["code", "text"]
    assert presets["mixed_submission"].present_results_separately is True
    assert (
        round(sum(presets["open_ended_coding"].normalized_weights().values()), 6) == 1.0
    )


def test_fusion_engine_exposes_assignment_presets() -> None:
    """The settings/API layer should be able to consume assignment presets."""
    presets = FusionEngine.get_assignment_presets()

    assert "algorithm_data_structure" in presets
    assert presets["mixed_submission"]["present_results_separately"] is True


def test_weight_governance_blocks_untested_default_changes() -> None:
    """Default weight changes require validation-set evidence before shipping."""
    result = evaluate_weight_change_governance(
        {"ast": 0.5, "token": 0.5},
        {"ast": 0.7, "token": 0.3},
    )

    assert result.allowed is False
    assert result.requires_validation is True
    assert result.changed_engines == ["ast", "token"]
    assert any("validation evidence" in warning for warning in result.warnings)


def test_weight_governance_allows_validated_weight_changes() -> None:
    """Validated default weight changes should pass governance checks."""
    result = evaluate_weight_change_governance(
        {"ast": 0.5, "token": 0.5},
        {"ast": 0.7, "token": 0.3},
        {
            "split": "validation",
            "validation_run_id": "bench-2026-04-23",
            "benchmark_dataset_id": "controlled_internal_v1",
            "metric_snapshot": {"plagdet": 0.44, "f1": 0.46},
        },
    )

    assert result.allowed is True
    assert result.warnings == []


def test_engine_config_includes_phase_two_policy_sections() -> None:
    """Engine config should publish normalization, presets, and governance sections."""
    config = load_engine_config()

    assert (
        config["score_normalization"]["common_scale"] == "similarity_probability_0_to_1"
    )
    assert len(config["fusion_presets"]) == 4
    assert config["weight_governance"]["required_split"] == "validation"
