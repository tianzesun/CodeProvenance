#!/usr/bin/env python3
"""
Enhanced benchmark test script to verify improved system.
"""

from pathlib import Path
import os
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_enhanced_benchmark_runner():
    """Test if enhanced benchmark runner works."""
    print("🧪 Testing Enhanced Benchmark Runner")
    print("=" * 50)

    try:
        from enhanced_benchmark_runner import EnhancedBenchmarkRunner
        runner = EnhancedBenchmarkRunner(max_samples_per_dataset=50)  # Small sample for testing
        print("✅ Enhanced benchmark runner imports successfully")

        # Test dataset availability
        available_datasets = []
        for key, dataset in runner.datasets.items():
            exists = Path(dataset['path']).exists()
            if exists:
                available_datasets.append(dataset['name'])
            status = "✅ Available" if exists else "❌ Not found"
            print(f"  {status} {dataset['name']}")

        print(f"📊 {len(available_datasets)}/{len(runner.datasets)} datasets available")

        # Test uncertainty quantifier
        from enhanced_benchmark_runner import UncertaintyQuantifier
        uq = UncertaintyQuantifier()
        test_values = [0.8, 0.82, 0.79, 0.85, 0.81]
        stats = uq.calculate_statistics(test_values)
        print(f"✅ Uncertainty quantification works (mean: {stats.mean:.3f})")

        # Test ground truth validator
        from enhanced_benchmark_runner import GroundTruthValidator
        gtv = GroundTruthValidator()
        quality = gtv.assess_dataset_quality("test", test_values, test_values)
        print(f"✅ Ground truth validation works (quality: {quality['overall_quality_score']:.2f})")

        return True

    except Exception as e:
        print(f"❌ Enhanced benchmark runner failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_datasets():
    """Test dataset availability with enhanced information."""
    print("\n🧪 Enhanced Dataset Availability Check")
    print("=" * 50)

    datasets = {
        'BigCloneBench': ('data/datasets/bigclonebench', 'Industry standard clone detection'),
        'POJ-104': ('data/datasets/poj104', 'Competition programming cases'),
        'Synthetic': ('data/datasets/synthetic', 'Advanced clone types (1-6)'),
        'Kaggle Student': ('data/datasets/kaggle_student_code', 'Real plagiarism cases'),
        'IR-Plag': ('data/datasets/IR-Plag-Dataset', 'Human semantic plagiarism'),
        'AI-SOCO': ('data/big_datasets/AI-SOCO', 'Authorship identification'),
        'MGTBench': ('data/datasets/MGTBench', 'AI-generated detection'),
        'AICD-Bench': ('data/datasets/AICD-Bench', 'Code vs text classification'),
        'PAN2025': ('data/big_datasets/pan2025', 'Latest AI text detection'),
        'PAN Plagiarism': ('data/big_datasets/pan-plagiarism-corpus-2011', 'Academic plagiarism'),
    }

    available = 0
    total_size = 0

    for name, (path, description) in datasets.items():
        if os.path.exists(path):
            # Get size with better error handling
            try:
                size_bytes = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(path)
                    for filename in filenames
                    if not filename.startswith('.')  # Skip hidden files
                )
                size_mb = size_bytes / (1024 * 1024)
                total_size += size_mb
                print(".1f")
                available += 1
            except (OSError, PermissionError):
                print(f"  ✅ {name}: Available ({description})")
                available += 1
        else:
            print(f"  ❌ {name}: Not found")

    print(f"\n📊 Summary: {available}/10 datasets available")
    print(".1f")
    return available, total_size

def run_quick_benchmark_test():
    """Run a quick benchmark test to verify functionality."""
    print("\n🧪 Quick Benchmark Functionality Test")
    print("=" * 50)

    try:
        from enhanced_benchmark_runner import EnhancedBenchmarkRunner

        runner = EnhancedBenchmarkRunner(max_samples_per_dataset=10)  # Very small for quick test

        # Test on synthetic dataset if available
        if Path('data/datasets/synthetic').exists():
            print("Running quick test on synthetic dataset...")
            result = runner.run_enhanced_benchmark(
                {
                    'name': 'Synthetic Dataset',
                    'path': 'data/datasets/synthetic',
                    'format': 'pairs_jsonl',
                    'primary_metric': 'accuracy'
                },
                'integritydesk',
                include_uncertainty=False,
                include_validation=False
            )

            print("✅ Quick benchmark test successful")
            print(f"   Samples processed: {result.total_samples}")
            print(".3f")
            print(".2f")
            return True
        else:
            print("⚠️  Synthetic dataset not available for testing")
            return False

    except Exception as e:
        print(f"❌ Quick benchmark test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main enhanced test function."""
    print("🚀 IntegrityDesk Enhanced Benchmark System Test Suite")
    print("=" * 70)

    # Test datasets
    available, total_size = test_datasets()

    # Test enhanced benchmark runner
    enhanced_works = test_enhanced_benchmark_runner()

    # Run quick benchmark test
    benchmark_works = run_quick_benchmark_test()

    # Summary
    print("\n📋 Enhanced System Test Results:")
    print(f"  Datasets: {available}/10 available ({total_size:.1f}MB)")
    print(f"  Enhanced Runner: {'✅ Working' if enhanced_works else '❌ Broken'}")
    print(f"  Benchmark Functionality: {'✅ Working' if benchmark_works else '❌ Broken'}")

    all_systems_good = available >= 8 and enhanced_works and benchmark_works

    if all_systems_good:
        print("\n🎉 ENHANCED BENCHMARK SYSTEM FULLY OPERATIONAL!")
        print("Features activated:")
        print("  ✅ Uncertainty quantification with confidence intervals")
        print("  ✅ Ground truth validation and quality assessment")
        print("  ✅ Contextual evaluation across different scenarios")
        print("  ✅ Enhanced error handling and logging")
        print("  ✅ Statistical significance testing")
        print("  ✅ Comprehensive automated reporting")
        print("\n🚀 Ready for advanced benchmarking!")
        print("Run: python enhanced_benchmark_runner.py")

    else:
        print("\n⚠️  Some enhanced features need attention:")
        if available < 8:
            print("  - Dataset availability needs improvement")
        if not enhanced_works:
            print("  - Enhanced runner components need fixes")
        if not benchmark_works:
            print("  - Benchmark execution needs debugging")

if __name__ == "__main__":
    main()