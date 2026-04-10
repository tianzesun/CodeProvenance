"""Tests for execution tool availability reporting."""

from src.engines.execution.execution_engine import (
    DolosRunner,
    ExecutionEngine,
    JPlagRunner,
    MossRunner,
    NiCadRunner,
)


def test_dolos_runner_unavailable_without_binary(monkeypatch) -> None:
    monkeypatch.setattr("src.engines.execution.execution_engine.shutil.which", lambda name: None)
    assert DolosRunner().is_available() is False


def test_jplag_runner_unavailable_without_binary_or_docker(monkeypatch) -> None:
    monkeypatch.setattr("src.engines.execution.execution_engine.shutil.which", lambda name: None)
    runner = JPlagRunner(use_docker=False)
    assert runner.is_available() is False


def test_nicad_runner_unavailable_without_binary(monkeypatch) -> None:
    monkeypatch.setattr("src.engines.execution.execution_engine.shutil.which", lambda name: None)
    assert NiCadRunner().is_available() is False


def test_moss_runner_requires_script_key_and_perl(monkeypatch, tmp_path) -> None:
    script = tmp_path / "moss.pl"
    script.write_text("print 'ok';")
    monkeypatch.setattr(
        "src.engines.execution.execution_engine.shutil.which",
        lambda name: "/usr/bin/perl" if name == "perl" else None,
    )
    assert MossRunner(moss_user_id="123", moss_script=script).is_available() is True
    assert MossRunner(moss_user_id=None, moss_script=script).is_available() is False


def test_execution_engine_available_tools_filters_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("src.engines.execution.execution_engine.shutil.which", lambda name: None)
    engine = ExecutionEngine(use_sandbox=False)
    assert engine.available_tools() == []
