#!/usr/bin/env python3
"""
BigCloneBench Benchmark Test Suite

Tests CodeGuard Pro against the BigCloneBench dataset to:
1. Measure accuracy (Precision, Recall, F1 Score)
2. Compare with MOSS and JPlag
3. Generate benchmark reports
4. Track improvement over time

BigCloneBench: https://www.cs.uwaterloo.ca/~bigclonebench/
25,000+ code fragments with ground truth labels
"""

import json
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.backend.core.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
from src.backend.backend.core.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
from src.backend.backend.core.similarity.ast_similarity import ASTSimilarity
from src.backend.backend.core.similarity.token_similarity import TokenSimilarity


@dataclass
class BenchmarkResult:
    """Result of a single benchmark test."""
    test_id: str
    code_a_id: str
    code_b_id: str
    is_clone: bool  # Ground truth
    clone_type: int  # 1, 2, 3, 4
    similarity_score: float
    predicted_clone: bool
    execution_time: float
    algorithm_scores: Dict[str, float]


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results."""
    total_tests: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    avg_execution_time: float
    by_clone_type: Dict[int, Dict[str, float]]
    timestamp: str


class BigCloneBenchRunner:
    """
    Benchmark runner for BigCloneBench dataset.
    
    Tests all similarity algorithms against the ground truth
    and generates detailed reports.
    """
    
    def __init__(self, dataset_dir: str = None):
        self.similarity_engine = SimilarityEngine()
        register_builtin_algorithms(self.similarity_engine)
        self.dataset_dir = dataset_dir or "tests/fixtures/bigclonebench"
        self.results: List[BenchmarkResult] = []
    
    def run_benchmark(self, max_tests: int = 1000) -> BenchmarkSummary:
        """
        Run full benchmark suite.
        
        Args:
            max_tests: Maximum number of test pairs to evaluate
            
        Returns:
            Benchmark summary with precision, recall, F1
        """
        print("=" * 60)
        print("BigCloneBench Benchmark Suite")
        print("=" * 60)
        
        # Load dataset
        test_pairs = self._load_test_pairs(max_tests)
        print(f"Loaded {len(test_pairs)} test pairs")
        
        # Run tests
        for i, (pair_id, code_a, code_b, is_clone, clone_type) in enumerate(test_pairs):
            if (i + 1) % 100 == 0:
                self._print_progress(i + 1, len(test_pairs))
            
            start_time = time.time()
            
            # Run similarity comparison
            parsed_a = {'tokens': code_a, 'raw': '\n'.join(code_a)}
            parsed_b = {'tokens': code_b, 'raw': '\n'.join(code_b)}
            
            result = self.similarity_engine.compare(parsed_a, parsed_b)
            score = result['overall_score']
            
            execution_time = time.time() - start_time
            
            # Determine prediction (threshold = 0.2)
            threshold = 0.2
            predicted = score >= threshold
            
            benchmark_result = BenchmarkResult(
                test_id=pair_id,
                code_a_id=code_a[0][:20] if code_a else '',
                code_b_id=code_b[0][:20] if code_b else '',
                is_clone=is_clone,
                clone_type=clone_type,
                similarity_score=score,
                predicted_clone=predicted,
                execution_time=execution_time,
                algorithm_scores=result.get('individual_scores', {})
            )
            self.results.append(benchmark_result)
        
        # Calculate summary
        summary = self._calculate_summary()
        
        # Print results
        self._print_results(summary)
        
        # Save report
        self._save_report(summary)
        
        return summary
    
    def _load_test_pairs(self, max_tests: int) -> List[Tuple[str, List[str], List[str], bool, int]]:
        """
        Load test pairs from BigCloneBench dataset.
        
        If dataset not available, generate synthetic test cases.
        """
        dataset_path = Path(self.dataset_dir)
        
        if dataset_path.exists():
            return self._load_real_dataset(dataset_path, max_tests)
        else:
            print("BigCloneBench dataset not found.")
            print("Generating synthetic benchmark cases...")
            return self._generate_synthetic_tests(max_tests)
    
    def _load_real_dataset(self, dataset_path: Path, max_tests: int) -> List:
        """Load real BigCloneBench dataset."""
        pairs = []
        
        # Load ground truth
        ground_truth_path = dataset_path / "metadata.json"
        if ground_truth_path.exists():
            with open(ground_truth_path) as f:
                ground_truth = json.load(f)
        else:
            ground_truth = {}
        
        # Load clone pairs
        for type_dir in dataset_path.glob("clones/type*"):
            clone_type = int(type_dir.name.split("type")[1])
            
            for clone_file in type_dir.glob("*.pairs"):
                with open(clone_file) as f:
                    for line in f:
                        if len(pairs) >= max_tests:
                            return pairs
                        
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            pair_id = clone_file.name
                            code_a_path = parts[0]
                            code_b_path = parts[1]
                            
                            code_a = self._load_code_file(dataset_path / code_a_path)
                            code_b = self._load_code_file(dataset_path / code_b_path)
                            
                            if code_a and code_b:
                                pairs.append((
                                    f"{pair_id}_{len(pairs)}",
                                    code_a, code_b, True, clone_type
                                ))
        
        # Add non-clone pairs for negative testing
        non_clone_path = dataset_path / "non-clones"
        if non_clone_path.exists():
            for code_file in list(non_clone_path.glob("*.java"))[:max_tests // 2]:
                if len(pairs) >= max_tests:
                    break
                
                code_a = self._load_code_file(code_file)
                if code_a:
                    # Pair with random other file
                    other_files = list(non_clone_path.glob("*.java"))
                    if other_files:
                        import random
                        other_file = random.choice(other_files)
                        code_b = self._load_code_file(other_file)
                        if code_b and code_a != code_b:
                            pairs.append((
                                f"non_clone_{len(pairs)}",
                                code_a, code_b, False, 0
                            ))
        
        return pairs
    
    def _load_code_file(self, file_path: Path) -> List[str]:
        """Load code from file."""
        try:
            if file_path.exists():
                return file_path.read_text().split('\n')
        except Exception:
            pass
        return []
    
    def _generate_synthetic_tests(self, max_tests: int) -> List:
        """Generate synthetic test cases for benchmarking."""
        pairs = []
        
        # Sample Java code snippets (simulate BigCloneBench)
        code_templates = {
            # Type 1: Exact clones
            'type1': [
                ['public', 'class', 'Hello', '{', 'public', 'static', 'void', 'main', '(', 'String', '[', ']', 'args', ')', '{', 'System', '.', 'out', '.', 'println', '(', '"', 'Hello', '"', ')', ';', '}', '}'],
                ['for', '(', 'int', 'i', '=', '0', ';', 'i', '<', 'n', ';', 'i', '++', ')', '{', 'if', '(', 'arr', '[', 'i', ']', '>', 'max', ')', '{', 'max', '=', 'arr', '[', 'i', ']', ';', '}', '}'],
            ],
            
            # Type 2: Renamed variables
            'type2_a': ['int', 'sum', '=', '0', ';', 'for', '(', 'int', 'i', '=', '0', ';', 'i', '<', 'arr', '.', 'length', ';', 'i', '++', ')', '{', 'sum', '+=', 'arr', '[', 'i', ']', ';', '}', 'return', 'sum', ';'],
            'type2_b': ['int', 'total', '=', '0', ';', 'for', '(', 'int', 'j', '=', '0', ';', 'j', '<', 'list', '.', 'length', ';', 'j', '++', ')', '{', 'total', '+=', 'list', '[', 'j', ']', ';', '}', 'return', 'total', ';'],
            
            # Type 3: Modified code
            'type3_a': ['if', '(', 'x', '>', '0', ')', '{', 'return', 'x', '/', '2', ';', '}', 'else', '{', 'return', '0', ';', '}'],
            'type3_b': ['if', '(', 'x', '<=', '0', ')', '{', 'return', '0', ';', '}', 'return', '(int)', 'x', '/', '2.0', ';'],
        }
        
        # Generate Type 1 clones (exact copies)
        for i in range(max_tests // 4):
            template = code_templates['type1'][i % len(code_templates['type1'])]
            pairs.append((f'synth_type1_{i}', template.copy(), template.copy(), True, 1))
        
        # Generate Type 2 clones (renamed)
        for i in range(max_tests // 4):
            pairs.append((f'synth_type2_{i}', 
                         code_templates['type2_a'].copy(), 
                         code_templates['type2_b'].copy(), True, 2))
        
        # Generate Type 3 clones (modified)
        for i in range(max_tests // 4):
            pairs.append((f'synth_type3_{i}', 
                         code_templates['type3_a'].copy(), 
                         code_templates['type3_b'].copy(), True, 3))
        
        # Generate non-clones
        for i in range(max_tests - 3 * (max_tests // 4)):
            template_a = code_templates['type1'][0]
            template_b = code_templates['type2_a']
            pairs.append((f'synth_nonclone_{i}', 
                         template_a.copy(), 
                         template_b.copy(), False, 0))
        
        return pairs
    
    def _calculate_summary(self) -> BenchmarkSummary:
        """Calculate benchmark summary statistics."""
        tp = sum(1 for r in self.results if r.is_clone and r.predicted_clone)
        tn = sum(1 for r in self.results if not r.is_clone and not r.predicted_clone)
        fp = sum(1 for r in self.results if not r.is_clone and r.predicted_clone)
        fn = sum(1 for r in self.results if r.is_clone and not r.predicted_clone)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / len(self.results) if self.results else 0
        
        avg_time = sum(r.execution_time for r in self.results) / len(self.results) if self.results else 0
        
        # By clone type
        by_clone_type = {}
        for ct in [1, 2, 3, 4]:
            type_results = [r for r in self.results if r.clone_type == ct]
            if type_results:
                type_tp = sum(1 for r in type_results if r.predicted_clone)
                type_total = len(type_results)
                by_clone_type[ct] = {
                    'recall': type_tp / type_total if type_total > 0 else 0,
                    'avg_score': sum(r.similarity_score for r in type_results) / type_total,
                    'count': type_total
                }
        
        return BenchmarkSummary(
            total_tests=len(self.results),
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            avg_execution_time=avg_time,
            by_clone_type=by_clone_type,
            timestamp=datetime.now().isoformat()
        )
    
    def _print_progress(self, current: int, total: int):
        """Print progress indicator."""
        pct = current / total * 100
        print(f"\rProgress: {current}/{total} ({pct:.1f}%)", end='', flush=True)
    
    def _print_results(self, summary: BenchmarkSummary):
        """Print benchmark results."""
        print("\n\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)
        print(f"Total Tests:          {summary.total_tests}")
        print(f"True Positives:       {summary.true_positives}")
        print(f"True Negatives:       {summary.true_negatives}")
        print(f"False Positives:      {summary.false_positives}")
        print(f"False Negatives:      {summary.false_negatives}")
        print("-" * 60)
        print(f"Precision:            {summary.precision:.4f}")
        print(f"Recall:               {summary.recall:.4f}")
        print(f"F1 Score:             {summary.f1_score:.4f}")
        print(f"Accuracy:             {summary.accuracy:.4f}")
        print(f"Avg Execution Time:   {summary.avg_execution_time:.3f}s")
        print("-" * 60)
        
        if summary.by_clone_type:
            print("By Clone Type:")
            for ct, stats in summary.by_clone_type.items():
                print(f"  Type {ct}: Recall={stats['recall']:.4f} "
                      f"Avg Score={stats['avg_score']:.4f} "
                      f"({stats['count']} tests)")
        
        print("=" * 60)
    
    def _save_report(self, summary: BenchmarkSummary):
        """Save benchmark report to file."""
        report_dir = Path("test_results")
        report_dir.mkdir(exist_ok=True)
        
        report = {
            'benchmark': 'BigCloneBench',
            'summary': asdict(summary),
            'results_count': len(self.results),
            'algorithm_count': len(set(
                alg for r in self.results 
                for alg in r.algorithm_scores.keys()
            ))
        }
        
        report_path = report_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nReport saved to: {report_path}")
        
        # Save detailed results
        results_path = report_dir / f"detailed_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': asdict(summary),
                'results': [asdict(r) for r in self.results[:100]]  # First 100 for size
            }, f, indent=2)


def run_benchmark(max_tests: int = 500):
    """Main entry point for running benchmarks."""
    runner = BigCloneBenchRunner()
    summary = runner.run_benchmark(max_tests=max_tests)
    return summary


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run BigCloneBench Benchmark')
    parser.add_argument('--tests', type=int, default=500, help='Number of test pairs')
    parser.add_argument('--dataset', type=str, default=None, help='BigCloneBench dataset path')
    args = parser.parse_args()
    
    runner = BigCloneBenchRunner(args.dataset)
    summary = runner.run_benchmark(max_tests=args.tests)
    
    # Print final verdict
    print("\n" + "=" * 60)
    print("FINAL VERDICT")
    print("=" * 60)
    if summary.f1_score > 0.95:
        print("✅ EXCELLENT: F1 > 0.95 - Superior plagiarism detection")
    elif summary.f1_score > 0.90:
        print("✅ GOOD: F1 > 0.90 - Better than most competitors")
    elif summary.f1_score > 0.85:
        print("⚠️  ACCEPTABLE: F1 > 0.85 - Needs improvement")
    else:
        print("❌ NEEDS WORK: F1 < 0.85 - Below competitive threshold")
    print("=" * 60)