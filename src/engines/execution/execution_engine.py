"""
Execution Engine - Real subprocess runner for external plagiarism detection tools.

Provides:
- MOSS execution with API key management
- JPlag execution with Docker/local fallback
- Dolos execution
- NiCad execution
- Timeout control
- Sandbox execution (Docker-based)
- Deterministic environment (seeded, reproducible)
- Result normalization to unified schema
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of an external tool execution."""
    tool_name: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    output_path: Optional[Path] = None
    parsed_pairs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "exit_code": self.exit_code,
            "execution_time": round(self.execution_time, 3),
            "num_pairs": len(self.parsed_pairs),
            "metadata": self.metadata,
        }


class DeterministicEnv:
    """Creates a deterministic execution environment."""

    def __init__(self, seed: int = 42, clean_env: bool = True):
        self.seed = seed
        self.clean_env = clean_env

    def build_env(self) -> Dict[str, str]:
        env = {}
        if self.clean_env:
            env = {
                "HOME": os.environ.get("HOME", "/tmp"),
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONHASHSEED": str(self.seed),
                "JAVA_TOOL_OPTIONS": f"-Dfile.encoding=UTF-8 -Duser.language=en -Duser.region=US",
            }
        else:
            env = dict(os.environ)
        env["PYTHONHASHSEED"] = str(self.seed)
        return env

    def compute_fingerprint(self, code_dir: Path) -> str:
        files = sorted(code_dir.rglob("*"))
        h = hashlib.sha256()
        for f in files:
            if f.is_file():
                h.update(f.read_bytes())
        return h.hexdigest()[:16]


class SandboxExecutor:
    """Docker-based sandbox for isolated tool execution."""

    def __init__(
        self,
        timeout: int = 300,
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        network_disabled: bool = True,
    ):
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_disabled = network_disabled
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def run_in_sandbox(
        self,
        image: str,
        command: List[str],
        volumes: Optional[Dict[str, str]] = None,
        workdir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        if not self._docker_available:
            return ExecutionResult(
                tool_name="sandbox",
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Docker not available",
                execution_time=0.0,
                metadata={"docker_available": False},
            )

        cmd = ["docker", "run", "--rm"]

        if self.network_disabled:
            cmd.append("--network=none")

        cmd.extend(["--memory", self.memory_limit])
        cmd.extend(["--cpus", str(self.cpu_limit)])

        if volumes:
            for host_path, container_path in volumes.items():
                cmd.extend(["-v", f"{host_path}:{container_path}"])

        if workdir:
            cmd.extend(["-w", workdir])

        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])

        cmd.append(image)
        cmd.extend(command)

        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=self.timeout,
            )
            elapsed = time.monotonic() - start
            return ExecutionResult(
                tool_name="sandbox",
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return ExecutionResult(
                tool_name="sandbox",
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {self.timeout}s",
                execution_time=elapsed,
                metadata={"timed_out": True},
            )


class BaseToolRunner(ABC):
    """Abstract base for external tool runners."""

    def __init__(
        self,
        timeout: int = 300,
        sandbox: Optional[SandboxExecutor] = None,
        deterministic_env: Optional[DeterministicEnv] = None,
    ):
        self.timeout = timeout
        self.sandbox = sandbox
        self.det_env = deterministic_env or DeterministicEnv()

    @property
    @abstractmethod
    def tool_name(self) -> str:
        pass

    @abstractmethod
    def run(
        self,
        code_dir: Path,
        language: str,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        pass

    def _ensure_output_dir(self, output_dir: Optional[Path]) -> Path:
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix=f"{self.tool_name}_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def is_available(self) -> bool:
        """Return whether the underlying tool is actually usable."""
        return True

    def _run_subprocess(
        self,
        cmd: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Path] = None,
    ) -> subprocess.CompletedProcess:
        run_env = env or self.det_env.build_env()
        return subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=self.timeout,
            env=run_env,
            cwd=str(cwd) if cwd else None,
        )


class MossRunner(BaseToolRunner):
    """
    MOSS (Measure Of Software Similarity) runner.

    Requires:
    - MOSS API key (MOSS_USER_ID env var or parameter)
    - moss.pl script available
    - Perl interpreter

    MOSS runs remotely, so sandboxing is limited to local preprocessing.
    """

    MOSS_LANG_MAP = {
        "python": "py",
        "java": "java",
        "c": "cc",
        "cpp": "cc",
        "javascript": "js",
        "ruby": "pl",
        "csharp": "cc",
        "go": "go",
        "rust": "cc",
    }

    def __init__(
        self,
        moss_user_id: Optional[str] = None,
        moss_script: Optional[Path] = None,
        timeout: int = 300,
        deterministic_env: Optional[DeterministicEnv] = None,
    ):
        super().__init__(timeout=timeout, deterministic_env=deterministic_env)
        self.moss_user_id = moss_user_id or os.environ.get("MOSS_USER_ID")
        self.moss_script = moss_script or Path("/usr/local/bin/moss.pl")

    @property
    def tool_name(self) -> str:
        return "moss"

    def is_available(self) -> bool:
        return bool(
            self.moss_user_id
            and shutil.which("perl")
            and self.moss_script
            and Path(self.moss_script).exists()
        )

    def run(
        self,
        code_dir: Path,
        language: str,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        output_dir = self._ensure_output_dir(output_dir)

        if not self.moss_user_id:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="MOSS_USER_ID not set. Set env var or pass moss_user_id.",
                execution_time=0.0,
                metadata={"error": "missing_api_key"},
            )

        moss_lang = self.MOSS_LANG_MAP.get(language.lower(), "cc")
        files = list(code_dir.rglob("*.py")) if language.lower() == "python" else list(code_dir.rglob("*"))
        files = [f for f in files if f.is_file() and not f.name.startswith(".")]

        if not files:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"No source files found in {code_dir}",
                execution_time=0.0,
            )

        cmd = ["perl", str(self.moss_script), "-l", moss_lang, "-u", self.moss_user_id]
        for f in files:
            cmd.append(str(f))

        start = time.monotonic()
        try:
            result = self._run_subprocess(cmd, cwd=code_dir)
            elapsed = time.monotonic() - start

            output_html = output_dir / "moss_results.html"
            if result.returncode == 0 and result.stdout.strip():
                url_line = result.stdout.strip().split("\n")[-1]
                if url_line.startswith("http"):
                    output_html.write_text(f"<html><body><p>Results: {url_line}</p></body></html>")

            return ExecutionResult(
                tool_name=self.tool_name,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
                output_path=output_html if output_html.exists() else None,
                metadata={
                    "num_files": len(files),
                    "language": moss_lang,
                    "fingerprint": self.det_env.compute_fingerprint(code_dir),
                },
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"MOSS timed out after {self.timeout}s",
                execution_time=self.timeout,
                metadata={"timed_out": True},
            )


class JPlagRunner(BaseToolRunner):
    """
    JPlag runner.

    Supports:
    - JAR-based execution (jplag.jar)
    - Docker-based execution (ghcr.io/jplag/jplag)
    - Multiple language frontends
    """

    JPLAG_LANG_MAP = {
        "python": "python3",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "javascript": "javascript",
        "typescript": "typescript",
        "csharp": "csharp",
        "go": "go",
        "rust": "rust",
        "kotlin": "kotlin",
        "swift": "swift",
    }

    def __init__(
        self,
        jplag_jar: Optional[Path] = None,
        use_docker: bool = True,
        timeout: int = 300,
        sandbox: Optional[SandboxExecutor] = None,
        deterministic_env: Optional[DeterministicEnv] = None,
    ):
        super().__init__(
            timeout=timeout,
            sandbox=sandbox or SandboxExecutor(timeout=timeout),
            deterministic_env=deterministic_env,
        )
        self.jplag_jar = jplag_jar
        self.use_docker = use_docker and self.sandbox._docker_available

    @property
    def tool_name(self) -> str:
        return "jplag"

    def is_available(self) -> bool:
        if self.use_docker:
            return bool(self.sandbox and self.sandbox._docker_available)
        if self.jplag_jar and self.jplag_jar.exists():
            return True
        return shutil.which("jplag") is not None

    def run(
        self,
        code_dir: Path,
        language: str,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        output_dir = self._ensure_output_dir(output_dir)
        jplag_lang = self.JPLAG_LANG_MAP.get(language.lower(), "text")

        if self.use_docker:
            return self._run_docker(code_dir, jplag_lang, output_dir)
        elif self.jplag_jar and self.jplag_jar.exists():
            return self._run_jar(code_dir, jplag_lang, output_dir)
        else:
            jplag_cmd = shutil.which("jplag")
            if jplag_cmd:
                return self._run_cli(jplag_cmd, code_dir, jplag_lang, output_dir)
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="JPlag not found. Install jplag.jar, Docker image, or CLI.",
                execution_time=0.0,
                metadata={"error": "tool_not_found"},
            )

    def _run_docker(
        self, code_dir: Path, language: str, output_dir: Path
    ) -> ExecutionResult:
        start = time.monotonic()
        result = self.sandbox.run_in_sandbox(
            image="ghcr.io/jplag/jplag:latest",
            command=["-l", language, "-r", "/output", "/input"],
            volumes={
                str(code_dir): "/input",
                str(output_dir): "/output",
            },
        )
        result.tool_name = self.tool_name
        result.execution_time = time.monotonic() - start
        result.output_path = output_dir / "results.json"
        if not result.output_path.exists():
            result.output_path = output_dir / "results.xml"
        result.metadata = {
            "mode": "docker",
            "language": language,
            "fingerprint": self.det_env.compute_fingerprint(code_dir),
        }
        return result

    def _run_jar(
        self, code_dir: Path, language: str, output_dir: Path
    ) -> ExecutionResult:
        cmd = [
            "java", "-jar", str(self.jplag_jar),
            "-l", language,
            "-r", str(output_dir),
            str(code_dir),
        ]
        start = time.monotonic()
        try:
            result = self._run_subprocess(cmd)
            elapsed = time.monotonic() - start
            return ExecutionResult(
                tool_name=self.tool_name,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
                output_path=output_dir / "results.json",
                metadata={
                    "mode": "jar",
                    "language": language,
                    "fingerprint": self.det_env.compute_fingerprint(code_dir),
                },
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"JPlag timed out after {self.timeout}s",
                execution_time=self.timeout,
                metadata={"timed_out": True, "mode": "jar"},
            )

    def _run_cli(
        self, jplag_cmd: str, code_dir: Path, language: str, output_dir: Path
    ) -> ExecutionResult:
        cmd = [jplag_cmd, "-l", language, "-r", str(output_dir), str(code_dir)]
        start = time.monotonic()
        try:
            result = self._run_subprocess(cmd)
            elapsed = time.monotonic() - start
            return ExecutionResult(
                tool_name=self.tool_name,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
                output_path=output_dir / "results.json",
                metadata={
                    "mode": "cli",
                    "language": language,
                    "fingerprint": self.det_env.compute_fingerprint(code_dir),
                },
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"JPlag timed out after {self.timeout}s",
                execution_time=self.timeout,
                metadata={"timed_out": True, "mode": "cli"},
            )


class DolosRunner(BaseToolRunner):
    """
    Dolos runner.

    Dolos is a modern plagiarism detection tool for source code.
    Requires Node.js and the Dolos CLI.
    """

    def __init__(
        self,
        timeout: int = 300,
        sandbox: Optional[SandboxExecutor] = None,
        deterministic_env: Optional[DeterministicEnv] = None,
    ):
        super().__init__(
            timeout=timeout,
            sandbox=sandbox or SandboxExecutor(timeout=timeout),
            deterministic_env=deterministic_env,
        )

    @property
    def tool_name(self) -> str:
        return "dolos"

    def is_available(self) -> bool:
        return shutil.which("dolos") is not None

    def run(
        self,
        code_dir: Path,
        language: str,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        output_dir = self._ensure_output_dir(output_dir)
        dolos_cmd = shutil.which("dolos")

        if not dolos_cmd:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Dolos CLI not found. Install with: npm install -g @dodona/dolos",
                execution_time=0.0,
                metadata={"error": "tool_not_found"},
            )

        cmd = [
            dolos_cmd, "run",
            "--format", "csv",
            "--output", str(output_dir / "dolos_results.csv"),
            str(code_dir),
        ]

        start = time.monotonic()
        try:
            result = self._run_subprocess(cmd)
            elapsed = time.monotonic() - start
            return ExecutionResult(
                tool_name=self.tool_name,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
                output_path=output_dir / "dolos_results.csv",
                metadata={
                    "language": language,
                    "fingerprint": self.det_env.compute_fingerprint(code_dir),
                },
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Dolos timed out after {self.timeout}s",
                execution_time=self.timeout,
                metadata={"timed_out": True},
            )


class NiCadRunner(BaseToolRunner):
    """
    NiCad clone detector runner.

    NiCad detects Type-1, Type-2, and Type-3 clones.
    Requires NiCad installation.
    """

    def __init__(
        self,
        nicad_path: Optional[Path] = None,
        timeout: int = 300,
        deterministic_env: Optional[DeterministicEnv] = None,
    ):
        super().__init__(timeout=timeout, deterministic_env=deterministic_env)
        self.nicad_path = nicad_path

    @property
    def tool_name(self) -> str:
        return "nicad"

    def is_available(self) -> bool:
        if self.nicad_path and Path(self.nicad_path).exists():
            return True
        return shutil.which("nicad5") is not None or shutil.which("nicad") is not None

    def run(
        self,
        code_dir: Path,
        language: str,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        output_dir = self._ensure_output_dir(output_dir)

        nicad_bin = self.nicad_path or Path("/usr/local/bin/nicad5")
        if not nicad_bin.exists():
            nicad_bin = shutil.which("nicad5") or shutil.which("nicad")

        if not nicad_bin:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr="NiCad not found. Set nicad_path or install NiCad.",
                execution_time=0.0,
                metadata={"error": "tool_not_found"},
            )

        system_name = f"benchmark_{language}_{int(time.time())}"
        cmd = [str(nicad_bin), language, str(code_dir), system_name]

        start = time.monotonic()
        try:
            result = self._run_subprocess(cmd)
            elapsed = time.monotonic() - start

            output_xml = output_dir / f"{system_name}.xml"
            if output_xml.exists():
                output_path = output_xml
            else:
                output_path = output_dir / "nicad_output.txt"
                output_path.write_text(result.stdout)

            return ExecutionResult(
                tool_name=self.tool_name,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
                output_path=output_path,
                metadata={
                    "language": language,
                    "system_name": system_name,
                    "fingerprint": self.det_env.compute_fingerprint(code_dir),
                },
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                tool_name=self.tool_name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"NiCad timed out after {self.timeout}s",
                execution_time=self.timeout,
                metadata={"timed_out": True},
            )


class ExecutionEngine:
    """
    Unified execution engine for running external plagiarism detection tools.

    Manages tool discovery, execution, and result collection.
    """

    TOOL_REGISTRY = {
        "moss": MossRunner,
        "jplag": JPlagRunner,
        "dolos": DolosRunner,
        "nicad": NiCadRunner,
    }

    def __init__(
        self,
        timeout: int = 300,
        use_sandbox: bool = True,
        seed: int = 42,
        tool_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.timeout = timeout
        self.use_sandbox = use_sandbox
        self.det_env = DeterministicEnv(seed=seed)
        self.sandbox = SandboxExecutor(timeout=timeout) if use_sandbox else None
        self.tool_configs = tool_configs or {}
        self._runners: Dict[str, BaseToolRunner] = {}

    def get_runner(self, tool_name: str) -> BaseToolRunner:
        if tool_name not in self._runners:
            cls = self.TOOL_REGISTRY.get(tool_name.lower())
            if not cls:
                raise ValueError(f"Unknown tool: {tool_name}. Available: {list(self.TOOL_REGISTRY.keys())}")
            config = self.tool_configs.get(tool_name, {})
            config.setdefault("timeout", self.timeout)
            config.setdefault("deterministic_env", self.det_env)
            if self.sandbox and tool_name.lower() in ("jplag", "dolos"):
                config.setdefault("sandbox", self.sandbox)
            self._runners[tool_name] = cls(**config)
        return self._runners[tool_name]

    def run_tool(
        self,
        tool_name: str,
        code_dir: Path,
        language: str,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        runner = self.get_runner(tool_name)
        return runner.run(code_dir, language, output_dir)

    def run_all_tools(
        self,
        code_dir: Path,
        language: str,
        tools: Optional[List[str]] = None,
        output_base: Optional[Path] = None,
    ) -> Dict[str, ExecutionResult]:
        tools = tools or list(self.TOOL_REGISTRY.keys())
        results = {}
        for tool in tools:
            output_dir = (output_base / tool) if output_base else None
            results[tool] = self.run_tool(tool, code_dir, language, output_dir)
        return results

    def available_tools(self) -> List[str]:
        available = []
        for tool_name in self.TOOL_REGISTRY:
            try:
                runner = self.get_runner(tool_name)
                if runner.is_available():
                    available.append(tool_name)
            except Exception:
                pass
        return available
