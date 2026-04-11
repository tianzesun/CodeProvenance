from src.api import server


def _tool_by_id(tools, tool_id):
    return next(tool for tool in tools if tool["id"] == tool_id)


def test_list_benchmark_tools_reflects_repo_inventory(tmp_path, monkeypatch):
    (tmp_path / "JPlag").mkdir()
    (tmp_path / "JPlag" / "jplag.jar").write_text("jar")

    (tmp_path / "NiCad-6.2").mkdir()
    (tmp_path / "NiCad-6.2" / "nicad6").write_text("#!/bin/sh\n")
    (tmp_path / "freetxl" / "current" / "bin").mkdir(parents=True)
    (tmp_path / "freetxl" / "current" / "bin" / "txl").write_text("#!/bin/sh\n")

    (tmp_path / "dolos").mkdir()
    (tmp_path / "dolos-2.9.3").mkdir()
    (tmp_path / "dolos-cli" / "node_modules" / ".bin").mkdir(parents=True)
    (tmp_path / "dolos-cli" / "node_modules" / ".bin" / "dolos").write_text("#!/bin/sh\n")
    (tmp_path / "dolos-cli" / "node20" / "bin").mkdir(parents=True)
    (tmp_path / "dolos-cli" / "node20" / "bin" / "node").write_text("#!/bin/sh\n")

    (tmp_path / "STRANGE").mkdir()
    (tmp_path / "gptzero").mkdir()

    monkeypatch.setattr(server, "TOOLS_DIR", tmp_path)

    tools = server._list_benchmark_tools()

    assert tools[0]["id"] == "integritydesk"

    jplag = _tool_by_id(tools, "jplag")
    assert jplag["runnable"] is True
    assert jplag["status"] == "Installed and ready"
    assert jplag["paths"] == ["tools/JPlag"]

    nicad = _tool_by_id(tools, "nicad")
    assert nicad["runnable"] is True
    assert nicad["paths"] == ["tools/NiCad-6.2"]

    dolos = _tool_by_id(tools, "dolos")
    assert dolos["paths"] == ["tools/dolos", "tools/dolos-2.9.3"]

    strange = _tool_by_id(tools, "strange")
    assert strange["runnable"] is False
    assert strange["status"] == "Installed only"

    gptzero = _tool_by_id(tools, "gptzero")
    assert gptzero["runnable"] is False
    assert gptzero["paths"] == ["tools/gptzero"]


def test_list_runnable_benchmark_tools_only_returns_verified_tools(tmp_path, monkeypatch):
    (tmp_path / "JPlag").mkdir()
    (tmp_path / "JPlag" / "jplag.jar").write_text("jar")
    monkeypatch.setattr(server, "TOOLS_DIR", tmp_path)

    runnable = server._list_runnable_benchmark_tools()

    runnable_ids = {tool["id"] for tool in runnable}
    assert "integritydesk" in runnable_ids
    assert "jplag" in runnable_ids
    assert "moss" not in runnable_ids
    assert "sherlock" not in runnable_ids


def test_run_competitor_tool_only_dispatches_real_cli_integrations(monkeypatch):
    dispatch_calls = []

    for tool_id in ["moss", "jplag", "dolos", "nicad", "pmd", "ac"]:
        monkeypatch.setattr(
            server,
            f"_run_{tool_id}_cli",
            lambda submissions, pairs, current=tool_id: dispatch_calls.append(current) or {"pairs": [{"file_a": "a.py", "file_b": "b.py", "score": 0.5}]},
        )

    submissions = {
        "a.py": "def add(a, b):\n    return a + b\n",
        "b.py": "def sum_numbers(x, y):\n    return x + y\n",
    }
    pairs = [("a.py", "b.py")]

    for tool_id in ["moss", "jplag", "dolos", "nicad", "pmd", "ac"]:
        result = server._run_competitor_tool(tool_id, submissions, pairs)
        assert result == {"pairs": [{"file_a": "a.py", "file_b": "b.py", "score": 0.5}]}

    assert dispatch_calls == ["moss", "jplag", "dolos", "nicad", "pmd", "ac"]
    assert server._run_competitor_tool("sherlock", submissions, pairs) is None
    assert server._run_competitor_tool("sim", submissions, pairs) is None
