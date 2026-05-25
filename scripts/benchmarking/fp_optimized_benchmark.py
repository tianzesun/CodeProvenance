#!/usr/bin/env python3
"""
Enhanced Benchmark Runner with Optimized False Positive Control

This version includes:
- Configurable similarity thresholds
- False positive rate monitoring
- Precision-recall optimization
- Multi-threshold evaluation
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ThresholdAnalysis:
    """Analysis results for different thresholds."""
    threshold: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    false_negative_rate: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int


class FPOptimizedBenchmarkRunner:
    """
    Benchmark runner optimized for false positive control.
    """

    def __init__(self, output_dir: str = "reports/benchmarks",
                 default_threshold: float = 0.7):  # Higher default threshold
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_threshold = default_threshold

        # Thresholds to test for optimization
        self.test_thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        # Minimal dataset loading for demonstration
        self.sample_data = self._load_sample_data()

    def _load_sample_data(self) -> List[Tuple[str, str, float]]:
        """Load sample data for FP analysis."""
        return [
            # Clear clones (should be detected)
            ("def add(a, b): return a + b", "def sum(x, y): return x + y", 1.0),
            ("for i in range(10): print(i)", "for j in range(10): print(j)", 1.0),

            # Borderline cases (may or may not be plagiarism)
            ("def max(a, b): return a if a > b else b", "def maximum(x, y): return x if x > y else y", 0.8),
            ("result = []", "output = []", 0.6),

            # Clear non-clones (should not be detected)
            ("def add(a, b): return a + b", "def multiply(x, y): return x * y", 0.0),
            ("print('hello')", "console.log('world')", 0.0),
            ("import os", "from pathlib import Path", 0.0),
        ]

    def analyze_false_positives(self, algorithm_name: str = "token_similarity") -> Dict[str, Any]:
        """
        Comprehensive false positive analysis across multiple thresholds.
        """
        logger.info(f"Starting false positive analysis for {algorithm_name}")

        results = []
        for threshold in self.test_thresholds:
            logger.info(f"Testing threshold: {threshold}")

            threshold_result = self._evaluate_threshold(
                self.sample_data, threshold, algorithm_name
            )
            results.append(threshold_result)

        # Find optimal threshold (balances precision and recall)
        optimal_threshold = self._find_optimal_threshold(results)

        analysis = {
            'algorithm': algorithm_name,
            'timestamp': datetime.now().isoformat(),
            'threshold_analysis': [r.__dict__ for r in results],
            'optimal_threshold': optimal_threshold.__dict__,
            'recommendations': self._generate_fp_recommendations(results)
        }

        # Save analysis
        analysis_file = self.output_dir / f"fp_analysis_{algorithm_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2)

        logger.info(f"False positive analysis saved to {analysis_file}")
        return analysis

    def _evaluate_threshold(self, test_data: List[Tuple[str, str, float]],
                          threshold: float, algorithm: str) -> ThresholdAnalysis:
        """Evaluate performance at a specific threshold."""
        tp = fp = tn = fn = 0

        for code_a, code_b, ground_truth in test_data:
            similarity = self._compute_similarity(code_a, code_b, algorithm)

            predicted_positive = similarity >= threshold
            actually_positive = ground_truth >= 0.5  # Binary classification

            if predicted_positive and actually_positive:
                tp += 1
            elif predicted_positive and not actually_positive:
                fp += 1
            elif not predicted_positive and not actually_positive:
                tn += 1
            elif not predicted_positive and actually_positive:
                fn += 1

        # Calculate metrics
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
        false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0

        return ThresholdAnalysis(
            threshold=threshold,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn
        )

    def _compute_similarity(self, code_a: str, code_b: str, algorithm: str) -> float:
        """Compute similarity using specified algorithm."""
        if algorithm == "token_similarity":
            return self._token_similarity(code_a, code_b)
        elif algorithm == "semantic_similarity":
            return self._semantic_similarity(code_a, code_b)
        elif algorithm == "context_aware":
            return self._context_aware_similarity(code_a, code_b)
        else:
            return self._token_similarity(code_a, code_b)  # Default

    def _token_similarity(self, code_a: str, code_b: str) -> float:
        """Token-based similarity (current implementation)."""
        import re

        def tokenize(code):
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

    def _semantic_similarity(self, code_a: str, code_b: str) -> float:
        """Semantic similarity (placeholder for advanced implementation)."""
        # This would use AST analysis, semantic understanding, etc.
        # For now, return a more conservative estimate
        token_sim = self._token_similarity(code_a, code_b)

        # Reduce false positives by being more conservative
        if token_sim > 0.8:
            return min(token_sim, 0.9)  # Cap high similarities
        elif token_sim > 0.6:
            return token_sim * 0.8  # Reduce medium similarities
        else:
            return token_sim * 0.5  # Reduce low similarities

    def _context_aware_similarity(self, code_a: str, code_b: str) -> float:
        """Context-aware similarity considering function names, comments, etc."""
        base_similarity = self._token_similarity(code_a, code_b)

        # Bonus for similar function names
        func_name_sim = self._function_name_similarity(code_a, code_b)
        if func_name_sim > 0.8:
            base_similarity = min(1.0, base_similarity + 0.1)

        # Penalty for different contexts
        context_sim = self._context_similarity(code_a, code_b)
        if context_sim < 0.3:
            base_similarity *= 0.8

        return base_similarity

    def _function_name_similarity(self, code_a: str, code_b: str) -> float:
        """Extract and compare function names."""
        import re
        import difflib

        def extract_func_names(code):
            matches = re.findall(r'def\s+(\w+)\s*\(', code)
            return matches

        names_a = extract_func_names(code_a)
        names_b = extract_func_names(code_b)

        if not names_a or not names_b:
            return 0.0

        # Simple similarity check
        similarities = []
        for name_a in names_a:
            for name_b in names_b:
                ratio = difflib.SequenceMatcher(None, name_a, name_b).ratio()
                similarities.append(ratio)

        return max(similarities) if similarities else 0.0

    def _context_similarity(self, code_a: str, code_b: str) -> float:
        """Compare code context (imports, comments, etc.)."""
        # Simplified context comparison
        imports_a = len([line for line in code_a.split('\n') if line.strip().startswith('import')])
        imports_b = len([line for line in code_b.split('\n') if line.strip().startswith('import')])

        comments_a = len([line for line in code_a.split('\n') if '#' in line])
        comments_b = len([line for line in code_b.split('\n') if '#' in line])

        # Context similarity based on structural elements
        import_sim = 1.0 if abs(imports_a - imports_b) <= 1 else 0.5
        comment_sim = 1.0 if abs(comments_a - comments_b) <= 2 else 0.5

        return (import_sim + comment_sim) / 2

    def _find_optimal_threshold(self, results: List[ThresholdAnalysis]) -> ThresholdAnalysis:
        """Find the optimal threshold balancing precision and recall."""
        # Use F1 score as the optimization metric
        best_result = max(results, key=lambda r: r.f1)
        return best_result

    def _generate_fp_recommendations(self, results: List[ThresholdAnalysis]) -> List[str]:
        """Generate recommendations for false positive reduction."""
        recommendations = []

        # Find the result with lowest FP rate
        lowest_fp = min(results, key=lambda r: r.false_positive_rate)

        if lowest_fp.false_positive_rate < 0.1:
            recommendations.append(f"Use threshold {lowest_fp.threshold} for minimal false positives ({lowest_fp.false_positive_rate:.1f})")
        else:
            recommendations.append("Consider implementing semantic analysis to reduce false positives")

        # Check precision vs recall trade-off
        high_precision = max(results, key=lambda r: r.precision)
        high_recall = max(results, key=lambda r: r.recall)

        if high_precision.precision > 0.9:
            recommendations.append(f"Threshold {high_precision.threshold} provides excellent precision ({high_precision.precision:.2f})")

        # General recommendations
        recommendations.extend([
            "Implement multi-stage filtering (token → semantic → context)",
            "Add human review workflow for borderline cases",
            "Use ensemble methods to combine multiple similarity measures",
            "Consider domain-specific thresholds for different programming languages"
        ])

        return recommendations

    def run_optimized_benchmark(self, algorithm: str = "context_aware") -> Dict[str, Any]:
        """Run benchmark with optimized false positive control."""
        logger.info(f"Running optimized benchmark with {algorithm}")

        # First, analyze false positives to find optimal threshold
        fp_analysis = self.analyze_false_positives(algorithm)
        optimal_threshold = fp_analysis['optimal_threshold']['threshold']

        logger.info(f"Using optimal threshold: {optimal_threshold}")

        # Run benchmark with optimal threshold
        result = self._evaluate_threshold(
            self.sample_data, optimal_threshold, algorithm
        )

        # Generate comprehensive report
        report = {
            'algorithm': algorithm,
            'optimal_threshold': optimal_threshold,
            'performance': result.__dict__,
            'fp_analysis': fp_analysis,
            'recommendations': [
                f"Deploy with threshold {optimal_threshold} to minimize false positives",
                "Monitor false positive rate in production and adjust threshold as needed",
                "Consider A/B testing different thresholds with real users",
                "Implement gradual rollout with human oversight for high-stakes cases"
            ]
        }

        # Save report
        report_file = self.output_dir / f"optimized_benchmark_{algorithm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Optimized benchmark report saved to {report_file}")
        return report


def main():
    """Main FP optimization runner."""
    print("🎯 False Positive Optimization Benchmark")
    print("=" * 50)

    runner = FPOptimizedBenchmarkRunner()

    # Analyze false positives across algorithms and thresholds
    print("🔍 Analyzing false positive patterns...")
    fp_analysis = runner.analyze_false_positives("token_similarity")

    print("\n📊 False Positive Analysis Complete")
    print(f"Optimal threshold: {fp_analysis['optimal_threshold']['threshold']}")
    print(".3f")
    print(".3f")
    # Test different algorithms
    algorithms = ["token_similarity", "semantic_similarity", "context_aware"]

    print("\n🧪 Testing Different Algorithms:")
    for algorithm in algorithms:
        print(f"\n🔍 Testing {algorithm}...")
        result = runner.run_optimized_benchmark(algorithm)

        perf = result['performance']
        print(".3f")
        print(".3f")
        print(".3f")
    print("\n✅ False positive optimization complete!")
    print("Check reports/benchmarks/ for detailed analysis.")


if __name__ == "__main__":
    main()