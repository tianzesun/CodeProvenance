"""Tests for JPlag benchmark adapter error reporting."""

from pathlib import Path

import pytest

from src.backend.benchmark.adapters.jplag_adapter import JPlagAdapter


class _FakeStdout:
    """Iterable stdout replacement for a failed JPlag process."""

    def __iter__(self):
        """Yield representative JPlag output lines."""
        yield "Loading Submissions 100%\n"
        yield "Error: invalid value for option '--language'\n"


class _FakeProcess:
    """Process replacement for a failed JPlag command."""

    stdout = _FakeStdout()
    returncode = 1

    def wait(self) -> int:
        """Return the fake process exit code."""
        return self.returncode


class _RemovedSubmissionStdout:
    """Iterable stdout replacement for recoverable JPlag parser removals."""

    def __iter__(self):
        """Yield JPlag removed-submission output lines."""
        yield "2026-05-06 [ERROR] SubmissionSet - ERROR -> Submission sub092 removed\n"
        yield "2026-05-06 [ERROR] SubmissionSet - ERROR -> Submission sub095 removed\n"


class _RemovedSubmissionProcess:
    """Process replacement for JPlag parse removals."""

    stdout = _RemovedSubmissionStdout()
    returncode = 1

    def wait(self) -> int:
        """Return the fake process exit code."""
        return self.returncode


def test_jplag_failure_includes_captured_output(monkeypatch) -> None:
    """JPlag failures should include useful CLI output in the raised error."""
    commands = []

    def fake_popen(*args, **kwargs):
        """Return a failed fake JPlag process."""
        commands.append(args[0])
        return _FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    adapter = JPlagAdapter()

    with pytest.raises(RuntimeError) as exc_info:
        adapter._run_group(
            Path("/tmp/jplag.jar"),
            "python3",
            {"a.py": "print(1)", "b.py": "print(2)"},
        )

    error = str(exc_info.value)
    assert "JPlag exited with code 1" in error
    assert "invalid value for option" in error
    assert "--cluster-skip" in commands[0]


def test_jplag_removed_submissions_are_recoverable(monkeypatch) -> None:
    """JPlag parser removals should not fail the whole benchmark tool."""

    def fake_popen(*args, **kwargs):
        """Return a fake JPlag process with removed submissions."""
        return _RemovedSubmissionProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    adapter = JPlagAdapter()

    result = adapter._run_group(
        Path("/tmp/jplag.jar"),
        "python3",
        {"a.py": "print(1)", "b.py": "print(2)"},
    )

    assert result == {}


def test_jplag_removed_submissions_fall_back_to_text_mode(monkeypatch) -> None:
    """JPlag parser removals should retry with text mode before returning zeros."""
    languages = []
    commands = []

    class SuccessfulTextProcess:
        """Process replacement for a successful text-mode JPlag run."""

        stdout = []
        returncode = 0

        def wait(self) -> int:
            """Return the fake process exit code."""
            return self.returncode

    def fake_popen(command, **kwargs):
        """Fail language mode once, then write a text-mode CSV."""
        commands.append(command)
        language = command[command.index("-l") + 1]
        languages.append(language)
        if language != "text":
            return _RemovedSubmissionProcess()

        result_root = Path(command[command.index("-r") + 1])
        result_root.mkdir(parents=True, exist_ok=True)
        (result_root / "results.csv").write_text(
            "submissionName1,submissionName2,averageSimilarity,maxSimilarity\n"
            "sub000,sub001,0.73,0.73\n",
            encoding="utf-8",
        )
        return SuccessfulTextProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    adapter = JPlagAdapter()

    result = adapter._run_group(
        Path("/tmp/jplag.jar"),
        "java",
        {"a.java": "class A {}", "b.java": "class B {}"},
    )

    assert languages == ["java", "text"]
    assert commands[1][commands[1].index("-p") + 1] == "java"
    assert result == {"a.java::b.java": 0.73}
