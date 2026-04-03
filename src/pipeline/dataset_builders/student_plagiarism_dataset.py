"""
Student Code Plagiarism Dataset – Ready-to-use benchmark data.

Includes:
1. Manual fib(n) test pairs (Type-1 to Type-4 clones + negatives)
2. Kaggle dataset wrapper for Ehsan Khani student-code-similarity dataset
3. Additional Python algorithm pairs for broader coverage
"""
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
import csv
from dataclasses import dataclass, field

from benchmark.data.obfuscation_generator import ObfuscationGenerator


# ========================================================================
# 1. FIBONACCI TEST PAIRS – Manual, carefully curated
# ========================================================================

# Raw code sources for the fib(n) assignment
FIB_ASSIGNMENT = {
    "recursive_original": '''def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
''',
    "iterative_original": '''def fib(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n+1):
        a, b = b, a + b
    return b
''',
    "memoized_original": '''def fib(n):
    memo = [0] * (n + 1)
    memo[1] = 1
    for i in range(2, n + 1):
        memo[i] = memo[i-1] + memo[i-2]
    return memo[n]
''',
    "iterative_v2": '''def fib(n):
    x = 0
    y = 1
    if n < 2:
        return n
    for i in range(n-1):
        x, y = y, x + y
    return y
''',
    "recursive_with_guard": '''def fib(n):
    if not isinstance(n, int):
        raise TypeError("n must be int")
    if n < 0:
        raise ValueError("n must be >= 0")
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
''',
    "iterative_with_docstring": '''def fib(n):
    """Return the nth Fibonacci number."""
    if n <= 1:
        return n
    prev, curr = 0, 1
    for _ in range(n - 1):
        prev, curr = curr, prev + curr
    return curr
''',
}

# Obfuscated versions (pre-generated for determinism)
def _get_obfuscated() -> Dict[str, str]:
    gen = ObfuscationGenerator(seed=42)
    results = {}
    for name, code in FIB_ASSIGNMENT.items():
        # Level 2: variable renaming
        r = gen.obfuscate(code, level=2, language="python")
        results[f"{name}_obf_rename"] = r.obfuscated
        # Level 4: mixed
        r2 = gen.obfuscate(code, level=4, language="python")
        results[f"{name}_obf_mixed"] = r2.obfuscated
    return results

_FIB_OBF = _get_obfuscated()

# =============================================================================
# Manual test pairs: (code1, code2, label, clone_type, description)
# label: 1 = plagiarized/clone, 0 = independent/not_plagiarized
# clone_type: 1=identical, 2=renamed, 3=restructured, 4=semantic, 5=independent
# =============================================================================
MANUAL_FIB_PAIRS: List[Dict[str, Any]] = [
    # ---- Type-1: Exact copy ----
    {
        "id": "fib_t1_exact",
        "code1": FIB_ASSIGNMENT["recursive_original"],
        "code2": FIB_ASSIGNMENT["recursive_original"],
        "label": 1,
        "clone_type": 1,
        "obfuscation_level": 0,
        "description": "Type-1: Exact same recursive fib",
    },
    {
        "id": "fib_t1_exact_iter",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": FIB_ASSIGNMENT["iterative_original"],
        "label": 1,
        "clone_type": 1,
        "obfuscation_level": 0,
        "description": "Type-1: Exact same iterative fib",
    },
    
    # ---- Type-2: Variable renaming ----
    {
        "id": "fib_t2_rename",
        "code1": FIB_ASSIGNMENT["recursive_original"],
        "code2": '''def fibonacci(number):
    # Calculate Fibonacci
    if number <= 1:
        return number
    return fibonacci(number-1) + fibonacci(number-2)
''',
        "label": 1,
        "clone_type": 2,
        "obfuscation_level": 2,
        "description": "Type-2: Renamed function and variable + added comment",
    },
    {
        "id": "fib_t2_rename_iter",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": FIB_ASSIGNMENT["iterative_v2"],
        "label": 1,
        "clone_type": 2,
        "obfuscation_level": 2,
        "description": "Type-2: Iterative with renamed vars (a,b -> x,y)",
    },
    
    # ---- Type-3: Restructured (recursion vs iteration) ----
    {
        "id": "fib_t3_recur_to_iter",
        "code1": FIB_ASSIGNMENT["recursive_original"],
        "code2": FIB_ASSIGNMENT["iterative_original"],
        "label": 1,
        "clone_type": 3,
        "obfuscation_level": 3,
        "description": "Type-3: Same semantics, recursion converted to iteration",
    },
    {
        "id": "fib_t3_iter_to_memo",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": FIB_ASSIGNMENT["memoized_original"],
        "label": 1,
        "clone_type": 3,
        "obfuscation_level": 3,
        "description": "Type-3: Iteration changed to memoized version",
    },
    {
        "id": "fib_t3_iter_variants",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": FIB_ASSIGNMENT["iterative_v2"],
        "label": 1,
        "clone_type": 3,
        "obfuscation_level": 3,
        "description": "Type-3: Two iterative variants with different loop logic",
    },
    
    # ---- Type-3 with mixed obfuscation ----
    {
        "id": "fib_t3_obf_rename",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": _FIB_OBF.get("iterative_original_obf_rename", FIB_ASSIGNMENT["iterative_v2"]),
        "label": 1,
        "clone_type": 3,
        "obfuscation_level": 2,
        "description": "Type-3: Obfuscated iterative (variable renaming)",
    },
    {
        "id": "fib_t3_obf_mixed",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": _FIB_OBF.get("iterative_original_obf_mixed", FIB_ASSIGNMENT["iterative_v2"]),
        "label": 1,
        "clone_type": 3,
        "obfuscation_level": 4,
        "description": "Type-3: Obfuscated iterative (mixed transforms)",
    },
    
    # ---- Type-4: Semantic similarity ----
    {
        "id": "fib_t4_semantic",
        "code1": FIB_ASSIGNMENT["recursive_original"],
        "code2": FIB_ASSIGNMENT["recursive_with_guard"],
        "label": 1,
        "clone_type": 4,
        "obfuscation_level": 3,
        "description": "Type-4: Same core algorithm with input validation added",
    },
    {
        "id": "fib_t4_docstring",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": FIB_ASSIGNMENT["iterative_with_docstring"],
        "label": 1,
        "clone_type": 4,
        "obfuscation_level": 1,
        "description": "Type-4: Same algorithm with docstring and better var names",
    },
    
    # ---- Negative: Independent implementations ----
    {
        "id": "fib_neg_1",
        "code1": FIB_ASSIGNMENT["iterative_original"],
        "code2": FIB_ASSIGNMENT["memoized_original"],
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Iterative vs Memoized (same task, different approach)",
    },
    {
        "id": "fib_neg_2",
        "code1": FIB_ASSIGNMENT["recursive_original"],
        "code2": FIB_ASSIGNMENT["memoized_original"],
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Naive recursion vs Memoized (different strategy)",
    },
    
    # ---- Negative: Different algorithms ----
    {
        "id": "fib_neg_sort_vs_search",
        "code1": '''def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
''',
        "code2": '''def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Completely different algorithms",
    },
]

# More diverse algorithm pairs
ALGORITHM_PAIRS: List[Dict[str, Any]] = [
    # ---- Sorting clones ----
    {
        "id": "sort_t1",
        "code1": '''def selection_sort(arr):
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
''',
        "code2": '''def selection_sort(lst):
    n = len(lst)
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if lst[j] < lst[min_idx]:
                min_idx = j
        lst[i], lst[min_idx] = lst[min_idx], lst[i]
    return lst
''',
        "label": 1,
        "clone_type": 2,
        "obfuscation_level": 2,
        "description": "Type-2: Selection sort with renamed param",
    },
    {
        "id": "sort_neg",
        "code1": '''def selection_sort(arr):
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
''',
        "code2": '''def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Selection sort vs Merge sort",
    },
    
    # ---- Prime checking ----
    {
        "id": "prime_t1",
        "code1": '''def is_prime(n):
    if n <= 1:
        return False
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
''',
        "code2": '''def is_prime(n):
    if n <= 1:
        return False
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
''',
        "label": 1,
        "clone_type": 1,
        "obfuscation_level": 0,
        "description": "Type-1: Exact prime check",
    },
    {
        "id": "prime_t2",
        "code1": '''def is_prime(n):
    if n <= 1:
        return False
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
''',
        "code2": '''def check_prime(number):
    # Returns True if prime
    if number <= 1:
        return False
    for i in range(2, number):
        if number % i == 0:
            return False
    return True
''',
        "label": 1,
        "clone_type": 2,
        "obfuscation_level": 2,
        "description": "Type-2: Prime check with renamed function + comment",
    },
    {
        "id": "prime_t3",
        "code1": '''def is_prime(n):
    if n <= 1:
        return False
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
''',
        "code2": '''def is_prime(n):
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
    return True
''',
        "label": 1,
        "clone_type": 3,
        "obfuscation_level": 3,
        "description": "Type-3: Naive vs optimized prime check (6k +/- 1)",
    },
    
    # ---- Linked list operations ----
    {
        "id": "ll_t1",
        "code1": '''class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

def reverse_list(head):
    prev = None
    current = head
    while current:
        next_node = current.next
        current.next = prev
        prev = current
        current = next_node
    return prev
''',
        "code2": '''class Node:
    def __init__(self, val):
        self.data = val
        self.next = None

def reverse_linked_list(head):
    prev_node = None
    curr = head
    while curr is not None:
        nxt = curr.next
        curr.next = prev_node
        prev_node = curr
        curr = nxt
    return prev_node
''',
        "label": 1,
        "clone_type": 2,
        "obfuscation_level": 2,
        "description": "Type-2: List reversal with renamed vars + class attribute rename",
    },
    
    # ---- Negative: Tree vs List ----
    {
        "id": "neg_tree_vs_list",
        "code1": '''class BinaryTreeNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

def inorder_traversal(root):
    result = []
    if root:
        result = inorder_traversal(root.left)
        result.append(root.val)
        result = result + inorder_traversal(root.right)
    return result
''',
        "code2": '''class Node:
    def __init__(self, d):
        self.data = d
        self.next_node = None

def reverse_list(head):
    prev = None
    curr = head
    while curr:
        nxt = curr.next_node
        curr.next_node = prev
        prev = curr
        curr = nxt
    return prev
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Tree traversal vs Linked list reversal",
    },
    
    # ---- Negative: Different math functions ----
    {
        "id": "neg_factorial_vs_power",
        "code1": '''def factorial(n):
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
''',
        "code2": '''def power(base, exp):
    result = 1
    for _ in range(exp):
        result *= base
    return result
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Factorial vs Power (similar structure, different semantics)",
    },
    
    # ---- Negative: Different string operations ----
    {
        "id": "neg_palindrome_vs_reverse",
        "code1": '''def is_palindrome(s):
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]
''',
        "code2": '''def reverse_string(s):
    result = ""
    for char in s:
        result = char + result
    return result
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Palindrome check vs String reversal",
    },
    
    # ---- Negative: Different search ----
    {
        "id": "neg_linear_vs_binary",
        "code1": '''def linear_search(arr, target):
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
''',
        "code2": '''def binary_search(arr, target):
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
    return -1
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: Linear vs Binary search (similar interface, different algorithm)",
    },
    
    # ---- Type-2: Dictionary comprehension vs loop ----
    {
        "id": "dict_t2",
        "code1": '''def word_frequencies(words):
    freq = {}
    for word in words:
        if word in freq:
            freq[word] += 1
        else:
            freq[word] = 1
    return freq
''',
        "code2": '''def count_words(word_list):
    counts = {}
    for w in word_list:
        if w in counts:
            counts[w] += 1
        else:
            counts[w] = 1
    return counts
''',
        "label": 1,
        "clone_type": 2,
        "obfuscation_level": 2,
        "description": "Type-2: Word frequency count with renamed vars",
    },
    
    # ---- Negative: GCD vs LCM ----
    {
        "id": "neg_gcd_vs_lcm",
        "code1": '''def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
''',
        "code2": '''def lcm(a, b):
    def gcd(x, y):
        while y:
            x, y = y, x % y
        return x
    return abs(a * b) // gcd(a, b)
''',
        "label": 0,
        "clone_type": 5,
        "obfuscation_level": 0,
        "description": "Independent: GCD vs LCM (LCM uses GCD internally, but different purpose)",
    },
]


# Combine all manual pairs
ALL_MANUAL_PAIRS = MANUAL_FIB_PAIRS + ALGORITHM_PAIRS


def get_fib_dataset() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Get the fib() test dataset with ground truth.

    Returns:
        (test_pairs, ground_truth_dict)
    """
    gt_pairs = [{
        "file1": f"student_{p['id']}_a.py",
        "file2": f"student_{p['id']}_b.py",
        "label": p["label"],
        "clone_type": f"T{p['clone_type']}",
        "description": p["description"],
    } for p in MANUAL_FIB_PAIRS]

    test_pairs = [{
        "code1": p["code1"],
        "code2": p["code2"],
        "label": p["label"],
        "obfuscation_level": p["obfuscation_level"],
        "id": p["id"],
        "description": p["description"],
        "file1": f"student_{p['id']}_a.py",
        "file2": f"student_{p['id']}_b.py",
    } for p in MANUAL_FIB_PAIRS]

    return test_pairs, {"pairs": gt_pairs}


def get_algorithm_dataset() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Get the algorithm test dataset.

    Returns:
        (test_pairs, ground_truth_dict)
    """
    gt_pairs = [{
        "file1": f"test_{p['id']}_a.py",
        "file2": f"test_{p['id']}_b.py",
        "label": p["label"],
        "clone_type": f"T{p['clone_type']}",
        "description": p["description"],
    } for p in ALGORITHM_PAIRS]

    test_pairs = [{
        "code1": p["code1"],
        "code2": p["code2"],
        "label": p["label"],
        "obfuscation_level": p["obfuscation_level"],
        "id": p["id"],
        "description": p["description"],
        "file1": f"test_{p['id']}_a.py",
        "file2": f"test_{p['id']}_b.py",
    } for p in ALGORITHM_PAIRS]

    return test_pairs, {"pairs": gt_pairs}


def get_full_manual_dataset() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Get combined fib + algorithm manual test dataset.

    Returns:
        (test_pairs, ground_truth_dict)
    """
    fib_pairs, fib_gt = get_fib_dataset()
    algo_pairs, algo_gt = get_algorithm_dataset()
    
    all_pairs = fib_pairs + algo_pairs
    all_gt = {"pairs": fib_gt["pairs"] + algo_gt["pairs"]}
    
    return all_pairs, all_gt


def save_manual_dataset(output_path: Path = Path("benchmark/data/manual_dataset.json")) -> None:
    """Save manual dataset to JSON for reuse."""
    test_pairs, gt = get_full_manual_dataset()
    
    data = {
        "name": "Student Plagiarism Manual Dataset",
        "description": (
            "Manual test pairs for Python code plagiarism detection benchmarking. "
            "Covers Type-1 (exact copy) through Type-4 (semantic) clones and "
            "independent implementations as negatives."
        ),
        "num_pairs": len(test_pairs),
        "num_positive": sum(1 for p in test_pairs if p["label"] == 1),
        "num_negative": sum(1 for p in test_pairs if p["label"] == 0),
        "test_pairs": test_pairs,
        "ground_truth": gt,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# ==============================================================================
# 2. Kaggle Dataset Wrapper
# ==============================================================================

class KaggleStudentCodeDataset:
    """
    Wrapper for the Kaggle Student Code Similarity dataset.

    Link: https://www.kaggle.com/datasets/ehsankhani/student-code-similarity-and-plagiarism-labels

    Expected structure after download:
        kaggle_student_code/
        +-- submissions/         # Python source files
        +-- similarity.csv       # Columns: file1, file2, similarity_score, is_plagiarized
        +-- README.md

    Usage:
        ds = KaggleStudentCodeDataset(Path("data/kaggle_student_code"))
        pairs = ds.load_pairs()
    """

    def __init__(self, data_dir: Path = Path("benchmark/data/kaggle_student_code")):
        self.data_dir = data_dir
        self._pairs: List[Dict[str, Any]] = []
        self._code_cache: Dict[str, str] = {}

    def is_available(self) -> bool:
        """Check if the dataset has been downloaded."""
        submissions_dir = self.data_dir / "submissions"
        csv_files = list(self.data_dir.glob("*.csv"))
        return submissions_dir.exists() and len(csv_files) > 0

    def load_pairs(self, max_pairs: int = None) -> List[Dict[str, Any]]:
        """
        Load plagiarism pairs from CSV.

        Returns:
            List of {"code1": ..., "code2": ..., "label": 0|1, "similarity": float, "id": str}
        """
        if not self.is_available():
            raise FileNotFoundError(
                f"Kaggle dataset not found at {self.data_dir}\n"
                f"Please download from:\n"
                f"https://www.kaggle.com/datasets/ehsankhani/student-code-similarity-and-plagiarism-labels\n"
                f"and extract to {self.data_dir}"
            )

        # Find the CSV file
        csv_files = list(self.data_dir.glob("*.csv"))
        if not csv_files:
            return []

        pairs = []
        with open(csv_files[0], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_pairs and i >= max_pairs:
                    break
                
                file1 = row.get('file1', row.get('submission1', ''))
                file2 = row.get('file2', row.get('submission2', ''))
                label = int(row.get('is_plagiarized', row.get('label', 0)))
                similarity = float(row.get('similarity_score', row.get('score', 0)))

                code1 = self._load_code(file1) if file1 else ""
                code2 = self._load_code(file2) if file2 else ""

                pairs.append({
                    "id": f"kaggle_{i}",
                    "code1": code1,
                    "code2": code2,
                    "label": label,
                    "similarity": similarity,
                    "obfuscation_level": 0,
                    "file1": file1,
                    "file2": file2,
                })

        self._pairs = pairs
        return pairs

    def _load_code(self, filename: str) -> str:
        """Load source code from submissions directory."""
        if filename in self._code_cache:
            return self._code_cache[filename]

        code_path = self.data_dir / "submissions" / filename
        if not code_path.exists():
            return ""

        try:
            code = code_path.read_text(encoding='utf-8', errors='ignore')
            self._code_cache[filename] = code
            return code
        except Exception:
            return ""

    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        if self._pairs:
            labels = [p["label"] for p in self._pairs]
            return {
                "name": "Kaggle Student Code Similarity",
                "source": "https://www.kaggle.com/datasets/ehsankhani/student-code-similarity-and-plagiarism-labels",
                "total_pairs": len(self._pairs),
                "positive_pairs": sum(1 for l in labels if l == 1),
                "negative_pairs": sum(1 for l in labels if l == 0),
                "pos_ratio": sum(labels) / len(labels) if labels else 0,
            }
        return {
            "name": "Kaggle Student Code Similarity",
            "total_pairs": 0,
            "available": self.is_available(),
        }


# ==============================================================================
# 3. Dataset Registry
# ==============================================================================

DATASET_REGISTRY = {
    "fib": get_fib_dataset,
    "algorithm": get_algorithm_dataset,
    "manual": get_full_manual_dataset,
    "full_manual": get_full_manual_dataset,
}

# Count statistics
_FIB_CNT = len(MANUAL_FIB_PAIRS)
_ALGO_CNT = len(ALGORITHM_PAIRS)
_TOTAL_CNT = _FIB_CNT + _ALGO_CNT
_POS_CNT = sum(1 for p in ALL_MANUAL_PAIRS if p["label"] == 1)
_NEG_CNT = sum(1 for p in ALL_MANUAL_PAIRS if p["label"] == 0)


def get_dataset_stats() -> Dict[str, Any]:
    """Get statistics for all manual datasets."""
    clone_type_counts = {}
    for p in ALL_MANUAL_PAIRS:
        ct = f"T{p['clone_type']}"
        label = "positive" if p["label"] == 1 else "negative"
        key = f"{ct}_{label}"
        clone_type_counts[key] = clone_type_counts.get(key, 0) + 1

    return {
        "total_pairs": _TOTAL_CNT,
        "positive_pairs": _POS_CNT,
        "negative_pairs": _NEG_CNT,
        "fib_pairs": _FIB_CNT,
        "algorithm_pairs": _ALGO_CNT,
        "clone_type_counts": clone_type_counts,
    }