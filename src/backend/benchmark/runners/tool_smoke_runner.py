# src/backend/benchmark/runners/tool_smoke_runner.py
"""
Tool smoke test runner.

Verifies that external benchmark tools are operational before full runs by:
- loading enabled tools from the registry,
- checking wrapper existence and executability,
- validating required runtimes,
- attempting a lightweight help/version command when safe,
- writing JSON results to tools/outputs/smoke/smoke_results.json.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

try:
    from tools.registry.tool_registry import ToolSpec, load_registry
except ModuleNotFoundError:
    # Fallback when repository root is not on PYTHONPATH.
    import importlib.util

    _REG_PATH = Path(__file__).resolve().parents[4] / "tools" / "registry" / "tool_registry.py"
    _SPEC = importlib.util.spec_from_file_location("tool_registry", _REG_PATH)
    if _SPEC is None or _SPEC.loader is None:
        raise
    _MOD = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_MOD)
    ToolSpec = _MOD.ToolSpec
    load_registry = _MOD.load_registry


logger = logging.getLogger(__name__)


@dataclass
class SmokeCheckResult:
    tool_name: str
    status: str  # PASS / FAIL
    wrapper_exists: bool = False
    wrapper_executable: bool = False
    tool_root_exists: bool = False
    runtime_ok: bool = False
    help_ok: bool = False
    fixture_run_ok: bool = False
    output_ok: bool = False
    notes: str = ""
    command: list[str] | None = None
    returncode: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolSmokeRunner:
    """
    Registry-driven smoke test runner for benchmark tools.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        registry_path: Optional[Path] = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.repo_root = repo_root or self._discover_repo_root()
        self.registry_path = registry_path or (self.repo_root / "tools" / "registry" / "tool_registry.yaml")
        self.timeout_seconds = timeout_seconds
        self.output_dir = self.repo_root / "tools" / "outputs" / "smoke"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.registry = load_registry(self.registry_path)

    def _discover_repo_root(self) -> Path:
        """
        Try to discover the repo root based on this file location:
        src/backend/benchmark/runners/tool_smoke_runner.py -> repo root is parents[4]
        """
        here = Path(__file__).resolve()
        return here.parents[4]

    def _check_runtime(self, runtime: str) -> bool:
        """
        Check if a required runtime exists in PATH.

        Special-case 'shell' as satisfied by bash/sh presence.
        """
        if runtime == "shell":
            return shutil.which("bash") is not None or shutil.which("sh") is not None
        return shutil.which(runtime) is not None

    def _all_runtimes_ok(self, tool: ToolSpec) -> tuple[bool, list[str]]:
        missing: list[str] = []
        for runtime in tool.runtime:
            if not self._check_runtime(runtime):
                missing.append(runtime)
        return (len(missing) == 0, missing)

    def _safe_probe_command(self, tool: ToolSpec) -> list[str] | None:
        """
        Return a lightweight command to probe the tool safely.

        The wrapper is always the entrypoint. For most tools, try '--help'.
        For MOSS, avoid contacting remote infrastructure; just syntax-check the Perl script
        behind the wrapper if possible, otherwise skip active probing.
        """
        wrapper = str(tool.wrapper_path)

        if tool.name == "moss":
            perl = shutil.which("perl")
            moss_pl = self.repo_root / "tools" / "external" / "moss" / "bin" / "moss.pl"
            if perl and moss_pl.exists():
                return [perl, "-c", str(moss_pl)]
            return None

        if tool.name == "sim":
            return [wrapper, "-h"]

        # Common safe pattern for CLI tools.
        return [wrapper, "--help"]

    def _probe_succeeded(self, tool: ToolSpec, completed: subprocess.CompletedProcess[str]) -> bool:
        """
        Determine whether a probe should be considered successful.
        """
        if completed.returncode == 0:
            return True

        output = f"{completed.stdout}\n{completed.stderr}".lower()

        # NiCad prints usage and exits non-zero for help in some builds.
        if tool.name == "nicad":
            return "nicad clone detector" in output and "usage:" in output

        # Some SIM binaries print help text but still exit non-zero.
        if tool.name == "sim":
            return "show avaibale options" in output or "miscellaneous options" in output

        return False

    def _run_command(self, command: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
        """
        Run a command and capture output.
        """
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            return subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            return subprocess.CompletedProcess(
                args=command,
                returncode=-1,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + "\nTimeout exceeded",
            )
        except Exception as exc:
            return subprocess.CompletedProcess(
                args=command,
                returncode=-2,
                stdout="",
                stderr=str(exc),
            )

    def _tail(self, text: str, max_chars: int = 400) -> str:
        text = text or ""
        return text[-max_chars:]

    def check_tool(self, tool: ToolSpec) -> SmokeCheckResult:
        """
        Run a smoke check for a single registry tool.
        """
        result = SmokeCheckResult(tool_name=tool.name, status="FAIL")

        result.wrapper_exists = tool.wrapper_path.exists()
        result.tool_root_exists = tool.tool_root.exists()

        if result.wrapper_exists:
            result.wrapper_executable = os.access(tool.wrapper_path, os.X_OK)

        runtimes_ok, missing = self._all_runtimes_ok(tool)
        result.runtime_ok = runtimes_ok

        if not result.tool_root_exists:
            result.notes = f"Tool root not found: {tool.tool_root}"
            return result

        if not result.wrapper_exists:
            result.notes = f"Wrapper not found: {tool.wrapper_path}"
            return result

        if not result.wrapper_executable:
            result.notes = f"Wrapper not executable: {tool.wrapper_path}"
            return result

        if not result.runtime_ok:
            result.notes = f"Missing runtimes: {', '.join(missing)}"
            return result

        probe_command = self._safe_probe_command(tool)
        result.command = probe_command

        if probe_command is None:
            # Accept a PASS for purely structural/runtime validation when no safe probe is available.
            result.help_ok = False
            result.status = "PASS"
            result.notes = "Wrapper and runtimes OK; no safe lightweight probe configured"
            return result

        completed = self._run_command(probe_command, cwd=self.repo_root)
        result.returncode = completed.returncode
        result.stdout_tail = self._tail(completed.stdout)
        result.stderr_tail = self._tail(completed.stderr)

        result.help_ok = self._probe_succeeded(tool, completed)

        if result.help_ok:
            result.status = "PASS"
            result.notes = "Wrapper, runtime, and lightweight probe succeeded"
        else:
            result.status = "FAIL"
            result.notes = "Lightweight probe failed"

        return result

    def run_all(self, only_official: bool = False) -> dict[str, SmokeCheckResult]:
        """
        Run smoke checks on enabled tools, optionally restricting to official tools.
        """
        tools = self.registry.enabled_tools()
        if only_official:
            tools = [tool for tool in tools if tool.official]

        results: dict[str, SmokeCheckResult] = {}

        for tool in tools:
            logger.info("Running smoke check for tool=%s", tool.name)
            results[tool.name] = self.check_tool(tool)

        output_path = self.output_dir / "smoke_results.json"
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(
                {name: result.to_dict() for name, result in results.items()},
                fh,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("Smoke test results written to %s", output_path)
        return results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)7s | %(message)s",
    )

    only_official = "--official-only" in sys.argv

    runner = ToolSmokeRunner()
    results = runner.run_all(only_official=only_official)

    print("\n" + "=" * 72)
    print("TOOL SMOKE TEST RESULTS")
    print("=" * 72)

    for name, result in results.items():
        print(
            f"{name:12} | {result.status:4} | "
            f"wrapper={str(result.wrapper_exists):5} | "
            f"exec={str(result.wrapper_executable):5} | "
            f"runtime={str(result.runtime_ok):5} | "
            f"probe={str(result.help_ok):5} | "
            f"{result.notes}"
        )

    print("=" * 72)

    failed = [result for result in results.values() if result.status == "FAIL"]
    if failed:
        print(f"\nFAIL: {len(failed)} tool(s) failed smoke checks")
        raise SystemExit(1)

    print(f"\nPASS: all {len(results)} checked tool(s) passed smoke checks")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
