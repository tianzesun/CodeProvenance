"""
Execution-based similarity algorithm.

Compares code by executing it and comparing outputs.
Handles Type 4 semantic clones - different syntax, same behavior.

Features:
- Docker sandbox execution
- Test case generation
- Output comparison
- Timeout and resource limits
- Multi-language support

SECURITY
--------
This module runs submitted (untrusted) code. It is only ever run inside a Docker
container with no network, a read-only filesystem, dropped capabilities, a
non-root user and CPU/memory/process limits. When Docker is not available it now
REFUSES to run the code. The previous version silently fell back to executing the
submission directly on the application server, which gives every student remote
code execution (environment secrets, the database, other students' work). An
operator who accepts that risk for a throw-away development machine must opt in
explicitly with ``EXECUTION_ALLOW_UNSANDBOXED=1``.
"""

import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from src.backend.domain.models import EvidenceBlock, Finding

from .base_similarity import BaseSimilarityAlgorithm

logger = logging.getLogger(__name__)

#: Captured stdout/stderr is truncated to this many bytes each (a program that prints
#: in a loop used to be buffered in memory without limit for the whole timeout).
MAX_OUTPUT_BYTES = 1_000_000
#: Partial credit for outputs that differ but resemble each other (relative to a match).
PARTIAL_CREDIT = 0.5
_RESULT_CACHE_SIZE = 512


class ExecutionResult:
    """Result of code execution."""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        execution_time: float = 0.0,
        memory_used: float = 0.0,
        timed_out: bool = False,
        refused: bool = False,
    ):
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.memory_used = memory_used
        self.timed_out = timed_out
        #: True when the code was NOT run because no sandbox is available.
        self.refused = refused
        self.output_hash = self._hash_output()

    def _hash_output(self) -> str:
        """Hash execution output for comparison (SHA-256; this used MD5)."""
        combined = f"{self.stdout}:{self.exit_code}"
        return hashlib.sha256(combined.encode("utf-8", "replace")).hexdigest()

    def is_successful(self) -> bool:
        """Check if execution was successful."""
        return self.exit_code == 0 and not self.timed_out and not self.refused


class TestCase:
    """Represents a test case for execution."""

    __test__ = False  # not a pytest test class

    def __init__(
        self,
        input_data: str = "",
        expected_output: str = "",
        test_type: str = "normal",
        description: str = "",
    ):
        self.input_data = input_data
        self.expected_output = expected_output
        self.test_type = test_type
        self.description = description


# language -> (image, filename, shell command run inside the container)
_DOCKER_SPECS: dict[str, tuple[str, str, str | list[str]]] = {
    "python": ("python:3.12-slim", "solution.py", ["python3", "solution.py"]),
    "java": ("eclipse-temurin:21-jdk", "Solution.java", "javac -d /tmp Solution.java && java -cp /tmp Solution"),
    "c": ("gcc:13", "solution.c", "gcc -o /tmp/solution solution.c && /tmp/solution"),
    "cpp": ("gcc:13", "solution.cpp", "g++ -o /tmp/solution solution.cpp && /tmp/solution"),
    "go": ("golang:1.22", "solution.go", "go run solution.go"),
    "rust": ("rust:1.78-slim", "solution.rs", "rustc solution.rs -o /tmp/solution && /tmp/solution"),
    "javascript": ("node:20-slim", "solution.js", ["node", "solution.js"]),
    "ruby": ("ruby:3.3-slim", "solution.rb", ["ruby", "solution.rb"]),
    "php": ("php:8.3-cli", "solution.php", ["php", "solution.php"]),
    "perl": ("perl:5.38", "solution.pl", ["perl", "solution.pl"]),
}
_LANGUAGE_ALIASES = {"python3": "python", "py": "python", "js": "javascript", "c++": "cpp", "golang": "go", "rs": "rust"}


def _normalize_language(language: str | None) -> str:
    name = (language or "python").strip().lower()
    return _LANGUAGE_ALIASES.get(name, name)


@lru_cache(maxsize=16)
def _find_interpreter(interpreter: str) -> str | None:
    """Resolve a local interpreter once (it was probed with a subprocess per run)."""
    return shutil.which(interpreter)


class DockerSandbox:
    """
    Docker-based code execution sandbox.

    Provides secure, isolated execution with:
    - Resource limits (CPU, memory, processes, time, output size)
    - Network isolation
    - Read-only filesystem with a small writable /tmp
    - No capabilities, no privilege escalation, non-root user
    """

    def __init__(
        self,
        timeout: int = 10,
        memory_limit: str = "256m",
        cpu_limit: float = 0.5,
        allow_unsandboxed: bool | None = None,
    ):
        """
        Initialize Docker sandbox.

        Args:
            timeout: Maximum execution time in seconds
            memory_limit: Memory limit (e.g., '256m', '1g')
            cpu_limit: CPU limit (0.0-1.0)
            allow_unsandboxed: Run on the host when Docker is missing. Default: only
                if ``EXECUTION_ALLOW_UNSANDBOXED=1``. Never enable this on a server
                that handles real submissions.
        """
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        if allow_unsandboxed is None:
            allow_unsandboxed = os.environ.get("EXECUTION_ALLOW_UNSANDBOXED") == "1"
        self.allow_unsandboxed = allow_unsandboxed
        self._docker_available = self._check_docker()
        if not self._docker_available:
            logger.warning(
                "Docker is not available: execution similarity is %s",
                "RUNNING SUBMISSIONS ON THE HOST (EXECUTION_ALLOW_UNSANDBOXED=1)"
                if self.allow_unsandboxed
                else "disabled (code will not be run)",
            )

    def _check_docker(self) -> bool:
        """Check that a Docker DAEMON is reachable.

        ``docker --version`` succeeds whenever the CLI is installed, even with no
        daemon, so "available" was true on machines where every run then failed.
        """
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    # ── execution ──────────────────────────────────────────────────

    def execute(
        self, code: str, language: str, test_input: str = ""
    ) -> ExecutionResult:
        """
        Execute code in Docker sandbox.

        Args:
            code: Source code to execute
            language: Programming language
            test_input: Standard input for the program

        Returns:
            ExecutionResult with stdout, stderr, exit_code, etc. A ``refused`` result
            (``is_successful()`` False) when no sandbox is available.
        """
        language = _normalize_language(language)
        if self._docker_available and language in _DOCKER_SPECS:
            return self._execute_docker(code, language, test_input)
        if self.allow_unsandboxed:
            return self._execute_local(code, language, test_input)
        return ExecutionResult(
            stderr="Execution refused: no container sandbox available for this language",
            exit_code=-2,
            refused=True,
        )

    def _execute_docker(self, code: str, language: str, test_input: str) -> ExecutionResult:
        image, filename, command = _DOCKER_SPECS[language]
        name = f"idesk-{uuid.uuid4().hex[:16]}"
        run_cmd = command if isinstance(command, list) else ["sh", "-c", command]

        fd, code_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
        try:
            with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as handle:
                handle.write(code)
            os.chmod(code_path, 0o644)  # readable by the unprivileged container user

            cmd = [
                "docker", "run", "--rm", "-i", "--name", name,
                f"--memory={self.memory_limit}", f"--memory-swap={self.memory_limit}",
                f"--cpus={self.cpu_limit}", "--pids-limit=64",
                "--network=none", "--read-only", "--tmpfs", "/tmp:rw,exec,nosuid,size=64m",
                "--cap-drop=ALL", "--security-opt", "no-new-privileges",
                "--user", "65534:65534",
                "-e", "HOME=/tmp", "-e", "GOCACHE=/tmp/gocache",
                "-v", f"{code_path}:/code/{filename}:ro", "-w", "/code",
                image, *run_cmd,
            ]  # fmt: skip

            def kill_container() -> None:
                # Killing the ``docker`` client does NOT stop the container, so a
                # timed-out submission used to keep burning CPU on the host.
                subprocess.run(["docker", "kill", name], capture_output=True, timeout=10, check=False)

            return self._run_limited(cmd, test_input, kill_container)
        finally:
            try:
                os.unlink(code_path)
            except OSError:
                pass

    def _execute_local(self, code: str, language: str, test_input: str) -> ExecutionResult:
        """Run code directly on the host. UNSAFE: only with an explicit opt-in."""
        interpreter = self._get_interpreter(language)
        if not interpreter:
            return ExecutionResult(stderr=f"Unsupported language: {language}", exit_code=-1)

        workdir = tempfile.mkdtemp(prefix="idesk-exec-")
        try:
            path = os.path.join(workdir, _DOCKER_SPECS.get(language, ("", "solution.txt", ""))[1])
            with open(path, "w", encoding="utf-8", errors="replace") as handle:
                handle.write(code)
            cmd = [interpreter, "-I", path] if language == "python" else [interpreter, path]

            def limits() -> None:  # pragma: no cover - runs in the child
                try:
                    import resource

                    resource.setrlimit(resource.RLIMIT_CPU, (self.timeout + 1, self.timeout + 1))
                    resource.setrlimit(resource.RLIMIT_AS, (512 << 20, 512 << 20))
                    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
                    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
                except Exception:  # noqa: S110
                    pass

            # Minimal environment: the server's secrets are not inherited.
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": workdir, "LANG": "C.UTF-8"}
            return self._run_limited(cmd, test_input, None, cwd=workdir, env=env, preexec_fn=limits)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _run_limited(
        self,
        cmd: list[str],
        test_input: str,
        on_timeout,
        **popen_kwargs: Any,
    ) -> ExecutionResult:
        """Run ``cmd`` with a wall-clock timeout and capped output."""
        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs
            )
        except OSError as exc:
            return ExecutionResult(stderr=f"Could not start process: {exc}", exit_code=-1)

        out_buf: list[bytes] = []
        err_buf: list[bytes] = []
        exceeded = threading.Event()

        def drain(stream, store: list[bytes]) -> None:
            total = 0
            try:
                while True:
                    chunk = stream.read(8192)
                    if not chunk:
                        break
                    if total < MAX_OUTPUT_BYTES:
                        store.append(chunk[: MAX_OUTPUT_BYTES - total])
                    total += len(chunk)
                    if total > MAX_OUTPUT_BYTES:
                        exceeded.set()
            except (OSError, ValueError):
                pass

        def feed() -> None:
            try:
                proc.stdin.write((test_input or "").encode("utf-8", "replace"))
                proc.stdin.close()
            except (OSError, ValueError):  # the program may exit without reading stdin
                pass

        threads = [
            threading.Thread(target=drain, args=(proc.stdout, out_buf), daemon=True),
            threading.Thread(target=drain, args=(proc.stderr, err_buf), daemon=True),
            threading.Thread(target=feed, daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        deadline = start + self.timeout
        while proc.poll() is None:
            if time.monotonic() >= deadline or exceeded.is_set():
                timed_out = True
                break
            time.sleep(0.02)

        if timed_out:
            proc.kill()
            if on_timeout is not None:
                try:
                    on_timeout()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not stop sandbox container: %s", exc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        for thread in threads:
            thread.join(timeout=2)

        elapsed = time.monotonic() - start
        stdout = b"".join(out_buf).decode("utf-8", "replace")
        stderr = b"".join(err_buf).decode("utf-8", "replace")
        if timed_out:
            reason = "output limit exceeded" if exceeded.is_set() else f"timed out after {self.timeout}s"
            return ExecutionResult(
                stdout=stdout, stderr=f"{stderr}\nExecution {reason}", exit_code=-1,
                execution_time=elapsed, timed_out=True,
            )  # fmt: skip
        return ExecutionResult(
            stdout=stdout, stderr=stderr, exit_code=proc.returncode, execution_time=elapsed
        )

    # ── helpers (kept for compatibility) ───────────────────────────

    def _get_docker_image(self, language: str) -> str | None:
        """Get Docker image for language."""
        spec = _DOCKER_SPECS.get(_normalize_language(language))
        return spec[0] if spec else None

    def _get_interpreter(self, language: str) -> str | None:
        """Get local interpreter for language."""
        interpreters = {
            "python": "python3",
            "javascript": "node",
            "ruby": "ruby",
            "perl": "perl",
            "php": "php",
            "bash": "bash",
        }
        interpreter = interpreters.get(_normalize_language(language))
        return _find_interpreter(interpreter) if interpreter else None

    def _get_filename(self, language: str) -> str:
        """Get filename for language."""
        spec = _DOCKER_SPECS.get(_normalize_language(language))
        return spec[1] if spec else "solution.txt"

    def _get_run_command(self, language: str, filename: str) -> list[str]:
        """Command to run code in Docker.

        Compiled languages were returned as ``["javac", file, "&&", "java", ...]``,
        which was then split on ``&&`` into two ARGUMENTS passed to ``docker run``
        (neither is an executable), so Java, C, C++ and Rust never worked. They now
        run through ``sh -c`` and compile into the writable /tmp.
        """
        spec = _DOCKER_SPECS.get(_normalize_language(language))
        if spec is None:
            return ["cat", filename]
        command = spec[2]
        return list(command) if isinstance(command, list) else ["sh", "-c", command]


class TestCaseGenerator:
    """
    Generates test cases for code execution comparison.

    Supports:
    - Standard input/output problems
    - Function-based problems
    - Edge cases
    """

    __test__ = False  # not a pytest test class

    def __init__(self):
        self.test_cases: list[TestCase] = []

    def generate_test_cases(self, code: str, language: str) -> list[TestCase]:
        """
        Generate test cases based on code analysis.

        Args:
            code: Source code
            language: Programming language

        Returns:
            List of TestCase objects
        """
        test_cases = []

        analysis = self._analyze_code(code)

        if analysis["type"] == "stdin_stdout":
            test_cases.extend(self._generate_io_tests(code))

        elif analysis["type"] == "function":
            test_cases.extend(self._generate_function_tests(code))

        # Always add edge cases
        test_cases.extend(self._generate_edge_cases())

        return test_cases[:10]  # Limit to 10 test cases

    def _analyze_code(self, code: str) -> dict[str, Any]:
        """Analyze code structure."""
        result: dict[str, Any] = {"type": "unknown", "functions": []}

        # Check for stdin/stdout patterns
        if any(
            p in code
            for p in [
                "input(",
                "raw_input(",
                "sys.stdin",
                "System.in",
                "scanf",
                "cin >>",
                "std::cin",
                "console.ReadLine",
                "bufio",
            ]
        ):
            result["type"] = "stdin_stdout"

        # Check for function definitions
        func_patterns = [
            r"def\s+(\w+)",  # Python
            r"(?:public\s+)?\w+\s+(\w+)\s*\(",  # Java/C/C++
            r"func\s+(\w+)",  # Go
            r"fn\s+(\w+)",  # Rust
        ]

        for pattern in func_patterns:
            functions = re.findall(pattern, code)
            if functions:
                result["functions"] = [f for f in functions if f not in ["main", "__init__"]]

        # A program that reads stdin stays an I/O program. The loop used to overwrite
        # the type with "function" whenever ANY pattern matched, and the Java/C pattern
        # matches almost everything (``return len(x)``, ``else if (``), so I/O tests
        # were almost never generated.
        if result["functions"] and result["type"] != "stdin_stdout":
            result["type"] = "function"

        return result

    def _generate_io_tests(self, code: str) -> list[TestCase]:
        """Generate I/O test cases."""

        common_inputs = [
            TestCase("5\n", "", "simple", "Single number"),
            TestCase("3 4 5\n", "", "numbers", "Space-separated"),
            TestCase("10\n20\n30\n", "", "newlines", "Newline-separated"),
            TestCase("hello world\n", "", "string", "Simple string"),
            TestCase("5\n1 2 3 4 5\n", "", "array", "Array with size"),
            TestCase("0\n", "", "empty", "Zero/empty"),
            TestCase("1\n", "", "minimal", "Minimal input"),
        ]

        return common_inputs[:5]

    def _generate_function_tests(self, code: str) -> list[TestCase]:
        """Generate function test cases."""

        return [
            TestCase("1 2", "", "small", "Small values"),
            TestCase("100 200", "", "medium", "Medium values"),
            TestCase("0 0", "", "zero", "Zero values"),
            TestCase("-1 -2", "", "negative", "Negative values"),
        ]

    def _generate_edge_cases(self) -> list[TestCase]:
        """Generate edge case test cases."""
        return [
            TestCase("", "", "empty", "Empty input"),
            TestCase("\n", "", "newline", "Just newline"),
            TestCase(" ", "", "whitespace", "Whitespace only"),
            TestCase("a" * 100, "", "long", "Long string"),
        ]


class ExecutionSimilarity(BaseSimilarityAlgorithm):
    """
    Execution-based similarity algorithm.

    Compares code by executing both versions and comparing outputs.
    Detects Type 4 semantic clones - different code, same behavior.

    Only tests on which BOTH programs run successfully and at least one prints
    something count as evidence. Two programs that print nothing (every module that
    only defines functions, or any pair of programs whose output is empty) used to
    "match" on every test and score 1.0 as semantic clones.
    """

    def __init__(
        self, timeout: int = 10, memory_limit: str = "256m", max_test_cases: int = 5
    ):
        """
        Initialize Execution similarity algorithm.

        Args:
            timeout: Maximum execution time per test case
            memory_limit: Memory limit for execution
            max_test_cases: Maximum number of test cases
        """
        super().__init__("execution")
        self.sandbox = DockerSandbox(timeout=timeout, memory_limit=memory_limit)
        self.test_generator = TestCaseGenerator()
        self.max_test_cases = max_test_cases
        self._result_cache: OrderedDict[tuple[str, str, str], ExecutionResult] = OrderedDict()
        self._cache_lock = threading.Lock()

    def _run(self, code: str, language: str, test_input: str) -> ExecutionResult:
        """Execute with a per-file result cache: in an all-pairs run each file was
        executed once PER PAIR instead of once per test input."""
        key = (hashlib.sha256(code.encode("utf-8", "replace")).hexdigest(), language, test_input)
        with self._cache_lock:
            cached = self._result_cache.get(key)
            if cached is not None:
                self._result_cache.move_to_end(key)
                return cached
        result = self.sandbox.execute(code, language, test_input)
        if not result.refused:
            with self._cache_lock:
                self._result_cache[key] = result
                while len(self._result_cache) > _RESULT_CACHE_SIZE:
                    self._result_cache.popitem(last=False)
        return result

    @staticmethod
    def _no_evidence(engine: str, reason: str) -> Finding:
        """"Could not measure" is 0.0 with zero confidence. It used to be a middle score
        of 0.5, which fusion treated as 50% similarity for any unrunnable pair."""
        return Finding(engine=engine, score=0.0, confidence=0.0, methodology=reason)

    def compare(self, parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> Finding:
        """
        Compare two code samples by executing and comparing outputs.

        Returns:
            A Finding object containing scores and evidence.
        """
        code_a = self._extract_code(parsed_a)
        code_b = self._extract_code(parsed_b)
        language = _normalize_language(parsed_a.get("language", parsed_b.get("language", "python")))

        if not code_a or not code_b:
            return Finding(engine=self.name, score=0.0, confidence=1.0)

        if not self._is_executable(code_a, language) or not self._is_executable(code_b, language):
            return self._no_evidence(self.name, "Execution comparison skipped: not executable")

        test_cases = self.test_generator.generate_test_cases(code_a, language)[: self.max_test_cases]
        if not test_cases:
            return self._no_evidence(self.name, "Execution comparison skipped: no test cases")

        matching = 0.0
        informative = 0
        for test_case in test_cases:
            result_a = self._run(code_a, language, test_case.input_data)
            result_b = self._run(code_b, language, test_case.input_data)

            if not (result_a.is_successful() and result_b.is_successful()):
                continue
            if not result_a.stdout and not result_b.stdout:
                continue  # nothing observable: not evidence of anything
            informative += 1

            if self._outputs_match(result_a, result_b):
                matching += 1.0
            else:
                matching += PARTIAL_CREDIT * self._output_similarity(result_a.stdout, result_b.stdout)

        if informative == 0:
            return self._no_evidence(
                self.name, "Execution comparison inconclusive: no test produced observable output"
            )

        score = matching / informative
        # Confidence reflects how many of the tests actually produced evidence.
        confidence = 0.88 * informative / len(test_cases)

        evidence = []
        if score > 0.8:
            evidence.append(
                EvidenceBlock(
                    engine=self.name,
                    score=score,
                    confidence=0.9,
                    a_snippet="Identical behavior on test cases",
                    b_snippet="Identical behavior on test cases",
                    transformation_notes=["Semantic behavior match (Type 4)"],
                )
            )

        return Finding(
            engine=self.name,
            score=min(1.0, max(0.0, score)),
            confidence=confidence,
            evidence_blocks=evidence,
            methodology=(
                f"Black-box execution comparison using sandbox isolation "
                f"({informative}/{len(test_cases)} tests observable)."
            ),
        )

    def _extract_code(self, parsed: dict[str, Any]) -> str:
        """Extract source code from parsed representation."""
        if parsed.get("raw"):
            return parsed["raw"]
        if parsed.get("code"):
            return parsed["code"]
        return ""

    def _is_executable(self, code: str, language: str) -> bool:
        """Check if code is likely to be executable."""
        language = _normalize_language(language)
        if language == "python":
            try:
                compile(code, "<string>", "exec")
                return True
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                return False

        indicators = [
            "def main",
            "if __name__",
            "public static void main",
            "func main",
            "int main",
            "input(",
            "print(",
            "System.out",
            "console.log",
        ]

        return any(ind in code for ind in indicators)

    def _outputs_match(self, result_a: ExecutionResult, result_b: ExecutionResult) -> bool:
        """Check if two execution outputs match."""
        if result_a.output_hash == result_b.output_hash:
            return True
        return self._normalize_output(result_a.stdout) == self._normalize_output(result_b.stdout)

    def _normalize_output(self, output: str) -> str:
        """Normalize output for comparison."""
        output = output.lower().strip()
        output = re.sub(r"\s+", " ", output)

        # Drop trailing zeros of decimal fractions: ``2.50`` -> ``2.5``, ``3.00`` -> ``3``.
        # The old pattern ``(\d+\.\d*?)0+`` also ate zeros in the MIDDLE of a fraction,
        # turning ``1.05`` into ``1.5`` and so declaring different results equal.
        output = re.sub(r"(\d+)\.0+(?![\d])", r"\1", output)
        output = re.sub(r"(\d+\.\d*?[1-9])0+(?![\d])", r"\1", output)
        return output

    def _output_similarity(self, output_a: str, output_b: str) -> float:
        """
        Calculate similarity between two outputs, in [0, 1].

        Uses sequence matching. The previous character-multiset overlap scored
        ``"42"`` against ``"24"`` as 1.0 (same characters, different order).
        """
        norm_a = self._normalize_output(output_a)
        norm_b = self._normalize_output(output_b)

        if not norm_a and not norm_b:
            return 1.0
        if not norm_a or not norm_b:
            return 0.0
        if norm_a == norm_b:
            return 1.0
        # bounded: SequenceMatcher is quadratic
        return SequenceMatcher(None, norm_a[:5000], norm_b[:5000], autojunk=False).ratio()
