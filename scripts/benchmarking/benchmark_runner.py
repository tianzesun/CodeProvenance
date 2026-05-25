#!/usr/bin/env python3
"""
Comprehensive Benchmark Runner for Plagiarism Detection

This script runs comprehensive benchmarks across all available datasets
with robust error handling, progress tracking, and detailed reporting.

Author: IntegrityDesk
Version: 2.0.0
"""

import json
import time
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('benchmark.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class DatasetBenchmark:
    """Configuration for benchmarking a dataset."""
    name: str
    path: str
    expected_format: str
    primary_metric: str
    max_samples: int = 1000  # Limit samples for testing
    description: str = ""


@dataclass
class BenchmarkResult:
    """Detailed result for a single test case."""
    index: int
    computed_similarity: float
    expected_similarity: float
    is_correct: bool
    execution_time_ms: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkRun:
    """Results of a complete benchmark run."""
    dataset: str
    algorithm: str
    timestamp: str
    total_samples: int
    correct_predictions: int
    metrics: Dict[str, float]
    execution_time_seconds: float
    results_file: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ComprehensiveBenchmarkRunner:
    """
    Production-ready benchmark runner with comprehensive error handling
    and robust dataset loading.
    """

    def __init__(self, output_dir: str = "reports/benchmarks",
                 max_samples_per_dataset: int = 1000,
                 similarity_threshold: float = 0.5):
        """
        Initialize the benchmark runner.

        Args:
            output_dir: Directory to save reports and results
            max_samples_per_dataset: Maximum samples to test per dataset
            similarity_threshold: Threshold for binary classification
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_samples = max_samples_per_dataset
        self.threshold = similarity_threshold

        # Dataset configurations with improved metadata
        self.datasets = {
            'bigclonebench': DatasetBenchmark(
                name='BigCloneBench',
                path='data/datasets/bigclonebench',
                expected_format='directory_pairs',
                primary_metric='f1',
                description='Industry standard clone detection benchmark'
            ),
            'poj104': DatasetBenchmark(
                name='POJ-104',
                path='data/datasets/poj104',
                expected_format='directory_pairs',
                primary_metric='precision',
                description='Competition programming plagiarism cases'
            ),
            'synthetic': DatasetBenchmark(
                name='Synthetic Dataset',
                path='data/datasets/synthetic',
                expected_format='pairs_jsonl',
                primary_metric='accuracy',
                description='Controlled testing with advanced clone types'
            ),
            'kaggle_student': DatasetBenchmark(
                name='Kaggle Student Code',
                path='data/datasets/kaggle_student_code',
                expected_format='csv_pairs',
                primary_metric='recall',
                description='Real student plagiarism cases'
            ),
            'ir_plag': DatasetBenchmark(
                name='IR-Plag',
                path='data/datasets/IR-Plag-Dataset',
                expected_format='directory_pairs',
                primary_metric='f1',
                description='Human-created semantic plagiarism'
            ),
            'ai_soco': DatasetBenchmark(
                name='AI-SOCO',
                path='data/big_datasets/AI-SOCO',
                expected_format='csv_pairs',
                primary_metric='accuracy',
                description='Authorship identification from competitive coding'
            ),
            'mgtbench': DatasetBenchmark(
                name='MGTBench',
                path='data/datasets/MGTBench',
                expected_format='pairs_jsonl',
                primary_metric='precision',
                description='AI-generated text detection benchmark'
            ),
            'aicd_bench': DatasetBenchmark(
                name='AICD-Bench',
                path='data/datasets/AICD-Bench',
                expected_format='parquet_pairs',
                primary_metric='accuracy',
                description='Code vs text classification benchmark'
            )
        }

        logger.info(f"Benchmark runner initialized with {len(self.datasets)} datasets")

    def run_all_benchmarks(self, algorithms: List[str] = None,
                          datasets: List[str] = None) -> List[BenchmarkRun]:
        """
        Run benchmarks on specified datasets and algorithms.

        Args:
            algorithms: List of algorithm names to test
            datasets: List of dataset keys to test (None = all available)

        Returns:
            List of BenchmarkRun results
        """
        if algorithms is None:
            algorithms = ['integritydesk']

        if datasets is None:
            datasets = list(self.datasets.keys())

        all_results = []
        total_start_time = time.time()

        logger.info(f"Starting benchmark suite with {len(algorithms)} algorithms on {len(datasets)} datasets")

        for dataset_key in datasets:
            if dataset_key not in self.datasets:
                logger.warning(f"Dataset {dataset_key} not configured, skipping")
                continue

            dataset_config = self.datasets[dataset_key]

            if not Path(dataset_config.path).exists():
                logger.warning(f"Dataset {dataset_config.name} not found at {dataset_config.path}")
                continue

            logger.info(f"Running {dataset_config.name} benchmarks...")

            for algorithm in algorithms:
                try:
                    logger.info(f"Testing {algorithm} on {dataset_config.name}")
                    result = self.run_single_benchmark(dataset_config, algorithm)

                    # Log summary
                    primary_metric = dataset_config.primary_metric
                    score = result.metrics.get(primary_metric, result.metrics.get('accuracy', 0))
                    logger.info(".3f")

                    all_results.append(result)

                except Exception as e:
                    error_msg = f"Failed to run {algorithm} on {dataset_config.name}: {e}"
                    logger.error(error_msg)
                    logger.debug(f"Traceback: {traceback.format_exc()}")

                    # Create error result
                    error_result = BenchmarkRun(
                        dataset=dataset_config.name,
                        algorithm=algorithm,
                        timestamp=datetime.now().isoformat(),
                        total_samples=0,
                        correct_predictions=0,
                        metrics={'accuracy': 0.0},
                        execution_time_seconds=0.0,
                        errors=[error_msg]
                    )
                    all_results.append(error_result)

        total_time = time.time() - total_start_time
        logger.info(".2f")

        return all_results

    def run_single_benchmark(self, dataset: DatasetBenchmark, algorithm: str) -> BenchmarkRun:
        """
        Run benchmark for a specific dataset and algorithm with comprehensive error handling.
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()

        logger.debug(f"Loading dataset: {dataset.name}")

        try:
            # Load dataset with error handling
            test_cases = self.load_dataset(dataset)

            if not test_cases:
                raise ValueError(f"No test cases loaded for {dataset.name}")

            if len(test_cases) > self.max_samples:
                logger.info(f"Limiting {dataset.name} to {self.max_samples} samples (from {len(test_cases)})")
                test_cases = test_cases[:self.max_samples]

            total_samples = len(test_cases)
            logger.info(f"Testing {total_samples} samples from {dataset.name}")

        except Exception as e:
            error_msg = f"Failed to load dataset {dataset.name}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        results = []
        correct = 0
        errors = []
        warnings = []

        # Progress tracking
        progress_interval = max(1, total_samples // 10)  # Log every 10%

        for i, (code_a, code_b, expected_sim, metadata) in enumerate(test_cases):
            try:
                # Progress logging
                if i % progress_interval == 0:
                    progress = (i / total_samples) * 100
                    logger.debug(".1f")

                # Measure execution time
                exec_start = time.time()
                computed_sim = self.compute_similarity(code_a, code_b, algorithm)
                exec_time = (time.time() - exec_start) * 1000  # ms

                # Validate similarity score
                if not isinstance(computed_sim, (int, float)) or not (0.0 <= computed_sim <= 1.0):
                    warnings.append(f"Invalid similarity score at sample {i}: {computed_sim}")
                    computed_sim = 0.0  # Default fallback

                # Check correctness
                predicted_similar = computed_sim >= self.threshold
                expected_similar = expected_sim >= self.threshold
                is_correct = predicted_similar == expected_similar

                if is_correct:
                    correct += 1

                results.append(BenchmarkResult(
                    index=i,
                    computed_similarity=computed_sim,
                    expected_similarity=expected_sim,
                    is_correct=is_correct,
                    execution_time_ms=exec_time,
                    metadata=metadata
                ))

            except Exception as e:
                error_msg = f"Error processing sample {i}: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)

                results.append(BenchmarkResult(
                    index=i,
                    computed_similarity=0.0,
                    expected_similarity=expected_sim,
                    is_correct=False,
                    execution_time_ms=0.0,
                    error=str(e),
                    metadata=metadata
                ))

        # Calculate comprehensive metrics
        metrics = self.calculate_metrics(results, dataset.primary_metric)

        execution_time = time.time() - start_time

        # Save detailed results
        results_file = self.save_detailed_results(
            dataset.name, algorithm, timestamp, results, metrics
        )

        logger.info(f"Completed {dataset.name} benchmark in {execution_time:.2f}s")

        return BenchmarkRun(
            dataset=dataset.name,
            algorithm=algorithm,
            timestamp=timestamp,
            total_samples=total_samples,
            correct_predictions=correct,
            metrics=metrics,
            execution_time_seconds=execution_time,
            results_file=results_file,
            errors=errors,
            warnings=warnings
        )

    def compute_similarity(self, code_a: str, code_b: str, algorithm: str) -> float:
        """
        Compute similarity between two code snippets.

        This is where you integrate your actual plagiarism detection algorithm.
        Currently uses a simple token-based similarity for demonstration.
        """
        # TODO: Replace with your actual IntegrityDesk engine
        return self.simple_similarity(code_a, code_b)

    def simple_similarity(self, code_a: str, code_b: str) -> float:
        """Simple token-based similarity for demonstration."""
        import re

        def tokenize(code):
            # Basic tokenization
            tokens = re.findall(r'\b\w+\b', code.lower())
            return set(tokens)

        tokens_a = tokenize(code_a)
        tokens_b = tokenize(code_b)

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)

        return intersection / union

    def calculate_metrics(self, results: List[BenchmarkResult],
                         primary_metric: str) -> Dict[str, float]:
        """Calculate comprehensive evaluation metrics."""
        if not results:
            return {'accuracy': 0.0}

        correct = sum(1 for r in results if r.is_correct)
        total = len(results)

        accuracy = correct / total if total > 0 else 0.0

        # Calculate precision, recall, F1 for binary classification
        true_positives = sum(1 for r in results if r.expected_similarity >= self.threshold and r.is_correct)
        false_positives = sum(1 for r in results if r.expected_similarity < self.threshold and not r.is_correct)
        false_negatives = sum(1 for r in results if r.expected_similarity >= self.threshold and not r.is_correct)

        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Execution time statistics
        exec_times = [r.execution_time_ms for r in results if r.execution_time_ms > 0]
        avg_exec_time = sum(exec_times) / len(exec_times) if exec_times else 0.0

        metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'avg_execution_time_ms': avg_exec_time,
            'total_samples': total,
            'error_rate': len([r for r in results if r.error]) / total
        }

        return metrics

    def load_dataset(self, dataset: DatasetBenchmark) -> List[Tuple[str, str, float, Dict]]:
        """Load test cases from a dataset with robust error handling."""
        try:
            if dataset.expected_format == 'pairs_jsonl':
                return self.load_synthetic_jsonl(dataset)
            elif dataset.expected_format == 'directory_pairs':
                return self.load_directory_pairs(dataset)
            elif dataset.expected_format == 'csv_pairs':
                return self.load_csv_pairs(dataset)
            else:
                logger.warning(f"Unknown format {dataset.expected_format} for {dataset.name}")
                return []
        except Exception as e:
            logger.error(f"Error loading {dataset.name}: {e}")
            return []

    def load_synthetic_jsonl(self, dataset: DatasetBenchmark) -> List[Tuple[str, str, float, Dict]]:
        """Load synthetic dataset from JSONL format."""
        pairs = []
        jsonl_file = Path(dataset.path) / "generated_pairs_v2.0_final.jsonl"

        if not jsonl_file.exists():
            # Try alternative files
            for alt_file in ["generated_pairs_v2.0.jsonl", "generated_pairs.jsonl"]:
                alt_path = Path(dataset.path) / alt_file
                if alt_path.exists():
                    jsonl_file = alt_path
                    break

        if jsonl_file.exists():
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for pair in data['pairs'][:self.max_samples]:
                    pairs.append((
                        pair['code_a'],
                        pair['code_b'],
                        1.0 if pair.get('label', 0) == 1 else 0.0,
                        {
                            'clone_type': pair.get('clone_type', 0),
                            'source': 'synthetic'
                        }
                    ))
            except Exception as e:
                logger.warning(f"Error loading synthetic JSONL: {e}")

        return pairs

    def load_directory_pairs(self, dataset: DatasetBenchmark) -> List[Tuple[str, str, float, Dict]]:
        """Load dataset from directory structure."""
        pairs = []
        dataset_path = Path(dataset.path)

        # Different loading strategies based on dataset
        if 'bigclonebench' in dataset.path.lower():
            pairs = self.load_bigclonebench_pairs(dataset_path)
        elif 'ir-plag' in dataset.path.lower():
            pairs = self.load_ir_plag_pairs(dataset_path)
        else:
            # Generic directory loading
            pairs = self.load_generic_directory_pairs(dataset_path)

        return pairs[:self.max_samples]

    def load_bigclonebench_pairs(self, dataset_path: Path) -> List[Tuple[str, str, float, Dict]]:
        """Load BigCloneBench formatted pairs."""
        pairs = []

        # Look for clone and non-clone directories
        clone_dirs = list(dataset_path.glob("**/clones"))
        non_clone_dirs = list(dataset_path.glob("**/non_clones"))

        # Load clone pairs
        for clone_dir in clone_dirs:
            for pair_file in clone_dir.glob("*.txt"):
                try:
                    with open(pair_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Parse pair format (adjust based on actual format)
                        parts = content.split('===SEPARATOR===')
                        if len(parts) == 2:
                            pairs.append((parts[0], parts[1], 1.0, {'source': 'bigclonebench', 'type': 'clone'}))
                except Exception as e:
                    logger.debug(f"Error loading clone pair {pair_file}: {e}")

        # Load non-clone pairs for balance
        for non_clone_dir in non_clone_dirs:
            for pair_file in non_clone_dir.glob("*.txt"):
                try:
                    with open(pair_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        parts = content.split('===SEPARATOR===')
                        if len(parts) == 2:
                            pairs.append((parts[0], parts[1], 0.0, {'source': 'bigclonebench', 'type': 'non_clone'}))
                except Exception as e:
                    logger.debug(f"Error loading non-clone pair {pair_file}: {e}")

        return pairs

    def load_ir_plag_pairs(self, dataset_path: Path) -> List[Tuple[str, str, float, Dict]]:
        """Load IR-Plag formatted pairs."""
        pairs = []

        # IR-Plag has case directories with plagiarized pairs
        for case_dir in dataset_path.glob("case-*"):
            if case_dir.is_dir():
                # Load original and plagiarized files
                original_files = list(case_dir.glob("*.orig"))
                plag_files = list(case_dir.glob("*.plag"))

                for orig_file in original_files:
                    for plag_file in plag_files:
                        try:
                            with open(orig_file, 'r', encoding='utf-8') as f1, \
                                 open(plag_file, 'r', encoding='utf-8') as f2:
                                code_a = f1.read()
                                code_b = f2.read()

                            pairs.append((code_a, code_b, 1.0, {'case': case_dir.name, 'source': 'ir_plag'}))
                        except Exception as e:
                            logger.debug(f"Error loading IR-Plag pair {orig_file} vs {plag_file}: {e}")

        return pairs

    def load_generic_directory_pairs(self, dataset_path: Path) -> List[Tuple[str, str, float, Dict]]:
        """Generic directory pair loading."""
        pairs = []
        # Implementation for other directory-based datasets
        return pairs

    def load_csv_pairs(self, dataset: DatasetBenchmark) -> List[Tuple[str, str, float, Dict]]:
        """Load dataset from CSV format."""
        pairs = []

        if dataset.name == 'AI-SOCO':
            pairs = self.load_ai_soco_csv(dataset)
        elif dataset.name == 'Kaggle Student Code':
            pairs = self.load_kaggle_csv(dataset)
        else:
            # Generic CSV loading
            csv_file = Path(dataset.path) / "data.csv"
            if csv_file.exists():
                try:
                    import csv
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Generic CSV parsing (adjust columns as needed)
                            code_a = row.get('code_a', row.get('code1', ''))
                            code_b = row.get('code_b', row.get('code2', ''))
                            label = float(row.get('label', row.get('similarity', 0)))
                            pairs.append((code_a, code_b, label, {'source': dataset.name.lower()}))
                except Exception as e:
                    logger.warning(f"Error loading CSV {csv_file}: {e}")

        return pairs[:self.max_samples]

    def load_ai_soco_csv(self, dataset: DatasetBenchmark) -> List[Tuple[str, str, float, Dict]]:
        """Load AI-SOCO authorship pairs from CSV."""
        pairs = []
        csv_file = Path(dataset.path) / "data_dir" / "train.csv"

        if csv_file.exists():
            try:
                import csv
                author_codes = {}

                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        uid = row.get('uid')
                        pid = row.get('pid')

                        if uid not in author_codes:
                            author_codes[uid] = []

                        code_file = Path(dataset.path) / "data_dir" / "train" / f"{pid}.cpp"
                        if code_file.exists():
                            try:
                                with open(code_file, 'r', encoding='utf-8') as cf:
                                    code = cf.read()
                                    if len(code) > 100:  # Filter empty/short
                                        author_codes[uid].append(code)
                            except Exception as e:
                                logger.debug(f"Error loading AI-SOCO code {code_file}: {e}")

                # Create positive pairs (same author, different problems)
                for uid, codes in author_codes.items():
                    if len(codes) >= 2:
                        for i in range(len(codes)):
                            for j in range(i+1, len(codes)):
                                pairs.append((codes[i], codes[j], 1.0, {'author': uid, 'source': 'ai_soco'}))
                                if len(pairs) >= self.max_samples // 2:
                                    break
                            if len(pairs) >= self.max_samples // 2:
                                break
                    if len(pairs) >= self.max_samples:
                        break

            except Exception as e:
                logger.error(f"Error loading AI-SOCO dataset: {e}")

        return pairs

    def load_kaggle_csv(self, dataset: DatasetBenchmark) -> List[Tuple[str, str, float, Dict]]:
        """Load Kaggle student plagiarism pairs."""
        pairs = []
        csv_file = Path(dataset.path) / "cheating_dataset.csv"

        if csv_file.exists():
            try:
                import csv
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    count = 0
                    for row in reader:
                        if count >= self.max_samples:
                            break
                        try:
                            # Load code from files (assuming file paths in CSV)
                            file1_path = Path(dataset.path) / str(row.get('File_1', ''))
                            file2_path = Path(dataset.path) / str(row.get('File_2', ''))

                            if file1_path.exists() and file2_path.exists():
                                with open(file1_path, 'r', encoding='utf-8') as f1, \
                                     open(file2_path, 'r', encoding='utf-8') as f2:
                                    code_a = f1.read()
                                    code_b = f2.read()

                                label = 1.0 if int(row.get('Label', 0)) > 0 else 0.0
                                pairs.append((code_a, code_b, label, {'source': 'kaggle'}))
                                count += 1

                        except Exception as e:
                            logger.debug(f"Error loading Kaggle pair: {e}")
            except Exception as e:
                logger.warning(f"Error loading Kaggle dataset: {e}")

        return pairs

    def save_detailed_results(self, dataset_name: str, algorithm: str,
                            timestamp: str, results: List[BenchmarkResult],
                            metrics: Dict[str, float]) -> str:
        """Save detailed benchmark results to JSON file."""
        results_file = self.output_dir / f"{dataset_name.lower()}_{algorithm}_{timestamp.replace(':', '-')}.json"

        # Convert results to serializable format
        serializable_results = []
        for result in results:
            result_dict = {
                'index': result.index,
                'computed_similarity': result.computed_similarity,
                'expected_similarity': result.expected_similarity,
                'is_correct': result.is_correct,
                'execution_time_ms': result.execution_time_ms,
                'metadata': result.metadata
            }
            if result.error:
                result_dict['error'] = result.error
            serializable_results.append(result_dict)

        data = {
            'dataset': dataset_name,
            'algorithm': algorithm,
            'timestamp': timestamp,
            'metrics': metrics,
            'results': serializable_results
        }

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Detailed results saved to {results_file}")
        return str(results_file)

    def generate_report(self, results: List[BenchmarkRun]) -> str:
        """Generate comprehensive benchmark report."""
        reports_dir = self.output_dir
        report_path = reports_dir / f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Comprehensive Plagiarism Detection Benchmark Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Summary table
            f.write("## Summary Results\n\n")
            f.write("| Dataset | Algorithm | Primary Metric | Score | Samples | Time (s) |\n")
            f.write("|---------|-----------|----------------|-------|---------|----------|\n")

            for result in results:
                dataset_config = None
                for config in self.datasets.values():
                    if config.name == result.dataset:
                        dataset_config = config
                        break

                if dataset_config:
                    primary_metric = dataset_config.primary_metric
                    score = result.metrics.get(primary_metric, result.metrics.get('accuracy', 0))
                    f.write(".3f")

            f.write("\n## Detailed Results\n\n")

            for result in results:
                f.write(f"### {result.dataset} - {result.algorithm}\n\n")
                f.write(f"- **Total Samples**: {result.total_samples}\n")
                f.write(f"- **Correct Predictions**: {result.correct_predictions}\n")
                f.write(f"- **Execution Time**: {result.execution_time_seconds:.2f}s\n")
                f.write(f"- **Results File**: {result.results_file or 'N/A'}\n\n")

                # Metrics table
                f.write("#### Metrics\n\n")
                f.write("| Metric | Value |\n")
                f.write("|--------|-------|\n")
                for metric, value in result.metrics.items():
                    if isinstance(value, float):
                        f.write(".4f")
                    else:
                        f.write(f"| {metric} | {value} |\n")

                # Errors and warnings
                if result.errors:
                    f.write("\n#### Errors\n\n")
                    for error in result.errors[:5]:  # Show first 5 errors
                        f.write(f"- {error}\n")

                if result.warnings:
                    f.write("\n#### Warnings\n\n")
                    for warning in result.warnings[:5]:  # Show first 5 warnings
                        f.write(f"- {warning}\n")

                f.write("\n---\n\n")

        logger.info(f"Report generated: {report_path}")
        return str(report_path)


def main():
    """Main benchmark runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive Plagiarism Detection Benchmark Suite")
    parser.add_argument('--datasets', nargs='*', help='Specific datasets to test')
    parser.add_argument('--algorithms', nargs='*', default=['integritydesk'], help='Algorithms to test')
    parser.add_argument('--max-samples', type=int, default=1000, help='Maximum samples per dataset')
    parser.add_argument('--output-dir', default='reports/benchmarks', help='Output directory')

    args = parser.parse_args()

    print("🚀 Comprehensive Plagiarism Detection Benchmark Suite v2.0")
    print("=" * 70)

    try:
        runner = ComprehensiveBenchmarkRunner(
            output_dir=args.output_dir,
            max_samples_per_dataset=args.max_samples
        )

        print("📊 Available datasets:")
        for key, dataset in runner.datasets.items():
            exists = Path(dataset.path).exists()
            status = "✅ Available" if exists else "❌ Not found"
            print(f"  {key}: {dataset.name} - {status}")
            if dataset.description:
                print(f"    {dataset.description}")

        print("\n🏃 Running benchmarks...")
        print(f"  Datasets: {args.datasets or 'all available'}")
        print(f"  Algorithms: {args.algorithms}")
        print(f"  Max samples per dataset: {args.max_samples}")

        # Run benchmarks
        results = runner.run_all_benchmarks(
            algorithms=args.algorithms,
            datasets=args.datasets
        )

        print("\n📋 Generating report...")
        report_path = runner.generate_report(results)

        print(f"✅ Benchmark complete! Report saved to: {report_path}")

        # Print summary
        print("\n📊 Final Results Summary:")
        successful_runs = [r for r in results if r.total_samples > 0]
        if successful_runs:
            avg_accuracy = sum(r.metrics.get('accuracy', 0) for r in successful_runs) / len(successful_runs)
            total_samples = sum(r.total_samples for r in successful_runs)
            total_time = sum(r.execution_time_seconds for r in successful_runs)
            print(".3f")
            print(f"  Total execution time: {total_time:.2f}s")
        else:
            print("  No successful benchmark runs")

    except Exception as e:
        logger.error(f"Benchmark suite failed: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        print(f"❌ Benchmark suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()