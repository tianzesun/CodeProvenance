import os
import sys
import tempfile
import subprocess
import resource
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float
    timeout: bool = False
    memory_exceeded: bool = False


class PythonSandboxExecutor:
    """
    Isolated execution sandbox for code generation benchmarks.
    Uses subprocess isolation with resource limits, timeout, and temp directory cleanup.
    """

    def __init__(
        self,
        timeout_seconds: int = 5,
        memory_limit_mb: int = 512,
        network_enabled: bool = False,
        cleanup: bool = True
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.network_enabled = network_enabled
        self.cleanup = cleanup

    def _set_limits(self) -> None:
        """Apply process resource limits in child process."""
        # Set CPU timeout
        resource.setrlimit(resource.RLIMIT_CPU, (self.timeout_seconds, self.timeout_seconds + 1))

        # Set memory limit
        memory_limit_bytes = self.memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))

        # Disable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def run(self, code: str) -> ExecutionResult:
        """
        Execute Python code in isolated sandbox.

        Args:
            code: Complete Python program to execute

        Returns:
            ExecutionResult with execution status and output
        """
        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "run.py")

            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.pop("VIRTUAL_ENV", None)

            if not self.network_enabled:
                env["http_proxy"] = "http://127.0.0.1:9"
                env["https_proxy"] = "http://127.0.0.1:9"

            try:
                result = subprocess.run(
                    [sys.executable, script_path],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    preexec_fn=self._set_limits,
                    env=env
                )

                elapsed_ms = (time.perf_counter() - start_time) * 1000

                return ExecutionResult(
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    elapsed_ms=elapsed_ms
                )

            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return ExecutionResult(
                    returncode=-1,
                    stdout="",
                    stderr="Timeout exceeded",
                    elapsed_ms=elapsed_ms,
                    timeout=True
                )
