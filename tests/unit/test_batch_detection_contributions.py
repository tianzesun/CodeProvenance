"""Pair results explain the score with the model that produced it."""

import json
from pathlib import Path

from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
)
from src.backend.engines.scoring.learned_fusion import (
    ARTIFACT_VERSION,
    DEFAULT_FEATURE_NAMES,
    LearnedFusionScorer,
)

CODE_A = (
    "def mean(values):\n"
    "    if not values:\n"
    "        return 0.0\n"
    "    total = 0.0\n"
    "    for value in values:\n"
    "        total += value\n"
    "    return total / len(values)\n"
)
CODE_B = CODE_A.replace("values", "items").replace("value", "item")


def _scorer(tmp_path: Path) -> LearnedFusionScorer:
    path = tmp_path / "model.json"
    path.write_text(
        json.dumps(
            {
                "version": ARTIFACT_VERSION,
                "feature_names": list(DEFAULT_FEATURE_NAMES),
                "coefficients": [-1.0, 0.0, 0.5, 0.0, 3.0, 0.0, 1.0],
                "intercept": -2.0,
                "metadata": {"trained_at": "2026-01-01T00:00:00"},
            }
        ),
        encoding="utf-8",
    )
    return LearnedFusionScorer(artifact_path=path)


def test_results_carry_the_learned_models_terms(tmp_path: Path) -> None:
    service = BatchDetectionService()
    service.learned_scorer = _scorer(tmp_path)

    (result,) = service.compare_all_pairs({"a.py": CODE_A, "b.py": CODE_B})

    assert set(result.contributions) == set(DEFAULT_FEATURE_NAMES)
    assert result.contributions["winnowing"] == round(
        3.0 * result.features["winnowing"], 6
    )
    assert result.contributions["ast"] <= 0.0


def test_results_fall_back_to_rule_based_contributions(tmp_path: Path) -> None:
    service = BatchDetectionService()
    service.learned_scorer = LearnedFusionScorer(artifact_path=tmp_path / "none.json")

    (result,) = service.compare_all_pairs({"a.py": CODE_A, "b.py": CODE_B})

    assert "winnowing" not in result.contributions
