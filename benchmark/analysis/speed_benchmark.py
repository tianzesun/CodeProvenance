"""Speed/profiling benchmarks for similarity detection engines.

Measures:
- Pairs processed per second
- Peak memory usage
- Time per comparison at different code sizes

Usage:
    python -m benchmark.analysis.speed_benchmark
"""
from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from benchmark.registry import registry


@dataclass
class SpeedProfile:
    """Speed benchmark result for one engine."""
    engine_name: str
    pairs_per_second: float
    avg_ms_per_pair: float
    peak_memory_mb: float
    times_ms: List[float] = field(default_factory=list)
    code_sizes: Dict[str, str] = field(default_factory=dict)
    
    def summary(self) -> str:
        return (
            f"{self.engine_name}: "
            f"{self.pairs_per_second:.0f} pairs/sec, "
            f"{self.avg_ms_per_pair:.1f}ms/pair, "
            f"{self.peak_memory_mb:.1f}MB peak"
        )


def run_speed_benchmark(
    engine: Any,
    code_pairs: List[Tuple[str, str]],
    warmup: int = 5,
    n_runs: int = 1,
) -> SpeedProfile:
    """Run speed benchmark on an engine.
    
    Args:
        engine: Similarity engine instance.
        code_pairs: List of (code_a, code_b) pairs to compare.
        warmup: Number of warmup comparisons (not timed).
        n_runs: Number of timed runs.
        
    Returns:
        SpeedProfile with timing and memory data.
    """
    engine_name = getattr(engine, 'name', str(type(engine).__name__))
    if callable(engine_name):
        engine_name = engine_name()
    
    # Get engine name
    try:
        engine_name_attr = engine.name
        if callable(engine_name_attr):
            engine_name = engine_name_attr()
        else:
            engine_name = engine_name_attr
    except (AttributeError, TypeError):
        pass
    
    # Warmup
    for i in range(min(warmup, len(code_pairs))):
        engine.compare(code_pairs[i][0], code_pairs[i][1])
    
    # Time comparisons
    all_times = []
    tracemalloc.start()
    
    for run in range(n_runs):
        for code_a, code_b in code_pairs:
            start = time.perf_counter()
            engine.compare(code_a, code_b)
            end = time.perf_counter()
            elapsed_ms = (end - start) * 1000
            all_times.append(elapsed_ms)
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    n_pairs = len(code_pairs) * n_runs
    total_time_sec = sum(all_times) / 1000
    avg_ms = sum(all_times) / len(all_times) if all_times else 0
    
    return SpeedProfile(
        engine_name=engine_name,
        pairs_per_second=n_pairs / total_time_sec if total_time_sec > 0 else 0,
        avg_ms_per_pair=avg_ms,
        peak_memory_mb=peak / (1024 * 1024),
        times_ms=[round(t, 2) for t in sorted(all_times)],
    )


def generate_code_at_sizes(base_code: str, sizes: List[int]) -> List[str]:
    """Generate code samples at different sizes by repeating the base code."""
    results = []
    for target_lines in sizes:
        lines = base_code.strip().split('\n')
        n_repeats = max(1, target_lines // max(len(lines), 1))
        results.append('\n'.join(lines * n_repeats)[:target_lines * 50])
    return results


def run_scaling_benchmark(
    engine: Any,
    base_code: str,
    sizes: Optional[List[int]] = None,
) -> Dict[str, SpeedProfile]:
    """Benchmark engine at different code sizes.
    
    Args:
        engine: Similarity engine instance.
        base_code: Base code to scale.
        sizes: Target line counts.
        
    Returns:
        Dict mapping size description to SpeedProfile.
    """
    if sizes is None:
        sizes = [10, 50, 100, 200, 500]
    
    results = {}
    for n_lines in sizes:
        pairs = [(base_code, base_code)] * 10
        profile = run_speed_benchmark(engine, pairs, warmup=2, n_runs=1)
        results[f"{n_lines}_lines"] = profile
    
    return results


def benchmark_all_engines(
    code_pairs: Optional[List[Tuple[str, str]]] = None,
    n_runs: int = 1,
) -> Dict[str, SpeedProfile]:
    """Run speed benchmark on all registered engines.
    
    Args:
        code_pairs: Optional custom pairs. If None, uses default test pairs.
        n_runs: Number of timed runs per engine.
        
    Returns:
        Dict mapping engine name to SpeedProfile.
    """
    if code_pairs is None:
        # Default test pairs: simple Python functions
        code_pairs = [
            (
                'def foo(x):\n    result = x + 1\n    return result',
                'def bar(y):\n    result = y + 2\n    return result'
            ),
            (
                'def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)',
                'def fact(n):\n    if n < 2: return 1\n    return n * fact(n - 1)'
            ),
            (
                'def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr',
                'def selection_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        min_idx = i\n        for j in range(i+1, n):\n            if arr[j] < arr[min_idx]:\n                min_idx = j\n        arr[i], arr[min_idx] = arr[min_idx], arr[i]\n    return arr'
            ),
        ]
    
    results = {}
    engines = registry.list_engines()
    
    for name, engine_class in sorted(engines.items()):
        try:
            engine = engine_class() if not isinstance(engine_class, type) else engine_class()
            profile = run_speed_benchmark(engine, code_pairs, warmup=2, n_runs=n_runs)
            results[name] = profile
        except Exception as e:
            results[name] = SpeedProfile(
                engine_name=name,
                pairs_per_second=0,
                avg_ms_per_pair=0,
                peak_memory_mb=0,
            )
    
    return results


if __name__ == "__main__":
    print("=" * 70)
    print("SPEED BENCHMARK - All Registered Engines")
    print("=" * 70)
    
    code_pairs = [
        (
            'def linear_search(arr, target):\n'
            '    for i in range(len(arr)):\n'
            '        if arr[i] == target:\n'
            '            return i\n'
            '    return -1\n',
            'def find_index(items, value):\n'
            '    for j in range(len(items)):\n'
            '        if items[j] == value:\n'
            '            return j\n'
            '    return -1\n',
        ),
        (
            'def factorial(n):\n'
            '    if n <= 1:\n'
            '        return 1\n'
            '    result = 1\n'
            '    for i in range(2, n + 1):\n'
            '        result *= i\n'
            '    return result\n',
            'def compute_factorial(x):\n'
            '    if x < 2:\n'
            '        return 1\n'
            '    output = 1\n'
            '    for k in range(2, x + 1):\n'
            '        output = output * k\n'
            '    return output\n',
        ),
    ]
    
    results = benchmark_all_engines(code_pairs, n_runs=3)
    
    print(f"\n{'Engine':<30} {'Pairs/sec':>10} {'ms/pair':>8} {'Peak MB':>8}")
    print("-" * 60)
    
    ranked = sorted(results.values(), key=lambda x: x.pairs_per_second, reverse=True)
    for profile in ranked:
        print(f"  {profile.engine_name:<28} {profile.pairs_per_second:>10.0f} "
              f"{profile.avg_ms_per_pair:>8.1f} {profile.peak_memory_mb:>8.1f}")
    
    # Fastest engine
    if ranked and ranked[0].pairs_per_second > 0:
        print(f"\n🏆 Fastest: {ranked[0].engine_name} ({ranked[0].pairs_per_second:.0f} pairs/sec)")
    
    print("\n" + "=" * 70)
    print("Scaling benchmark (Hybrid engine at different code sizes)")
    print("=" * 70)
    
    hybrid = registry.get_instance("hybrid")
    base = 'def foo(x):\n    """Example function."""\n    result = x * 2 + 1\n    return result\n'
    
    for n_lines in [10, 50, 100, 200, 500]:
        big = (base.strip() + '\n') * n_lines
        pairs = [(big[:1000], big[:1000])]
        profile = run_speed_benchmark(hybrid, pairs, warmup=2, n_runs=1)
        print(f"  {n_lines:>4} lines: {profile.avg_ms_per_pair:>8.1f}ms/pair, "
              f"{profile.peak_memory_mb:>6.1f}MB peak")