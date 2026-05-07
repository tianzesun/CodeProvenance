"""Tests for external benchmark tool progress callback dispatch."""

from pathlib import Path
from types import SimpleNamespace

from src.backend.benchmark.runners import external_tool_runner
from src.backend.benchmark.runners.external_tool_runner import ExternalToolRunner


def test_external_tool_runner_forwards_progress_callback(monkeypatch) -> None:
    """Ensure adapter wrappers accept the runner's progress callback keyword."""
    calls = []

    def fake_batch(submissions, pairs, progress_cb=None):
        """Record the callback supplied by the external tool runner."""
        calls.append(progress_cb)
        return {"pairs": []}

    monkeypatch.setattr(external_tool_runner, "run_dolos_batch", fake_batch)
    runner = ExternalToolRunner()

    def callback(line) -> None:
        """Ignore a streamed progress line."""
        _ = line

    assert runner.run_tool("dolos", {"a.py": "print(1)"}, [], progress_cb=callback) == {
        "pairs": []
    }
    assert calls == [callback]


def test_external_tool_runner_forwards_moss_user_id(monkeypatch) -> None:
    """Ensure the runner passes its configured MOSS credential to the adapter."""
    calls = []

    def fake_batch(submissions, pairs, moss_user_id=None, progress_cb=None):
        """Record MOSS-specific dispatch arguments."""
        calls.append((moss_user_id, progress_cb))
        return {"pairs": []}

    def callback(line) -> None:
        """Ignore a streamed progress line."""
        _ = line

    monkeypatch.setattr(external_tool_runner, "run_moss_batch", fake_batch)
    runner = ExternalToolRunner(moss_user_id="12345")

    assert runner.run_tool("moss", {"a.py": "print(1)"}, [], progress_cb=callback) == {
        "pairs": []
    }
    assert calls == [("12345", callback)]


def test_unavailable_internal_tools_accept_progress_callback(monkeypatch) -> None:
    """Ensure built-in external-tool runners share the same callback signature."""
    monkeypatch.setattr(ExternalToolRunner, "_find_nicad_executable", lambda self: None)
    monkeypatch.setattr(ExternalToolRunner, "_find_txl_executable", lambda self: None)
    monkeypatch.setattr(
        ExternalToolRunner, "_find_sherlock_executable", lambda self: None
    )
    runner = ExternalToolRunner()

    def progress_cb(line) -> None:
        """Ignore a streamed progress line."""
        _ = line

    assert (
        runner.run_tool("nicad", {"a.py": "print(1)"}, [], progress_cb=progress_cb)
        is None
    )
    assert (
        runner.run_tool("sherlock", {"a.py": "print(1)"}, [], progress_cb=progress_cb)
        is None
    )


def test_nicad_resolves_relative_report_dir(monkeypatch, tmp_path) -> None:
    """Ensure NiCad reports are parsed relative to the NiCad install directory."""
    nicad_root = tmp_path / "tools" / "external" / "nicad"
    nicad_bin = nicad_root / "nicad6"
    txl_bin = nicad_root / "lib" / "nicad" / "txl"
    nicad_bin.parent.mkdir(parents=True)
    txl_bin.parent.mkdir(parents=True)
    nicad_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    txl_bin.write_text("#!/bin/sh\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        """Create a relative NiCad report inside the command cwd."""
        source_root = Path(command[3])
        assert source_root.name != "subs"
        report_dir = Path(kwargs["cwd"]) / "nicadclones" / source_root.name
        report_dir.mkdir(parents=True)
        (report_dir / "report-classes.xml").write_text(
            """
<clones>
<class classid="1" nclones="2" nlines="12" similarity="100">
<source file="sub000/a.py" startline="1" endline="12" pcid="1" />
<source file="sub001/b.py" startline="1" endline="12" pcid="2" />
</class>
</clones>
""".strip(),
            encoding="utf-8",
        )
        (report_dir / "report-classes-withsource.xml").write_text(
            "<clones><class><source>\x08</source></class></clones>",
            encoding="utf-8",
        )
        return SimpleNamespace(
            returncode=0,
            stdout=f"Results in nicadclones/{source_root.name}/\n",
            stderr="",
        )

    monkeypatch.setattr(external_tool_runner.subprocess, "run", fake_run)
    runner = ExternalToolRunner(tools_dir=tmp_path / "tools")

    result = runner.run_tool(
        "nicad",
        {"a.py": "print(1)", "b.py": "print(1)"},
        [("a.py", "b.py")],
    )

    assert result == {"pairs": [{"file_a": "a.py", "file_b": "b.py", "score": 1.0}]}


def test_nicad_parser_recovers_from_malformed_xml(tmp_path) -> None:
    """Ensure malformed NiCad XML source bodies do not fail the benchmark."""
    xml_path = tmp_path / "bad-classes.xml"
    xml_path.write_text(
        """
<clones>
<class classid="1" nclones="2" nlines="12" similarity="85">
<source file="sub000/a.py" startline="1" endline="12" pcid="1">
\x08
</source>
<source file="sub001/b.py" startline="1" endline="12" pcid="2"></source>
</class>
</clones>
""".strip(),
        encoding="utf-8",
    )
    runner = ExternalToolRunner()

    result = runner._parse_nicad_xml(
        xml_path,
        {"a.py": "print(1)", "b.py": "print(1)"},
        {
            "sub000": {"filename": "a.py", "path": "/tmp/sub000/a.py"},
            "sub001": {"filename": "b.py", "path": "/tmp/sub001/b.py"},
        },
    )

    assert result == {"a.py::b.py": 0.85}
