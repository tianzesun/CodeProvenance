"""Dispatch tests for the bootstrap benchmark plugin."""

from typing import Any

import pytest

from src.backend.benchmark.runners import (
    core_runner,
    diagnostic_runner,
    full_runner,
    layer_runner,
)
from src.backend.bootstrap.plugins.benchmark import BenchmarkRunner

RUNNERS = {
    "full": (full_runner, "FullBenchmarkRunner"),
    "core": (core_runner, "CoreBenchmarkRunner"),
    "layer": (layer_runner, "ThreeLayerBenchmarkRunner"),
    "diagnostic": (diagnostic_runner, "DiagnosticBenchmarkRunner"),
}


@pytest.mark.parametrize("mode", sorted(RUNNERS))
def test_run_dispatches_to_runner_for_mode(
    mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each mode should construct its runner and return that runner's run()."""
    module, class_name = RUNNERS[mode]

    class FakeRunner:
        def run(self) -> dict[str, Any]:
            return {"runner": class_name}

    monkeypatch.setattr(module, class_name, FakeRunner)

    assert BenchmarkRunner().run(mode=mode) == {"runner": class_name}


def test_run_does_not_require_dataset_on_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runners are synthetic, so a missing data/<dataset> must not fail."""

    class FakeRunner:
        def run(self) -> dict[str, Any]:
            return {}

    monkeypatch.setattr(full_runner, "FullBenchmarkRunner", FakeRunner)

    assert BenchmarkRunner().run(dataset="no-such-dataset") == {}


def test_run_rejects_unknown_mode() -> None:
    """An unknown mode should list the valid ones."""
    with pytest.raises(ValueError, match="Available"):
        BenchmarkRunner().run(mode="bogus")
