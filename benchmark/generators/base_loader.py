"""Base code loader for dataset generation.

Loads raw code files from data/raw/ directory and provides
sampling utilities for generating code pairs.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import List, Optional, Tuple


class CodePool:
    """Pool of raw code files for generating pairs.
    
    Loads all Python files from the specified directory and
    provides methods to sample individual files or pairs.
    """
    
    def __init__(self, data_dir: str = "benchmark/data/raw", seed: int = 42):
        """Initialize the code pool.
        
        Args:
            data_dir: Directory containing raw code files.
            seed: Random seed for reproducibility.
        """
        self.data_dir = Path(data_dir)
        self.seed = seed
        self.rng = random.Random(seed)
        
        # Load all Python files
        self.files: List[Path] = []
        if self.data_dir.exists():
            self.files = list(self.data_dir.glob("**/*.py"))
        
        if not self.files:
            print(f"Warning: No Python files found in {data_dir}")
            print("Using built-in template code instead.")
            self._use_templates()
    
    def _use_templates(self) -> None:
        """Use built-in template code if no files are found."""
        self.templates = [
            # Sorting algorithms
            """def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr""",
            
            """def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)""",
            
            """def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1""",
            
            """def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n-1) + fibonacci(n-2)""",
            
            """def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True""",
            
            """def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] < right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result""",
            
            """def gcd(a, b):
    while b:
        a, b = b, a % b
    return a""",
            
            """def factorial(n):
    if n == 0 or n == 1:
        return 1
    else:
        return n * factorial(n-1)""",
            
            """def linear_search(arr, target):
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1""",
            
            """def reverse_string(s):
    return s[::-1]""",
        ]
        self.files = []  # No actual files, use templates
    
    def sample(self) -> str:
        """Sample a single code snippet.
        
        Returns:
            A code string.
        """
        if self.files:
            file_path = self.rng.choice(self.files)
            try:
                return file_path.read_text(encoding='utf-8')
            except Exception:
                return self.rng.choice(self.templates)
        else:
            return self.rng.choice(self.templates)
    
    def sample_pair(self) -> Tuple[str, str]:
        """Sample two different code snippets.
        
        Returns:
            Tuple of (code_a, code_b).
        """
        code_a = self.sample()
        code_b = self.sample()
        
        # Ensure they're different
        attempts = 0
        while code_b == code_a and attempts < 10:
            code_b = self.sample()
            attempts += 1
        
        return code_a, code_b
    
    def count(self) -> int:
        """Return number of available code files.
        
        Returns:
            Number of files in the pool.
        """
        if self.files:
            return len(self.files)
        else:
            return len(self.templates)