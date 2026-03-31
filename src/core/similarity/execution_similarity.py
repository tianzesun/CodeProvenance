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
"""

from typing import List, Dict, Any, Optional, Tuple
from .base_similarity import BaseSimilarityAlgorithm
from collections import Counter
import hashlib
import subprocess
import tempfile
import os
import json
import time
import re


class ExecutionResult:
    """Result of code execution."""
    
    def __init__(self, stdout: str = '', stderr: str = '', 
                 exit_code: int = 0, execution_time: float = 0.0,
                 memory_used: float = 0.0, timed_out: bool = False):
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.memory_used = memory_used
        self.timed_out = timed_out
        self.output_hash = self._hash_output()
    
    def _hash_output(self) -> str:
        """Hash execution output for comparison."""
        combined = f"{self.stdout}:{self.exit_code}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def is_successful(self) -> bool:
        """Check if execution was successful."""
        return self.exit_code == 0 and not self.timed_out


class TestCase:
    """Represents a test case for execution."""
    
    def __init__(self, input_data: str = '', expected_output: str = '',
                 test_type: str = 'normal', description: str = ''):
        self.input_data = input_data
        self.expected_output = expected_output
        self.test_type = test_type
        self.description = description


class DockerSandbox:
    """
    Docker-based code execution sandbox.
    
    Provides secure, isolated execution with:
    - Resource limits (CPU, memory, time)
    - Network isolation
    - Filesystem restrictions
    """
    
    def __init__(self, timeout: int = 10, memory_limit: str = '256m',
                 cpu_limit: float = 0.5):
        """
        Initialize Docker sandbox.
        
        Args:
            timeout: Maximum execution time in seconds
            memory_limit: Memory limit (e.g., '256m', '1g')
            cpu_limit: CPU limit (0.0-1.0)
        """
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self._docker_available = self._check_docker()
    
    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def execute(self, code: str, language: str, 
                test_input: str = '') -> ExecutionResult:
        """
        Execute code in Docker sandbox.
        
        Args:
            code: Source code to execute
            language: Programming language
            test_input: Standard input for the program
            
        Returns:
            ExecutionResult with stdout, stderr, exit_code, etc.
        """
        if not self._docker_available:
            return self._execute_local(code, language, test_input)
        
        # Get Docker image for language
        image = self._get_docker_image(language)
        if not image:
            return self._execute_local(code, language, test_input)
        
        # Write code to temp file
        filename = self._get_filename(language)
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=os.path.splitext(filename)[1],
            delete=False
        ) as f:
            f.write(code)
            code_path = f.name
        
        try:
            # Build docker run command
            cmd = [
                'docker', 'run', '--rm',
                '-i',  # Interactive for stdin
                f'--memory={self.memory_limit}',
                f'--cpus={self.cpu_limit}',
                '--network=none',  # No network access
                '--read-only',  # Read-only filesystem
                '-v', f'{code_path}:/code/{filename}:ro',
                '-w', '/code',
                image
            ]
            
            # Add language-specific command
            run_cmd = self._get_run_command(language, filename)
            cmd.extend(run_cmd)
            
            # Execute
            start_time = time.time()
            try:
                result = subprocess.run(
                    cmd,
                    input=test_input,
                    capture_output=True, text=True,
                    timeout=self.timeout
                )
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    execution_time=execution_time,
                    timed_out=False
                )
                
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    stderr=f'Execution timed out after {self.timeout}s',
                    exit_code=-1,
                    execution_time=self.timeout,
                    timed_out=True
                )
        
        finally:
            # Cleanup temp file
            try:
                os.unlink(code_path)
            except OSError:
                pass
    
    def _execute_local(self, code: str, language: str, 
                       test_input: str = '') -> ExecutionResult:
        """Execute code locally (fallback when Docker unavailable)."""
        # Find interpreter for language
        interpreter = self._get_interpreter(language)
        if not interpreter:
            return ExecutionResult(
                stderr=f'Unsupported language: {language}',
                exit_code=-1
            )
        
        # Write code to temp file
        filename = self._get_filename(language)
        suffix = os.path.splitext(filename)[1]
        
        with tempfile.NamedTemporaryFile(
            mode='w', suffix=suffix, delete=False
        ) as f:
            f.write(code)
            code_path = f.name
        
        try:
            # Build command
            cmd = [interpreter, code_path]
            
            # Execute
            start_time = time.time()
            try:
                result = subprocess.run(
                    cmd,
                    input=test_input,
                    capture_output=True, text=True,
                    timeout=self.timeout
                )
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    execution_time=execution_time,
                    timed_out=False
                )
                
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    stderr=f'Execution timed out after {self.timeout}s',
                    exit_code=-1,
                    execution_time=self.timeout,
                    timed_out=True
                )
        
        finally:
            try:
                os.unlink(code_path)
            except OSError:
                pass
    
    def _get_docker_image(self, language: str) -> Optional[str]:
        """Get Docker image for language."""
        images = {
            'python': 'python:3.12-slim',
            'python3': 'python:3.12-slim',
            'java': 'eclipse-temurin:21-jre',
            'c': 'gcc:latest',
            'cpp': 'gcc:latest',
            'go': 'golang:latest',
            'rust': 'rust:slim',
            'javascript': 'node:20-slim',
            'ruby': 'ruby:3.3-slim',
            'php': 'php:8.3-cli',
            'perl': 'perl:latest',
        }
        return images.get(language.lower())
    
    def _get_interpreter(self, language: str) -> Optional[str]:
        """Get local interpreter for language."""
        interpreters = {
            'python': 'python3',
            'python3': 'python3',
            'javascript': 'node',
            'ruby': 'ruby',
            'perl': 'perl',
            'php': 'php',
            'bash': 'bash',
        }
        interpreter = interpreters.get(language.lower())
        if not interpreter:
            return None
        
        # Check if interpreter exists
        try:
            subprocess.run(
                [interpreter, '--version'],
                capture_output=True, timeout=5
            )
            return interpreter
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
    
    def _get_filename(self, language: str) -> str:
        """Get filename for language."""
        extensions = {
            'python': 'solution.py',
            'python3': 'solution.py',
            'java': 'Solution.java',
            'c': 'solution.c',
            'cpp': 'solution.cpp',
            'go': 'solution.go',
            'rust': 'solution.rs',
            'javascript': 'solution.js',
            'ruby': 'solution.rb',
            'php': 'solution.php',
        }
        return extensions.get(language.lower(), 'solution.txt')
    
    def _get_run_command(self, language: str, filename: str) -> List[str]:
        """Get command to run code in Docker."""
        commands = {
            'python': ['python3', filename],
            'python3': ['python3', filename],
            'java': ['javac', filename, '&&', 'java', 'Solution'],
            'c': ['gcc', '-o', 'solution', filename, '&&', './solution'],
            'cpp': ['g++', '-o', 'solution', filename, '&&', './solution'],
            'go': ['go', 'run', filename],
            'rust': ['rustc', filename, '-o', 'solution', '&&', './solution'],
            'javascript': ['node', filename],
            'ruby': ['ruby', filename],
            'php': ['php', filename],
        }
        cmd = commands.get(language.lower(), ['cat', filename])
        return ' '.join(cmd).split('&&')


class TestCaseGenerator:
    """
    Generates test cases for code execution comparison.
    
    Supports:
    - Standard input/output problems
    - Function-based problems
    - Edge cases
    """
    
    def __init__(self):
        self.test_cases: List[TestCase] = []
    
    def generate_test_cases(self, code: str, language: str) -> List[TestCase]:
        """
        Generate test cases based on code analysis.
        
        Args:
            code: Source code
            language: Programming language
            
        Returns:
            List of TestCase objects
        """
        test_cases = []
        
        # Analyze code structure
        analysis = self._analyze_code(code)
        
        if analysis['type'] == 'stdin_stdout':
            # Generate I/O test cases
            test_cases.extend(self._generate_io_tests(code))
        
        elif analysis['type'] == 'function':
            # Generate function test cases
            test_cases.extend(self._generate_function_tests(code))
        
        # Always add edge cases
        test_cases.extend(self._generate_edge_cases())
        
        return test_cases[:10]  # Limit to 10 test cases
    
    def _analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code structure."""
        result = {'type': 'unknown', 'functions': []}
        
        # Check for stdin/stdout patterns
        if any(p in code for p in [
            'input(', 'raw_input(', 'sys.stdin',
            'System.in', 'scanf', 'cin >>',
            'std::cin', 'console.ReadLine', 'bufio'
        ]):
            result['type'] = 'stdin_stdout'
        
        # Check for function definitions
        func_patterns = [
            r'def\s+(\w+)',          # Python
            r'(?:public\s+)?\w+\s+(\w+)\s*\(',  # Java/C/C++
            r'func\s+(\w+)',         # Go
            r'fn\s+(\w+)',           # Rust
        ]
        
        for pattern in func_patterns:
            functions = re.findall(pattern, code)
            if functions:
                result['functions'] = [f for f in functions if f not in ['main', '__init__']]
                if result['functions']:
                    result['type'] = 'function'
        
        return result
    
    def _generate_io_tests(self, code: str) -> List[TestCase]:
        """Generate I/O test cases."""
        test_cases = []
        
        # Common test inputs
        common_inputs = [
            # Simple numbers
            TestCase('5\n', '', 'simple', 'Single number'),
            TestCase('3 4 5\n', '', 'numbers', 'Space-separated'),
            TestCase('10\n20\n30\n', '', 'newlines', 'Newline-separated'),
            
            # Strings
            TestCase('hello world\n', '', 'string', 'Simple string'),
            
            # Arrays/lists
            TestCase('5\n1 2 3 4 5\n', '', 'array', 'Array with size'),
            
            # Empty/edge
            TestCase('0\n', '', 'empty', 'Zero/empty'),
            TestCase('1\n', '', 'minimal', 'Minimal input'),
        ]
        
        return common_inputs[:5]
    
    def _generate_function_tests(self, code: str) -> List[TestCase]:
        """Generate function test cases."""
        test_cases = []
        
        # For function-based problems, generate input variations
        inputs = [
            TestCase('1 2', '', 'small', 'Small values'),
            TestCase('100 200', '', 'medium', 'Medium values'),
            TestCase('0 0', '', 'zero', 'Zero values'),
            TestCase('-1 -2', '', 'negative', 'Negative values'),
        ]
        
        return inputs
    
    def _generate_edge_cases(self) -> List[TestCase]:
        """Generate edge case test cases."""
        return [
            TestCase('', '', 'empty', 'Empty input'),
            TestCase('\n', '', 'newline', 'Just newline'),
            TestCase(' ', '', 'whitespace', 'Whitespace only'),
            TestCase('a' * 100, '', 'long', 'Long string'),
        ]


class ExecutionSimilarity(BaseSimilarityAlgorithm):
    """
    Execution-based similarity algorithm.
    
    Compares code by executing both versions and comparing outputs.
    Detects Type 4 semantic clones - different code, same behavior.
    """
    
    def __init__(self, timeout: int = 10, memory_limit: str = '256m',
                 max_test_cases: int = 5):
        """
        Initialize Execution similarity algorithm.
        
        Args:
            timeout: Maximum execution time per test case
            memory_limit: Memory limit for execution
            max_test_cases: Maximum number of test cases
        """
        super().__init__("execution")
        self.sandbox = DockerSandbox(
            timeout=timeout,
            memory_limit=memory_limit
        )
        self.test_generator = TestCaseGenerator()
        self.max_test_cases = max_test_cases
    
    def compare(self, parsed_a: Dict[str, Any], 
                parsed_b: Dict[str, Any]) -> float:
        """
        Compare two code samples by executing and comparing outputs.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        code_a = self._extract_code(parsed_a)
        code_b = self._extract_code(parsed_b)
        language = parsed_a.get('language', parsed_b.get('language', 'python'))
        
        if not code_a or not code_b:
            return 0.0
        
        # Check if code is executable (has main logic)
        if not self._is_executable(code_a, language) or not self._is_executable(code_b, language):
            return 0.5  # Assume similar if can't execute
        
        # Generate test cases
        test_cases = self.test_generator.generate_test_cases(code_a, language)
        test_cases = test_cases[:self.max_test_cases]
        
        if not test_cases:
            return 0.5  # Default similarity
        
        # Execute both codes on each test case
        matching = 0
        total = len(test_cases)
        executed_successfully = 0
        
        for test_case in test_cases:
            result_a = self.sandbox.execute(code_a, language, test_case.input_data)
            result_b = self.sandbox.execute(code_b, language, test_case.input_data)
            
            # Both must succeed to compare
            if result_a.is_successful() and result_b.is_successful():
                executed_successfully += 1
                
                # Compare outputs
                if self._outputs_match(result_a, result_b):
                    matching += 1
                else:
                    # Partial credit for similar outputs
                    similarity = self._output_similarity(
                        result_a.stdout, result_b.stdout
                    )
                    matching += similarity
        
        if executed_successfully == 0:
            return 0.5  # Couldn't execute, assume neutral
        
        return matching / total
    
    def _extract_code(self, parsed: Dict[str, Any]) -> str:
        """Extract source code from parsed representation."""
        if 'raw' in parsed:
            return parsed['raw']
        if 'code' in parsed:
            return parsed['code']
        return ''
    
    def _is_executable(self, code: str, language: str) -> bool:
        """Check if code is likely to be executable."""
        # Check for syntax errors
        if language.lower() in ['python', 'python3']:
            try:
                compile(code, '<string>', 'exec')
                return True
            except SyntaxError:
                return False
        
        # Check for main logic indicators
        indicators = [
            'def main', 'if __name__',
            'public static void main',
            'func main',
            'int main',
            'input(', 'print(',
            'System.out', 'console.log',
        ]
        
        return any(ind in code for ind in indicators)
    
    def _outputs_match(self, result_a: ExecutionResult, 
                       result_b: ExecutionResult) -> bool:
        """Check if two execution outputs match."""
        # Exact match
        if result_a.output_hash == result_b.output_hash:
            return True
        
        # Normalize and compare
        norm_a = self._normalize_output(result_a.stdout)
        norm_b = self._normalize_output(result_b.stdout)
        
        return norm_a == norm_b
    
    def _normalize_output(self, output: str) -> str:
        """Normalize output for comparison."""
        # Lowercase
        output = output.lower()
        
        # Remove leading/trailing whitespace
        output = output.strip()
        
        # Normalize whitespace
        output = re.sub(r'\s+', ' ', output)
        
        # Remove trailing zeros from floats
        output = re.sub(r'(\d+\.\d*?)0+', r'\1', output)
        
        return output
    
    def _output_similarity(self, output_a: str, output_b: str) -> float:
        """
        Calculate similarity between two outputs.
        
        Returns partial credit for similar (but not identical) outputs.
        """
        norm_a = self._normalize_output(output_a)
        norm_b = self._normalize_output(output_b)
        
        if not norm_a and not norm_b:
            return 1.0
        if not norm_a or not norm_b:
            return 0.0
        
        # Exact match
        if norm_a == norm_b:
            return 1.0
        
        # Levenshtein-based similarity
        max_len = max(len(norm_a), len(norm_b))
        if max_len == 0:
            return 1.0
        
        # Simple character overlap
        chars_a = Counter(norm_a)
        chars_b = Counter(norm_b)
        
        common = sum((chars_a & chars_b).values())
        total = sum((chars_a | chars_b).values())
        
        return common / total if total > 0 else 0.0