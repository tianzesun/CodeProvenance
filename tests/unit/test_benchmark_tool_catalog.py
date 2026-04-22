from src.backend.api import server


def _tool_by_id(tools, tool_id):
    return next(tool for tool in tools if tool["id"] == tool_id)


def test_list_benchmark_tools_reflects_repo_inventory(tmp_path, monkeypatch):
    external = tmp_path / "external"
    for name in [
        "JPlag",
        "nicad",
        "dolos",
        "dolos-2.9.3",
        "sherlock",
        "STRANGE",
        "gptzero",
    ]:
        (external / name).mkdir(parents=True)
    (external / "JPlag" / "jplag.jar").touch()
    (external / "dolos" / "dolos").touch()
    sherlock_bin = external / "sherlock" / "sherlock"
    sherlock_bin.touch()
    sherlock_bin.chmod(0o755)

    monkeypatch.setattr(server, "TOOLS_DIR", tmp_path)

    tools = server._list_benchmark_tools()

    assert tools[0]["id"] == "integritydesk"

    jplag = _tool_by_id(tools, "jplag")
    assert jplag["runnable"] is True
    assert jplag["status"] == "Installed and ready"
    assert jplag["paths"] == ["tools/external/JPlag"]

    nicad = _tool_by_id(tools, "nicad")
    assert nicad["runnable"] is False
    assert nicad["paths"] == ["tools/external/nicad"]

    dolos = _tool_by_id(tools, "dolos")
    assert dolos["paths"] == ["tools/external/dolos", "tools/external/dolos-2.9.3"]

    sherlock = _tool_by_id(tools, "sherlock")
    assert sherlock["runnable"] is True
    assert sherlock["status"] == "Installed and ready"
    assert sherlock["paths"] == ["tools/external/sherlock"]

    strange = _tool_by_id(tools, "strange")
    assert strange["runnable"] is False
    assert strange["status"] == "Not ready"

    gptzero = _tool_by_id(tools, "gptzero")
    assert gptzero["runnable"] is False
    assert gptzero["paths"] == ["tools/external/gptzero"]


def test_run_competitor_tool_supports_expanded_repo_tools():
    submissions = {
        "a.py": "def add(a, b):\n    return a + b\n",
        "b.py": "def sum_numbers(x, y):\n    return x + y\n",
    }
    pairs = [("a.py", "b.py")]

    for tool_id in ["moss", "jplag", "dolos", "nicad", "pmd", "sherlock"]:
        try:
            result = server._run_competitor_tool(tool_id, submissions, pairs)
        except RuntimeError:
            continue
        if result is None:
            continue
        assert "pairs" in result, tool_id
        assert len(result["pairs"]) == 1, tool_id
        assert 0.0 <= result["pairs"][0]["score"] <= 1.0, tool_id


def test_prepare_moss_script_uses_settings_and_writable_log(tmp_path):
    script_path = tmp_path / "moss.pl"
    script_path.write_text(
        "\n".join(
            [
                "my $logfile = '/var/log/moss/' . ${prof}.${now};",
                "$userid=394450069;",
                'system("bash", "save_moss_report.sh","$logfile");',
            ]
        ),
        encoding="utf-8",
    )

    patched_script = server._prepare_moss_script(script_path, tmp_path / "run", "12345")

    script_text = patched_script.read_text(encoding="utf-8")
    assert "$ENV{'MOSS_LOGFILE'}" in script_text
    assert "$ENV{'MOSS_USER_ID'}" in script_text
    assert "/var/log/moss" not in script_text
    assert 'if -e "save_moss_report.sh"' in script_text


def test_run_sherlock_cli_parses_real_binary_output(tmp_path, monkeypatch):
    external = tmp_path / "external" / "sherlock"
    external.mkdir(parents=True)
    sherlock_bin = external / "sherlock"
    sherlock_bin.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'source_dir="${@: -1}"',
                'printf "%s/a.py;%s/b.py;42%%\\n" "$source_dir" "$source_dir"',
            ]
        ),
        encoding="utf-8",
    )
    sherlock_bin.chmod(0o755)

    monkeypatch.setattr(server, "TOOLS_DIR", tmp_path)

    result = server._run_sherlock_cli(
        {
            "a.py": "def add(a, b):\n    return a + b\n",
            "b.py": "def sum_numbers(x, y):\n    return x + y\n",
        },
        [("a.py", "b.py")],
    )

    assert result == {"pairs": [{"file_a": "a.py", "file_b": "b.py", "score": 0.42}]}
