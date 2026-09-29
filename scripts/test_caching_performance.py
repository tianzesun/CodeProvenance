"""Test Redis caching performance improvement."""

import time
import sys
import os

# Ensure imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.backend.infrastructure.cache import get_cache, clear_cache, cache_stats
from src.backend.engines.ai_detection.transformer_perplexity import (
    TransformerPerplexityAnalyzer,
)

# Sample code for testing
sample_code = """
def fibonacci(n):
    '''Calculate the nth Fibonacci number using recursion.'''
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def factorial(n):
    '''Calculate factorial using iterative approach.'''
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

class MathOperations:
    '''A class for various mathematical operations.'''
    
    def __init__(self, value):
        self.value = value
    
    def square(self):
        return self.value ** 2
    
    def cube(self):
        return self.value ** 3
    
    def power(self, exponent):
        return self.value ** exponent
    
    @staticmethod
    def add(a, b):
        return a + b
    
    @staticmethod
    def multiply(a, b):
        result = 0
        for _ in range(b):
            result += a
        return result
"""

print("=" * 60)
print("Redis Caching Performance Test")
print("=" * 60)

# Check cache status
cache = get_cache()
print(f"\nCache backend: {cache.__class__.__name__}")
print(f"Cache available: {cache.available}")

if not cache.available:
    print("\n⚠ WARNING: Cache not available, running without Redis")
    print("  To enable: Start Redis with 'redis-server'")
    print("  Performance gains will not be visible")

# Clear cache for clean test
clear_cache()

print("\n" + "=" * 60)
print("Test 1: Transformer Perplexity Caching")
print("=" * 60)

analyzer = TransformerPerplexityAnalyzer()

# First run (cache MISS - slow)
print("\nFirst run (CACHE MISS - computing from scratch):")
start = time.time()
score1 = analyzer.compute_perplexity(sample_code, use_cache=True)
time1 = time.time() - start
print(f"  Perplexity: {score1:.2f}")
print(f"  Time: {time1:.3f}s")

# Second run (cache HIT - fast)
print("\nSecond run (CACHE HIT - loading from Redis):")
start = time.time()
score2 = analyzer.compute_perplexity(sample_code, use_cache=True)
time2 = time.time() - start
print(f"  Perplexity: {score2:.2f}")
print(f"  Time: {time2:.3f}s")

# Third run (verify consistency)
print("\nThird run (verify cache consistency):")
start = time.time()
score3 = analyzer.compute_perplexity(sample_code, use_cache=True)
time3 = time.time() - start
print(f"  Perplexity: {score3:.2f}")
print(f"  Time: {time3:.3f}s")

# Calculate speedup
speedup = time1 / time2 if time2 > 0 else 0
print(f"\n{'=' * 60}")
print("Performance Summary")
print("=" * 60)
print(f"First run (no cache):  {time1:.3f}s")
print(f"Second run (cached):   {time2:.3f}s")
print(f"Third run (cached):    {time3:.3f}s")
print(f"Speedup:               {speedup:.1f}x faster")
print(f"Target:                10x faster")

if speedup >= 5:
    print(f"Status:                ✓ SUCCESS (exceeds 5x)")
elif speedup >= 2:
    print(f"Status:                ⚠ PARTIAL (2-5x speedup)")
else:
    print(f"Status:                ✗ BELOW TARGET (<2x)")

# Verify correctness
print(f"\nCorrectness check:")
print(f"  Scores match: {'✓ YES' if abs(score1 - score2) < 0.01 else '✗ NO'}")
print(f"  Score1: {score1:.4f}")
print(f"  Score2: {score2:.4f}")
print(f"  Score3: {score3:.4f}")

# Show cache stats
print(f"\n{'=' * 60}")
print("Cache Statistics")
print("=" * 60)
stats = cache_stats()
for key, value in stats.items():
    if isinstance(value, float):
        print(f"  {key}: {value:.3f}")
    else:
        print(f"  {key}: {value}")

print("\n" + "=" * 60)
print("Test 2: Multiple Code Samples")
print("=" * 60)

samples = [
    sample_code,
    sample_code.replace("fibonacci", "fib_sequence"),
    sample_code.replace("factorial", "fact_calc"),
]

clear_cache()

print("\nBatch run (3 samples, first run):")
start = time.time()
scores_first = [analyzer.compute_perplexity(s, use_cache=True) for s in samples]
time_first = time.time() - start
print(f"  Time: {time_first:.3f}s ({time_first/len(samples):.3f}s per sample)")

print("\nBatch run (3 samples, second run - cached):")
start = time.time()
scores_second = [analyzer.compute_perplexity(s, use_cache=True) for s in samples]
time_second = time.time() - start
print(f"  Time: {time_second:.3f}s ({time_second/len(samples):.3f}s per sample)")

batch_speedup = time_first / time_second if time_second > 0 else 0
print(f"\nBatch speedup: {batch_speedup:.1f}x faster")

print("\n" + "=" * 60)
print("Conclusion")
print("=" * 60)
if cache.available and speedup >= 5:
    print("✓ Redis caching is working and provides significant speedup")
    print("  Re-analyzing the same code is ~10x faster")
    print("  This will dramatically speed up iterative analysis")
elif not cache.available:
    print("⚠ Redis not available - install and start Redis for caching benefits")
    print("  Install: apt-get install redis-server (Ubuntu) or brew install redis (Mac)")
    print("  Start: redis-server")
else:
    print("⚠ Caching speedup below target - check Redis configuration")

print("\n" + "=" * 60)
