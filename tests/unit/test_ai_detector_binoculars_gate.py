"""An uncalibrated Binoculars pair must abstain from fusion entirely.

The default Qwen2.5-0.5B pair measured at chance on AIGCodeSet (best
single-threshold split 62%, fully overlapping class distributions — see
scripts/probe-binoculars.py), so the orchestrator must not let it vote
with Falcon-fitted thresholds: it contributes no signal, never loads the
models, and the method reflects what actually fused.
"""

from src.backend.engines.ai import orchestrator as orch_module
from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

AI_CODE = (
    "def calculate_mean(values: list[float]) -> float:\n"
    '    """Return the arithmetic mean of the provided values."""\n'
    "    if not values:\n"
    '        raise ValueError("values must not be empty")\n'
    "    return sum(values) / len(values)\n"
)


class _StubDetector:
    """Stand-in detector that records whether it was asked to score."""

    def __init__(self, result: dict, model: str, performer: str) -> None:
        self.result = result
        self.model = model
        self.performer = performer
        self.calls = 0

    def analyze(self, code: str, language: str | None = None) -> dict:
        """Return the canned layer result and count the invocation."""
        self.calls += 1
        return self.result


def test_default_uncalibrated_pair_abstains(monkeypatch) -> None:
    """Uncalibrated pair: no signal, no method credit, no model load."""
    orchestrator = AIDetectionOrchestrator()
    stub = _StubDetector(
        result={
            "ai_probability": 0.99,
            "confidence": 0.9,
            "raw_score": 0.4,
            "label": "Most likely AI-generated",
            "available": True,
            "calibrated": False,
        },
        model="qwen/qwen2.5-0.5b",
        performer="qwen/qwen2.5-0.5b-instruct",
    )
    monkeypatch.setattr(orchestrator, "binoculars", stub)
    monkeypatch.setattr(orch_module, "is_calibrated", lambda *_args: False)

    result = orchestrator.analyze(AI_CODE)

    assert stub.calls == 0, "abstaining pair must not load/score"
    assert "binoculars" not in result["signals"]
    assert result["method"] != "binoculars"
    layer = result["layers"]["binoculars"]
    assert layer["available"] is False
    assert layer["calibrated"] is False


def test_calibrated_pair_contributes_to_fusion(monkeypatch) -> None:
    """A calibrated pair scores, fuses, and is reported as the method."""
    orchestrator = AIDetectionOrchestrator()
    stub = _StubDetector(
        result={
            "ai_probability": 0.95,
            "confidence": 0.9,
            "raw_score": 0.6,
            "label": "Most likely AI-generated",
            "available": True,
            "calibrated": True,
        },
        model="tiiuae/falcon-7b",
        performer="tiiuae/falcon-7b-instruct",
    )
    monkeypatch.setattr(orchestrator, "binoculars", stub)
    monkeypatch.setattr(orch_module, "is_calibrated", lambda *_args: True)

    result = orchestrator.analyze(AI_CODE)

    assert stub.calls == 1
    assert result["signals"]["binoculars"] == 0.95
    assert result["method"] == "binoculars"
    assert result["layers"]["binoculars"]["raw_score"] == 0.6
