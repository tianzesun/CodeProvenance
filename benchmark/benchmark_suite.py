"""
Benchmark Suite for IntegrityDesk.

Provides standardized test cases and accuracy metrics for evaluating
similarity detection performance.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict
import statistics


@dataclass
class TestCase:
    """A benchmark test case with ground truth."""
    id: str
    name: str
    description: str
    file_a: str
    file_b: str
    ground_truth_similarity: float  # Expected similarity (0.0 - 1.0)
    ground_truth_category: str  # 'identical', 'similar', 'different'
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result of running a benchmark test."""
    test_case_id: str
    computed_similarity: float
    ground_truth_similarity: float
    error: float  # |computed - ground_truth|
    is_correct: bool
    execution_time_ms: float
    category: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Overall benchmark report."""
    total_tests: int
    passed: int
    failed: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    mean_error: float
    mean_absolute_error: float
    rmse: float
    execution_time_ms: float
    results: List[BenchmarkResult]
    category_metrics: Dict[str, Dict[str, float]]
    algorithm_metrics: Dict[str, Dict[str, float]]


class BenchmarkSuite:
    """
    Benchmark suite for evaluating similarity detection accuracy.
    
    Includes:
    - Standardized test cases with ground truth
    - Accuracy metrics (precision, recall, F1)
    - Per-category performance analysis
    - Comparison with MOSS baselines
    """
    
    # Ground truth test cases
    DEFAULT_TEST_CASES = [
        # Identical code pairs (high similarity)
        TestCase(
            id="identical_python_1",
            name="Identical Python - Basic",
            description="Two exactly identical Python files",
            file_a="def add(a, b): return a + b",
            file_b="def add(a, b): return a + b",
            ground_truth_similarity=1.0,
            ground_truth_category="identical",
            language="python"
        ),
        TestCase(
            id="identical_java_1",
            name="Identical Java - Class",
            description="Two exactly identical Java classes",
            file_a="public class Test { public int add(int a, int b) { return a + b; } }",
            file_b="public class Test { public int add(int a, int b) { return a + b; } }",
            ground_truth_similarity=1.0,
            ground_truth_category="identical",
            language="java"
        ),
        
        # Renamed variables (high similarity)
        TestCase(
            id="renamed_python_1",
            name="Renamed Variables - Python",
            description="Same logic with different variable names (normalized AST detection)",
            file_a="def add(a, b): return a + b",
            file_b="def add(x, y): return x + y",
            ground_truth_similarity=0.70,
            ground_truth_category="similar",
            language="python"
        ),
        TestCase(
            id="renamed_python_2",
            name="Renamed Functions - Python",
            description="Same function with different names (normalized AST detection)",
            file_a="def calculate_sum(a, b): return a + b",
            file_b="def compute_total(x, y): return x + y",
            ground_truth_similarity=0.65,
            ground_truth_category="similar",
            language="python"
        ),
        
        # Refactored code (moderate similarity)
        TestCase(
            id="refactored_python_1",
            name="Refactored Loop - Python",
            description="Loop converted to list comprehension",
            file_a="result = []\nfor x in items:\n    result.append(x * 2)",
            file_b="result = [x * 2 for x in items]",
            ground_truth_similarity=0.70,
            ground_truth_category="similar",
            language="python"
        ),
        TestCase(
            id="refactored_python_2",
            name="Refactored If-Else - Python",
            description="If-else converted to ternary",
            file_a="if x > 0:\n    return True\nelse:\n    return False",
            file_b="return True if x > 0 else False",
            ground_truth_similarity=0.75,
            ground_truth_category="similar",
            language="python"
        ),
        
        # Similar structure (moderate similarity)
        TestCase(
            id="similar_structure_1",
            name="Similar Loop Structure",
            description="Same loop pattern with different operations",
            file_a="for i in range(n):\n    total += arr[i]",
            file_b="for i in range(n):\n    total *= arr[i]",
            ground_truth_similarity=0.60,
            ground_truth_category="similar",
            language="python"
        ),
        TestCase(
            id="similar_structure_2",
            name="Similar Function Structure",
            description="Same function pattern with different logic",
            file_a="def process(data):\n    result = []\n    for item in data:\n        result.append(item.strip())\n    return result",
            file_b="def process(data):\n    result = []\n    for item in data:\n        result.append(item.lower())\n    return result",
            ground_truth_similarity=0.65,
            ground_truth_category="similar",
            language="python"
        ),
        
        # Different code (low similarity)
        TestCase(
            id="different_python_1",
            name="Different Algorithms",
            description="Completely different algorithms",
            file_a="def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr",
            file_b="def quick_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quick_sort(left) + middle + quick_sort(right)",
            ground_truth_similarity=0.15,
            ground_truth_category="different",
            language="python"
        ),
        TestCase(
            id="different_python_2",
            name="Different Languages",
            description="Same algorithm in different styles",
            file_a="x = 5\ny = 10\nprint(x + y)",
            file_b="let x: i32 = 5;\nlet y: i32 = 10;\nprintln!(\"{}\", x + y);",
            ground_truth_similarity=0.20,
            ground_truth_category="different",
            language="python"
        ),
        TestCase(
            id="different_java_1",
            name="Different Java Implementations",
            description="Different approaches to same problem",
            file_a="public int sum(int[] arr) { int total = 0; for (int i = 0; i < arr.length; i++) { total += arr[i]; } return total; }",
            file_b="public int sum(int[] arr) { return Arrays.stream(arr).sum(); }",
            ground_truth_similarity=0.40,
            ground_truth_category="different",
            language="java"
        ),
        
        # Edge cases
        TestCase(
            id="empty_code",
            name="Empty Code",
            description="One empty file",
            file_a="",
            file_b="def foo(): pass",
            ground_truth_similarity=0.0,
            ground_truth_category="different",
            language="python"
        ),
        TestCase(
            id="whitespace_only",
            name="Whitespace Only",
            description="Files with only whitespace differences",
            file_a="def foo():\n    return 1",
            file_b="def foo():\n        return 1",
            ground_truth_similarity=0.95,
            ground_truth_category="similar",
            language="python"
        ),
        TestCase(
            id="comment_only",
            name="Comment Only",
            description="Files differing only in comments",
            file_a="# This adds two numbers\ndef add(a, b): return a + b",
            file_b="# Function to add numbers\ndef add(a, b): return a + b",
            ground_truth_similarity=0.95,
            ground_truth_category="similar",
            language="python"
        ),
        
        # Plagiarism patterns
        TestCase(
            id="plagiarism_copy_1",
            name="Direct Copy",
            description="Near-identical code with minor changes",
            file_a="def find_max(arr):\n    max_val = arr[0]\n    for val in arr:\n        if val > max_val:\n            max_val = val\n    return max_val",
            file_b="def find_max(arr):\n    max_val = arr[0]\n    for val in arr:\n        if val > max_val:\n            max_val = val\n    return max_val",
            ground_truth_similarity=0.98,
            ground_truth_category="identical",
            language="python"
        ),
        TestCase(
            id="plagiarism_template_1",
            name="Template Filling",
            description="Same template with different variable names",
            file_a="# Student A's submission\ndef process(data):\n    result = []\n    for item in data:\n        if item > 0:\n            result.append(item * 2)\n    return result",
            file_b="# Student B's submission\ndef process(data):\n    result = []\n    for num in data:\n        if num > 0:\n            result.append(num * 2)\n    return result",
            ground_truth_similarity=0.85,
            ground_truth_category="similar",
            language="python"
        ),
        TestCase(
            id="plagiarism_shuffle_1",
            name="Code Shuffle",
            description="Same logic in different order",
            file_a="a = 1\nb = 2\nc = 3\nresult = a + b + c",
            file_b="result = 1 + 2 + 3\n# just a test",
            ground_truth_similarity=0.40,
            ground_truth_category="different",
            language="python"
        ),
    ]
    
    def __init__(self, threshold_high: float = 0.7, threshold_low: float = 0.3):
        """
        Initialize benchmark suite.
        
        Args:
            threshold_high: Threshold for high similarity detection
            threshold_low: Threshold for low similarity detection
        """
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self.test_cases = self.DEFAULT_TEST_CASES.copy()
    
    def add_test_case(self, test_case: TestCase):
        """Add a custom test case."""
        self.test_cases.append(test_case)
    
    def load_test_cases_from_file(self, filepath: str):
        """Load test cases from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for item in data.get('test_cases', []):
            test_case = TestCase(
                id=item['id'],
                name=item['name'],
                description=item['description'],
                file_a=item['file_a'],
                file_b=item['file_b'],
                ground_truth_similarity=item['ground_truth_similarity'],
                ground_truth_category=item['ground_truth_category'],
                language=item.get('language', 'python'),
                metadata=item.get('metadata', {})
            )
            self.add_test_case(test_case)
    
    def save_test_cases_to_file(self, filepath: str):
        """Save current test cases to JSON file."""
        data = {
            'test_cases': [
                {
                    'id': tc.id,
                    'name': tc.name,
                    'description': tc.description,
                    'file_a': tc.file_a,
                    'file_b': tc.file_b,
                    'ground_truth_similarity': tc.ground_truth_similarity,
                    'ground_truth_category': tc.ground_truth_category,
                    'language': tc.language,
                    'metadata': tc.metadata
                }
                for tc in self.test_cases
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def run_benchmark(
        self,
        similarity_function,
        algorithm_name: str = "default"
    ) -> BenchmarkReport:
        """
        Run benchmark tests with a similarity function.
        
        Args:
            similarity_function: Function that takes (code_a, code_b) and returns similarity (0-1)
            algorithm_name: Name of the algorithm being tested
            
        Returns:
            BenchmarkReport with results
        """
        results = []
        category_results = defaultdict(list)
        start_time = time.time()
        
        for test_case in self.test_cases:
            try:
                # Measure execution time
                exec_start = time.time()
                computed = similarity_function(test_case.file_a, test_case.file_b)
                exec_time = (time.time() - exec_start) * 1000  # ms
                
                # Calculate error
                error = abs(computed - test_case.ground_truth_similarity)
                
                # Determine if classification is correct
                computed_category = self._categorize_similarity(computed)
                is_correct = computed_category == test_case.ground_truth_category
                
                result = BenchmarkResult(
                    test_case_id=test_case.id,
                    computed_similarity=computed,
                    ground_truth_similarity=test_case.ground_truth_similarity,
                    error=error,
                    is_correct=is_correct,
                    execution_time_ms=exec_time,
                    category=test_case.ground_truth_category,
                    metadata={'name': test_case.name, 'algorithm': algorithm_name}
                )
                
                results.append(result)
                category_results[test_case.ground_truth_category].append(result)
                
            except Exception as e:
                # Handle errors
                result = BenchmarkResult(
                    test_case_id=test_case.id,
                    computed_similarity=0.0,
                    ground_truth_similarity=test_case.ground_truth_similarity,
                    error=1.0,
                    is_correct=False,
                    execution_time_ms=0.0,
                    category=test_case.ground_truth_category,
                    metadata={'name': test_case.name, 'error': str(e)}
                )
                results.append(result)
        
        total_time = (time.time() - start_time) * 1000
        
        # Calculate metrics
        return self._calculate_metrics(results, category_results, total_time)
    
    def _categorize_similarity(self, similarity: float) -> str:
        """Categorize similarity score."""
        if similarity >= 0.8:
            return 'identical'
        elif similarity >= 0.4:
            return 'similar'
        else:
            return 'different'
    
    def _calculate_metrics(
        self,
        results: List[BenchmarkResult],
        category_results: Dict[str, List[BenchmarkResult]],
        total_time: float
    ) -> BenchmarkReport:
        """Calculate benchmark metrics."""
        total = len(results)
        passed = sum(1 for r in results if r.is_correct)
        failed = total - passed
        
        # Calculate errors
        errors = [r.error for r in results]
        mean_error = statistics.mean(errors) if errors else 0.0
        mae = mean_error  # Mean Absolute Error
        rmse = statistics.stdev(errors) if len(errors) > 1 else 0.0  # Root Mean Square Error
        
        # Calculate classification metrics
        # For each category, calculate true/false positives/negatives
        tp = sum(1 for r in results if r.is_correct and r.ground_truth_similarity >= 0.4)
        fp = sum(1 for r in results if not r.is_correct and r.computed_similarity >= 0.4)
        tn = sum(1 for r in results if r.is_correct and r.ground_truth_similarity < 0.4)
        fn = sum(1 for r in results if not r.is_correct and r.computed_similarity < 0.4)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = passed / total if total > 0 else 0.0
        
        # Per-category metrics
        category_metrics = {}
        for category, cat_results in category_results.items():
            cat_passed = sum(1 for r in cat_results if r.is_correct)
            cat_total = len(cat_results)
            cat_errors = [r.error for r in cat_results]
            
            category_metrics[category] = {
                'accuracy': cat_passed / cat_total if cat_total > 0 else 0.0,
                'mean_error': statistics.mean(cat_errors) if cat_errors else 0.0,
                'count': cat_total
            }
        
        # Per-algorithm metrics (same as overall for single algorithm)
        algorithm_metrics = {
            'default': {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'mae': mae,
                'rmse': rmse
            }
        }
        
        return BenchmarkReport(
            total_tests=total,
            passed=passed,
            failed=failed,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            mean_error=mean_error,
            mean_absolute_error=mae,
            rmse=rmse,
            execution_time_ms=total_time,
            results=results,
            category_metrics=category_metrics,
            algorithm_metrics=algorithm_metrics
        )
    
    def compare_algorithms(
        self,
        algorithms: Dict[str, callable]
    ) -> Dict[str, BenchmarkReport]:
        """
        Compare multiple similarity algorithms.
        
        Args:
            algorithms: Dictionary of algorithm_name -> similarity_function
            
        Returns:
            Dictionary of algorithm_name -> BenchmarkReport
        """
        return {
            name: self.run_benchmark(func, name)
            for name, func in algorithms.items()
        }
    
    def generate_report(self, report: BenchmarkReport, format: str = 'text') -> str:
        """
        Generate a benchmark report.
        
        Args:
            report: BenchmarkReport to format
            format: Output format ('text', 'json', 'markdown')
            
        Returns:
            Formatted report string
        """
        if format == 'json':
            return self._format_json(report)
        elif format == 'markdown':
            return self._format_markdown(report)
        else:
            return self._format_text(report)
    
    def _format_text(self, report: BenchmarkReport) -> str:
        """Format report as plain text."""
        lines = [
            "=" * 60,
            "IntegrityDesk Benchmark Report",
            "=" * 60,
            "",
            "OVERALL METRICS",
            "-" * 40,
            f"Total Tests:      {report.total_tests}",
            f"Passed:           {report.passed} ({report.passed/report.total_tests*100:.1f}%)",
            f"Failed:           {report.failed}",
            f"Accuracy:         {report.accuracy:.2%}",
            f"Precision:        {report.precision:.2%}",
            f"Recall:           {report.recall:.2%}",
            f"F1 Score:         {report.f1_score:.2%}",
            f"Mean Error:       {report.mean_error:.4f}",
            f"MAE:              {report.mean_absolute_error:.4f}",
            f"RMSE:             {report.rmse:.4f}",
            f"Execution Time:   {report.execution_time_ms:.2f}ms",
            "",
            "PER-CATEGORY METRICS",
            "-" * 40,
        ]
        
        for category, metrics in report.category_metrics.items():
            lines.append(
                f"{category.capitalize():15} Accuracy: {metrics['accuracy']:.2%}  "
                f"Mean Error: {metrics['mean_error']:.4f}  Count: {metrics['count']}"
            )
        
        lines.extend(["", "DETAILED RESULTS", "-" * 40])
        
        for result in sorted(report.results, key=lambda x: x.error, reverse=True):
            status = "✓" if result.is_correct else "✗"
            lines.append(
                f"{status} {result.test_case_id:25} "
                f"Computed: {result.computed_similarity:.3f}  "
                f"Expected: {result.ground_truth_similarity:.3f}  "
                f"Error: {result.error:.3f}  "
                f"({result.execution_time_ms:.2f}ms)"
            )
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def _format_json(self, report: BenchmarkReport) -> str:
        """Format report as JSON."""
        data = {
            'summary': {
                'total_tests': report.total_tests,
                'passed': report.passed,
                'failed': report.failed,
                'accuracy': report.accuracy,
                'precision': report.precision,
                'recall': report.recall,
                'f1_score': report.f1_score,
                'mean_error': report.mean_error,
                'mae': report.mean_absolute_error,
                'rmse': report.rmse,
                'execution_time_ms': report.execution_time_ms
            },
            'category_metrics': report.category_metrics,
            'algorithm_metrics': report.algorithm_metrics,
            'results': [
                {
                    'test_case_id': r.test_case_id,
                    'computed_similarity': r.computed_similarity,
                    'ground_truth_similarity': r.ground_truth_similarity,
                    'error': r.error,
                    'is_correct': r.is_correct,
                    'execution_time_ms': r.execution_time_ms,
                    'category': r.category
                }
                for r in report.results
            ]
        }
        return json.dumps(data, indent=2)
    
    def _format_markdown(self, report: BenchmarkReport) -> str:
        """Format report as Markdown."""
        lines = [
            "# IntegrityDesk Benchmark Report",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Tests | {report.total_tests} |",
            f"| Passed | {report.passed} ({report.passed/report.total_tests*100:.1f}%) |",
            f"| Failed | {report.failed} |",
            f"| Accuracy | {report.accuracy:.2%} |",
            f"| Precision | {report.precision:.2%} |",
            f"| Recall | {report.recall:.2%} |",
            f"| F1 Score | {report.f1_score:.2%} |",
            f"| MAE | {report.mean_absolute_error:.4f} |",
            f"| RMSE | {report.rmse:.4f} |",
            f"| Execution Time | {report.execution_time_ms:.2f}ms |",
            "",
            "## Per-Category Metrics",
            "",
            "| Category | Accuracy | Mean Error | Count |",
            "|----------|----------|------------|-------|",
        ]
        
        for category, metrics in report.category_metrics.items():
            lines.append(
                f"| {category.capitalize()} | {metrics['accuracy']:.2%} | "
                f"{metrics['mean_error']:.4f} | {metrics['count']} |"
            )
        
        lines.extend([
            "",
            "## Detailed Results",
            "",
            "| Test Case | Computed | Expected | Error | Status |",
            "|-----------|----------|----------|-------|--------|",
        ])
        
        for result in report.results:
            status = "✅" if result.is_correct else "❌"
            lines.append(
                f"| {result.test_case_id} | {result.computed_similarity:.3f} | "
                f"{result.ground_truth_similarity:.3f} | {result.error:.3f} | {status} |"
            )
        
        return "\n".join(lines)


def example_similarity_function(code_a: str, code_b: str) -> float:
    """
    Example similarity function for testing.
    
    This is a simple implementation for demonstration.
    In practice, use IntegrityDesk's actual similarity engine.
    """
    if not code_a or not code_b:
        return 0.0
    
    if code_a == code_b:
        return 1.0
    
    # Simple character-level similarity
    set_a = set(code_a.split())
    set_b = set(code_b.split())
    
    if not set_a or not set_b:
        return 0.0
    
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    
    return intersection / union if union > 0 else 0.0


# Convenience function for running benchmarks
def run_quick_benchmark(similarity_function=example_similarity_function) -> BenchmarkReport:
    """
    Run a quick benchmark with default test cases.
    
    Args:
        similarity_function: Function to benchmark
        
    Returns:
        BenchmarkReport
    """
    suite = BenchmarkSuite()
    return suite.run_benchmark(similarity_function, "quick_test")


def generate_comparison_report(
    algorithms: Dict[str, callable],
    output_format: str = 'markdown'
) -> str:
    """
    Generate a comparison report for multiple algorithms.
    
    Args:
        algorithms: Dictionary of algorithm_name -> similarity_function
        output_format: Output format ('text', 'json', 'markdown')
        
    Returns:
        Formatted comparison report
    """
    suite = BenchmarkSuite()
    results = suite.compare_algorithms(algorithms)
    
    # Generate comparison table
    lines = []
    
    if output_format == 'markdown':
        lines = ["# Algorithm Comparison Report", "", "| Algorithm | Accuracy | Precision | Recall | F1 | MAE |"]
        lines.append("|----------|---------|-----------|--------|----|-----|")
        
        for name, report in results.items():
            lines.append(
                f"| {name} | {report.accuracy:.2%} | {report.precision:.2%} | "
                f"{report.recall:.2%} | {report.f1_score:.2%} | {report.mean_absolute_error:.4f} |"
            )
    
    elif output_format == 'text':
        lines = ["Algorithm Comparison Report", "=" * 50, ""]
        for name, report in results.items():
            lines.append(f"{name}:")
            lines.append(f"  Accuracy: {report.accuracy:.2%}")
            lines.append(f"  F1 Score: {report.f1_score:.2%}")
            lines.append(f"  MAE:      {report.mean_absolute_error:.4f}")
            lines.append("")
    
    return "\n".join(lines)
