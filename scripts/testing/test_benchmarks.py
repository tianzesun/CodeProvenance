#!/usr/bin/env python3
"""
Simple benchmark test script to verify setup.
"""

from pathlib import Path
import os
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_datasets():
    """Test dataset availability."""
    print("🧪 Testing Dataset Availability")
    print("=" * 40)

    datasets = {
        'BigCloneBench': 'data/datasets/bigclonebench',
        'POJ-104': 'data/datasets/poj104',
        'Synthetic': 'data/datasets/synthetic',
        'Kaggle Student': 'data/datasets/kaggle_student_code',
        'IR-Plag': 'data/datasets/IR-Plag-Dataset',
        'AI-SOCO': 'data/big_datasets/AI-SOCO',
        'MGTBench': 'data/datasets/MGTBench',
        'AICD-Bench': 'data/datasets/AICD-Bench',
        'PAN2025': 'data/big_datasets/pan2025',
        'PAN Plagiarism': 'data/big_datasets/pan-plagiarism-corpus-2011'
    }

    available = 0
    total_size = 0

    for name, path in datasets.items():
        if os.path.exists(path):
            # Get size
            try:
                size_bytes = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(path)
                    for filename in filenames
                )
                size_mb = size_bytes / (1024 * 1024)
                total_size += size_mb
                print(".1f")
                available += 1
            except:
                print(f"  ✅ {name}: Available")
                available += 1
        else:
            print(f"  ❌ {name}: Not found")

    print(f"\n📊 Summary: {available}/{len(datasets)} datasets available")
    print(".1f")
    return available, total_size

def test_benchmark_runner():
    """Test if benchmark runner can be imported."""
    print("\n🧪 Testing Benchmark Runner Import")
    print("=" * 40)

    try:
        from benchmark_runner import ComprehensiveBenchmarkRunner
        runner = ComprehensiveBenchmarkRunner()
        print("✅ Benchmark runner imports successfully")
        return True
    except Exception as e:
        print(f"❌ Benchmark runner failed: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 IntegrityDesk Dataset & Benchmark Test Suite")
    print("=" * 60)

    # Test datasets
    available, total_size = test_datasets()

    # Test benchmark runner
    runner_works = test_benchmark_runner()

    # Summary
    print("\n📋 Test Results:")
    print(f"  Datasets: {available}/10 available ({total_size:.1f}MB)")
    print(f"  Benchmark Runner: {'✅ Working' if runner_works else '❌ Broken'}")

    if available >= 8 and runner_works:
        print("\n🎉 READY FOR BENCHMARKING!")
        print("Run: python benchmark_runner.py")
    else:
        print("\n⚠️  Some components need attention before benchmarking")

if __name__ == "__main__":
    main()