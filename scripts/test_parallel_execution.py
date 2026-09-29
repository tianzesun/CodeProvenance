"""Test parallel execution performance improvement."""

import time
from src.backend.application.services.batch_detection_service import BatchDetectionService

# Sample code submissions
submissions = {
    f"student_{i}.py": f"""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

class Calculator_{i}:
    def add(self, a, b):
        return a + b
    
    def multiply(self, a, b):
        result = 0
        for _ in range(b):
            result += a
        return result
"""
    for i in range(15)  # 15 files = 105 pairs
}

print(f"Testing with {len(submissions)} submissions ({len(submissions) * (len(submissions) - 1) // 2} pairs)")

# Test sequential
print("\n=== Sequential Execution ===")
service_seq = BatchDetectionService(threshold=0.5)
start = time.time()
results_seq = service_seq.compare_all_pairs(submissions, use_parallel=False)
seq_time = time.time() - start
print(f"Time: {seq_time:.2f}s")
print(f"Results: {len(results_seq)} pairs")
print(f"Top score: {results_seq[0].score:.4f} ({results_seq[0].file_a} vs {results_seq[0].file_b})")

# Test parallel
print("\n=== Parallel Execution ===")
service_par = BatchDetectionService(threshold=0.5)
start = time.time()
results_par = service_par.compare_all_pairs(submissions, use_parallel=True, max_workers=8)
par_time = time.time() - start
print(f"Time: {par_time:.2f}s")
print(f"Results: {len(results_par)} pairs")
print(f"Top score: {results_par[0].score:.4f} ({results_par[0].file_a} vs {results_par[0].file_b})")

# Compare
speedup = seq_time / par_time if par_time > 0 else 0
print(f"\n=== Performance Improvement ===")
print(f"Sequential: {seq_time:.2f}s")
print(f"Parallel:   {par_time:.2f}s")
print(f"Speedup:    {speedup:.2f}x faster")
print(f"Target:     3-5x speedup")
print(f"Status:     {'✓ SUCCESS' if speedup >= 2.5 else '⚠ BELOW TARGET'}")

# Verify results match
print(f"\n=== Correctness Check ===")
scores_match = all(
    abs(r1.score - r2.score) < 0.001
    for r1, r2 in zip(sorted(results_seq, key=lambda x: (x.file_a, x.file_b)),
                       sorted(results_par, key=lambda x: (x.file_a, x.file_b)))
)
print(f"Scores match: {'✓ YES' if scores_match else '✗ NO'}")
