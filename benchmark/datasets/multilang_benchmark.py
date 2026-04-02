"""Multi-language dataset for Layer 3 generalization testing.

Provides semantically equivalent code samples in:
- Python
- Java
- JavaScript

Each language implements the same algorithms so cross-language
generalization can be evaluated properly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Multi-language algorithm templates (same logic, different syntax)
# =============================================================================

PYTHON_SAMPLES: List[str] = [
    # 0: Linear search
    '''def linear_search(arr, target):
    """Search for target using linear search."""
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
''',
    # 1: Binary search
    '''def binary_search(sorted_list, target):
    """Search for target in sorted list."""
    left, right = 0, len(sorted_list) - 1
    while left <= right:
        mid = (left + right) // 2
        if sorted_list[mid] == target:
            return mid
        elif sorted_list[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
''',
    # 2: Bubble sort
    '''def bubble_sort(arr):
    """Sort array using bubble sort."""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                temp = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
    return arr
''',
    # 3: Factorial
    '''def factorial(n):
    """Calculate factorial of n."""
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result = result * i
    return result
''',
    # 4: GCD
    '''def gcd(a, b):
    """Calculate greatest common divisor."""
    while b != 0:
        a, b = b, a % b
    return a
''',
    # 5: Fibonacci
    '''def fibonacci(n):
    """Generate fibonacci sequence up to n terms."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    seq = [0, 1]
    for i in range(2, n):
        seq.append(seq[i-1] + seq[i-2])
    return seq
''',
    # 6: Is prime
    '''def is_prime(number):
    """Check if a number is prime."""
    if number < 2:
        return False
    for i in range(2, int(number ** 0.5) + 1):
        if number % i == 0:
            return False
    return True
''',
    # 7: Reverse string
    '''def reverse_string(s):
    """Reverse a string."""
    return s[::-1]
''',
    # 8: Sum of list
    '''def sum_list(numbers):
    """Calculate sum of list elements."""
    total = 0
    for num in numbers:
        total = total + num
    return total
''',
    # 9: Find max
    '''def find_max(numbers):
    """Find maximum value in a list."""
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
''',
]

JAVA_SAMPLES: List[str] = [
    # 0: Linear search
    '''public static int linearSearch(int[] arr, int target) {
    // Search for target using linear search
    for (int i = 0; i < arr.length; i++) {
        if (arr[i] == target) {
            return i;
        }
    }
    return -1;
}
''',
    # 1: Binary search
    '''public static int binarySearch(int[] sortedArr, int target) {
    // Search for target in sorted array
    int left = 0;
    int right = sortedArr.length - 1;
    while (left <= right) {
        int mid = (left + right) / 2;
        if (sortedArr[mid] == target) {
            return mid;
        } else if (sortedArr[mid] < target) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    return -1;
}
''',
    # 2: Bubble sort
    '''public static List<Integer> bubbleSort(List<Integer> arr) {
    // Sort list using bubble sort
    int n = arr.size();
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr.get(j) > arr.get(j + 1)) {
                int temp = arr.get(j);
                arr.set(j, arr.get(j + 1));
                arr.set(j + 1, temp);
            }
        }
    }
    return arr;
}
''',
    # 3: Factorial
    '''public static int factorial(int n) {
    // Calculate factorial of n
    if (n <= 1) {
        return 1;
    }
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result = result * i;
    }
    return result;
}
''',
    # 4: GCD
    '''public static int gcd(int a, int b) {
    // Calculate greatest common divisor
    while (b != 0) {
        int temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}
''',
    # 5: Fibonacci
    '''public static List<Integer> fibonacci(int n) {
    // Generate fibonacci sequence up to n terms
    List<Integer> seq = new ArrayList<>();
    if (n <= 0) return seq;
    if (n == 1) { seq.add(0); return seq; }
    seq.add(0);
    seq.add(1);
    for (int i = 2; i < n; i++) {
        seq.add(seq.get(i-1) + seq.get(i-2));
    }
    return seq;
}
''',
    # 6: Is prime
    '''public static boolean isPrime(int number) {
    // Check if a number is prime
    if (number < 2) return false;
    for (int i = 2; i <= Math.sqrt(number); i++) {
        if (number % i == 0) return false;
    }
    return true;
}
''',
    # 7: Reverse string
    '''public static String reverseString(String s) {
    // Reverse a string
    return new StringBuilder(s).reverse().toString();
}
''',
    # 8: Sum of list
    '''public static int sumList(List<Integer> numbers) {
    // Calculate sum of list elements
    int total = 0;
    for (int num : numbers) {
        total = total + num;
    }
    return total;
}
''',
    # 9: Find max
    '''public static int findMax(List<Integer> numbers) {
    // Find maximum value in a list
    if (numbers.isEmpty()) return 0;
    int maxVal = numbers.get(0);
    for (int num : numbers) {
        if (num > maxVal) maxVal = num;
    }
    return maxVal;
}
''',
]

JAVASCRIPT_SAMPLES: List[str] = [
    # 0: Linear search
    '''function linearSearch(arr, target) {
    // Search for target using linear search
    for (let i = 0; i < arr.length; i++) {
        if (arr[i] === target) {
            return i;
        }
    }
    return -1;
}
''',
    # 1: Binary search
    '''function binarySearch(sortedArr, target) {
    // Search for target in sorted array
    let left = 0;
    let right = sortedArr.length - 1;
    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        if (sortedArr[mid] === target) {
            return mid;
        } else if (sortedArr[mid] < target) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    return -1;
}
''',
    # 2: Bubble sort
    '''function bubbleSort(arr) {
    // Sort array using bubble sort
    const n = arr.length;
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                const temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
    return arr;
}
''',
    # 3: Factorial
    '''function factorial(n) {
    // Calculate factorial of n
    if (n <= 1) return 1;
    let result = 1;
    for (let i = 2; i <= n; i++) {
        result = result * i;
    }
    return result;
}
''',
    # 4: GCD
    '''function gcd(a, b) {
    // Calculate greatest common divisor
    while (b !== 0) {
        const temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}
''',
    # 5: Fibonacci
    '''function fibonacci(n) {
    // Generate fibonacci sequence up to n terms
    if (n <= 0) return [];
    if (n === 1) return [0];
    const seq = [0, 1];
    for (let i = 2; i < n; i++) {
        seq.push(seq[i-1] + seq[i-2]);
    }
    return seq;
}
''',
    # 6: Is prime
    '''function isPrime(number) {
    // Check if a number is prime
    if (number < 2) return false;
    for (let i = 2; i <= Math.sqrt(number); i++) {
        if (number % i === 0) return false;
    }
    return true;
}
''',
    # 7: Reverse string
    '''function reverseString(s) {
    // Reverse a string
    return s.split('').reverse().join('');
}
''',
    # 8: Sum of list
    '''function sumList(numbers) {
    // Calculate sum of list elements
    let total = 0;
    for (const num of numbers) {
        total = total + num;
    }
    return total;
}
''',
    # 9: Find max
    '''function findMax(numbers) {
    // Find maximum value in a list
    if (numbers.length === 0) return null;
    let maxVal = numbers[0];
    for (const num of numbers) {
        if (num > maxVal) maxVal = num;
    }
    return maxVal;
}
''',
]


# =============================================================================
# Dataset class
# =============================================================================


@dataclass
class MultiLangDataset:
    """Container for multi-language code samples."""
    python: Dict[str, str]
    java: Dict[str, str]
    javascript: Dict[str, str]
    
    @property
    def languages(self) -> List[str]:
        return [k for k in [
            "python" if self.python else None,
            "java" if self.java else None,
            "javascript" if self.javascript else None,
        ] if k]
    
    def get_pairs(self, lang_a: str, lang_b: str) -> List[Tuple[str, str]]:
        """Get semantically aligned code pairs across languages."""
        samples_a = getattr(self, lang_a, {})
        samples_b = getattr(self, lang_b, {})
        common_keys = set(samples_a.keys()) & set(samples_b.keys())
        return [(samples_a[k], samples_b[k]) for k in sorted(common_keys)]
    
    def get_single_language(self, lang: str) -> List[str]:
        """Get all samples for a single language."""
        return list(getattr(self, lang, {}).values())


class MultiLangLoader:
    """Loads multi-language benchmark data for Layer 3 generalization testing.
    
    Returns semantically equivalent code in Python, Java, and JavaScript.
    """
    
    def __init__(self, include_types: Optional[List[str]] = None):
        """Initialize loader.
        
        Args:
            include_types: Optional list of specific algorithms to include.
                If None, all 10 algorithms are included.
        """
        self._include_types = include_types
        self._dataset: Optional[MultiLangDataset] = None
    
    def _indices(self) -> List[int]:
        if self._include_types:
            # allow indices or names
            mapping = {
                "linear_search": 0, "binary_search": 1, "bubble_sort": 2,
                "factorial": 3, "gcd": 4, "fibonacci": 5,
                "is_prime": 6, "reverse_string": 7, "sum_list": 8, "find_max": 9,
            }
            indices = []
            for item in self._include_types:
                if isinstance(item, int):
                    indices.append(item)
                else:
                    idx = mapping.get(item)
                    if idx is not None:
                        indices.append(idx)
            return sorted(set(indices))
        return list(range(len(PYTHON_SAMPLES)))
    
    def load(self) -> MultiLangDataset:
        """Load the multi-language dataset."""
        indices = self._indices()
        python = {str(i): PYTHON_SAMPLES[i] for i in indices}
        java = {str(i): JAVA_SAMPLES[i] for i in indices}
        javascript = {str(i): JAVASCRIPT_SAMPLES[i] for i in indices}
        self._dataset = MultiLangDataset(python=python, java=java, javascript=javascript)
        return self._dataset
    
    @property
    def dataset(self) -> Optional[MultiLangDataset]:
        return self._dataset


# =============================================================================
# Convenience function for Layer 3 runner
# =============================================================================


def get_multilang_samples(
    include: Optional[List[str]] = None
) -> List[Tuple[str, List[str]]]:
    """Return language, samples tuples for Layer 3 evaluation.
    
    Args:
        include: Optional list of algorithm names to include.
        
    Returns:
        List of (language_name, [code_samples]) tuples.
    """
    loader = MultiLangLoader(include_types=include)
    ds = loader.load()
    
    return [
        ("python", ds.get_single_language("python")),
        ("java", ds.get_single_language("java")),
        ("javascript", ds.get_single_language("javascript")),
    ]