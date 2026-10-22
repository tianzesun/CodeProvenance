"""A failing Dolos CLI must explain itself, not point at logs nobody kept."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.backend.benchmark.adapters.dolos_adapter import DolosBenchmarkEngine


def _fake_cli(tool_dir: Path, body: str) -> Path:
    """Write an executable stand-in for the Dolos CLI and return the tool dir."""
    tool_dir.mkdir(parents=True, exist_ok=True)
    cli = tool_dir / "dolos"
    cli.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    cli.chmod(0o755)
    return tool_dir


def _engine(tool_dir: Path) -> DolosBenchmarkEngine:
    """Return an adapter pinned to *tool_dir* instead of the bundled binaries."""
    engine = DolosBenchmarkEngine()
    engine.TOOL_DIRS = (tool_dir,)
    return engine


def test_failure_message_carries_the_tool_output(tmp_path) -> None:
    """The exit code alone was reported; the reason is what a host needs."""
    tool_dir = _fake_cli(
        tmp_path / "dolos-cli",
        'if [[ "${1:-}" == "--help" ]]; then echo "plagiarism --output-format"; exit 0; fi\n'
        'echo "Error: dolos requires Node.js >= 18 (found v14.21.3)"\n'
        "exit 1\n",
    )

    with pytest.raises(RuntimeError) as excinfo:
        _engine(tool_dir).run_batch({"a.py": "x = 1"}, [("a.py", "a.py")])

    message = str(excinfo.value)
    assert "exited with code 1" in message
    assert "Node.js >= 18" in message
    assert tool_dir.name in message


def test_failure_message_says_so_when_the_tool_prints_nothing(tmp_path) -> None:
    """An empty failure is still distinguishable from a missing binary."""
    tool_dir = _fake_cli(
        tmp_path / "dolos-cli",
        'if [[ "${1:-}" == "--help" ]]; then echo "plagiarism --output-format"; exit 0; fi\n'
        "exit 3\n",
    )

    with pytest.raises(RuntimeError) as excinfo:
        _engine(tool_dir).run_batch({"a.py": "x = 1"}, [("a.py", "a.py")])

    assert "exited with code 3" in str(excinfo.value)
    assert "printed no output" in str(excinfo.value)


def test_a_missing_cli_is_not_an_error(tmp_path) -> None:
    """No binary means unavailable, which the caller reports as such."""
    engine = DolosBenchmarkEngine()
    engine.TOOL_DIRS = (tmp_path / "nowhere",)
    assert engine.run_batch({"a.py": "x = 1"}, [("a.py", "a.py")]) == {"pairs": []}


def test_abi_mismatch_gets_a_remediation_hint(tmp_path) -> None:
    """The native-parser ABI error is the one a fresh host actually hits."""
    tool_dir = _fake_cli(
        tmp_path / "dolos-cli",
        'if [[ "${1:-}" == "--help" ]]; then echo "plagiarism --output-format"; exit 0; fi\n'
        'echo "[error] was compiled against a different Node.js version using"\n'
        'echo "NODE_MODULE_VERSION 141. This version of Node.js requires NODE_MODULE_VERSION 127."\n'
        "exit 1\n",
    )

    with pytest.raises(RuntimeError) as excinfo:
        _engine(tool_dir).run_batch({"a.py": "x = 1"}, [("a.py", "a.py")])

    message = str(excinfo.value)
    assert "NODE_MODULE_VERSION 127" in message
    assert "npm rebuild" in message
    assert "tools/external/dolos-cli/node/bin" in message


def test_a_node_bin_directory_is_preferred(tmp_path) -> None:
    """A pinned runtime next to the CLI wins over whatever PATH has."""
    tool_dir = _fake_cli(
        tmp_path / "dolos-cli" / "node_modules" / ".bin",
        'if [[ "${1:-}" == "--help" ]]; then echo "plagiarism --output-format"; exit 0; fi\n'
        'echo "node: $(command -v node)"\n'
        "exit 1\n",
    )
    node_bin = tmp_path / "dolos-cli" / "node" / "bin"
    node_bin.mkdir(parents=True)
    node = node_bin / "node"
    node.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    node.chmod(0o755)

    with pytest.raises(RuntimeError) as excinfo:
        _engine(tool_dir).run_batch({"a.py": "x = 1"}, [("a.py", "a.py")])

    assert f"node: {node}" in str(excinfo.value)


def test_the_legacy_node20_directory_still_works(tmp_path) -> None:
    """Earlier checkouts put the runtime in ``node20/bin``; keep honouring it."""
    tool_dir = _fake_cli(
        tmp_path / "dolos-cli" / "node_modules" / ".bin",
        'if [[ "${1:-}" == "--help" ]]; then echo "plagiarism --output-format"; exit 0; fi\n'
        'echo "node: $(command -v node)"\n'
        "exit 1\n",
    )
    node_bin = tmp_path / "dolos-cli" / "node20" / "bin"
    node_bin.mkdir(parents=True)
    node = node_bin / "node"
    node.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    node.chmod(0o755)

    with pytest.raises(RuntimeError) as excinfo:
        _engine(tool_dir).run_batch({"a.py": "x = 1"}, [("a.py", "a.py")])

    assert f"node: {node}" in str(excinfo.value)
