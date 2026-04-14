from src.backend.backend.api import server


def _tool_by_id(tools, tool_id):
    return next(tool for tool in tools if tool["id"] == tool_id)


def test_list_benchmark_tools_reflects_repo_inventory(tmp_path, monkeypatch):
    for name in [
        "JPlag",
        "NiCad-6.2",
        "dolos",
        "dolos-2.9.3",
        "STRANGE",
        "gptzero",
    ]:
        (tmp_path / name).mkdir()

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


def test_run_competitor_tool_supports_expanded_repo_tools():
    submissions = {
        "a.py": "def add(a, b):\n    return a + b\n",
        "b.py": "def sum_numbers(x, y):\n    return x + y\n",
    }
    pairs = [("a.py", "b.py")]

    for tool_id in ["moss", "jplag", "dolos", "nicad", "pmd", "sherlock", "sim"]:
        result = server._run_competitor_tool(tool_id, submissions, pairs)
        assert result is not None, tool_id
        assert "pairs" in result, tool_id
        assert len(result["pairs"]) == 1, tool_id
        assert 0.0 <= result["pairs"][0]["score"] <= 1.0, tool_id
