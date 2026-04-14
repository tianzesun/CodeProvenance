"""Synthetic dataset generator for controlled ground truth evaluation.

This generates controlled code transformations with known similarity labels,
enabling precise measurement of detector capabilities across clone types.

Clone Types Generated:
- Type-1: Exact clones (identical code)
- Type-2: Renamed identifiers (variable/method renaming)
- Type-3: Restructured (reordered statements, loop transformations)
- Type-4: Semantic (same logic, different implementation)

Usage:
    from src.backend.benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
    
    generator = SyntheticDatasetGenerator(seed=42)
    dataset = generator.generate_pair_count(
        type1=50, type2=50, type3=50, type4=50, non_clone=200
    )
    print(f"Generated {len(dataset.pairs)} pairs")
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import json


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class SyntheticPair:
    """A synthetic code pair with ground truth."""
    id: str
    code_a: str
    code_b: str
    clone_type: int  # 0=non-clone, 1=T1, 2=T2, 3=T3, 4=T4
    label: int  # 1=clone, 0=non-clone
    obfuscation: str = "none"  # "none", "rename", "reorder", "restructure"
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyntheticDataset:
    """Complete synthetic dataset."""
    pairs: List[SyntheticPair]
    name: str = "synthetic"
    version: str = "1.0"
    
    def save(self, path: str) -> str:
        """Save dataset to JSON file.
        
        Args:
            path: Output file path.
            
        Returns:
            Path to saved file.
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "name": self.name,
            "version": self.version,
            "pair_count": len(self.pairs),
            "pairs": [
                {
                    "id": p.id,
                    "code_a": p.code_a,
                    "code_b": p.code_b,
                    "clone_type": p.clone_type,
                    "label": p.label,
                    "obfuscation": p.obfuscation,
                    "metadata": p.metadata,
                }
                for p in self.pairs
            ],
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return str(output_path)
    
    @classmethod
    def load(cls, path: str) -> "SyntheticDataset":
        """Load dataset from JSON file.
        
        Args:
            path: Path to JSON file.
            
        Returns:
            Loaded SyntheticDataset.
        """
        output_path = Path(path)
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        pairs = [
            SyntheticPair(
                id=p["id"],
                code_a=p["code_a"],
                code_b=p["code_b"],
                clone_type=p["clone_type"],
                label=p["label"],
                obfuscation=p["obfuscation"],
                metadata=p.get("metadata", {}),
            )
            for p in data["pairs"]
        ]
        
        return cls(
            pairs=pairs,
            name=data.get("name", "synthetic"),
            version=data.get("version", "1.0"),
        )
    
    def stats(self) -> Dict[str, int]:
        """Get dataset statistics.
        
        Returns:
            Dictionary with counts by clone type.
        """
        counts: Dict[str, int] = {}
        for p in self.pairs:
            key = f"type_{p.clone_type}" if p.clone_type > 0 else "non_clone"
            counts[key] = counts.get(key, 0) + 1
        counts["total"] = len(self.pairs)
        return counts


# =============================================================================
# Code transformation functions
# =============================================================================

# Sample code templates for generating synthetic pairs
SAMPLE_TEMPLATES = [
    # Python function template
    '''def {func_name}({args}):
    """{docstring}."""
    {body}
    return {return_val}
''',
    # Java method template
    '''public {return_type} {method_name}({params}) {{
    // {comment}
    {body}
    return {return_val};
}}
''',
]


def _generate_identifier(seed: int, prefix: str = "") -> str:
    """Generate a random identifier.
    
    Args:
        seed: Random seed for reproducibility.
        prefix: Optional identifier prefix.
        
    Returns:
        Random identifier string.
    """
    rng = random.Random(seed)
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(rng.choice(chars) for _ in range(6))
    return f"{prefix}{suffix}"


def _generate_variable_name(seed: int) -> str:
    """Generate a variable name.
    
    Args:
        seed: Random seed.
        
    Returns:
        Variable name string.
    """
    names = [
        "result", "value", "data", "input", "output",
        "item", "index", "count", "total", "sum",
        "x", "y", "z", "temp", "val",
    ]
    rng = random.Random(seed)
    return rng.choice(names)


# =============================================================================
# Clone type generators
# =============================================================================

def generate_type1_pair(base_code: str, seed: int = 42) -> Tuple[str, str]:
    """Generate Type-1 clone pair (identical code).
    
    Args:
        base_code: Base source code.
        seed: Random seed.
        
    Returns:
        Tuple of (code_a, code_b) - identical.
    """
    return base_code, base_code


def generate_type2_pair(base_code: str, seed: int = 42) -> Tuple[str, str]:
    """Generate Type-2 clone pair (renamed identifiers).
    
    Args:
        base_code: Base source code.
        seed: Random seed for consistent renaming.
        
    Returns:
        Tuple of (code_a, code_b) with renamed identifiers.
    """
    rng = random.Random(seed)
    
    # Collect all potential identifiers
    import re
    
    # Find common variable-like identifiers
    identifiers = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', base_code))
    
    # Filter out keywords
    keywords = {
        'def', 'return', 'if', 'else', 'for', 'while', 'import', 'from',
        'class', 'try', 'except', 'finally', 'with', 'as', 'in', 'not',
        'and', 'or', 'is', 'None', 'True', 'False', 'print', 'self',
        'int', 'float', 'str', 'list', 'dict', 'set', 'tuple', 'bool',
        'public', 'private', 'protected', 'static', 'void', 'final',
        'new', 'this', 'super', 'extends', 'implements', 'interface',
        'const', 'let', 'var', 'function', 'async', 'await',
    }
    
    identifiers = {i for i in identifiers if i not in keywords and len(i) > 1}
    
    # Create renaming map
    rename_map = {}
    for ident in identifiers:
        new_name = _generate_identifier(rng.randint(0, 999999), prefix="v_")
        rename_map[ident] = new_name
    
    # Apply renaming
    modified = base_code
    for old, new in rename_map.items():
        modified = re.sub(r'\b' + re.escape(old) + r'\b', new, modified)
    
    return base_code, modified


def generate_type3_pair(base_code: str, seed: int = 42) -> Tuple[str, str]:
    """Generate Type-3 clone pair (restructured code).
    
    Args:
        base_code: Base source code.
        seed: Random seed for consistent restructuring.
        
    Returns:
        Tuple of (code_a, code_b) with restructured code.
    """
    rng = random.Random(seed)
    
    # Strategy 1: Add redundant statements
    lines = base_code.split('\n')
    non_empty = [i for i, l in enumerate(lines) if l.strip()]
    
    if len(non_empty) > 2:
        # Add a redundant comment line
        insert_pos = rng.choice(non_empty[1:-1]) if len(non_empty) > 2 else non_empty[0]
        lines.insert(insert_pos, f"    # Processing step")
    
    modified = '\n'.join(lines)
    
    # Strategy 2: Reorder independent statements (if there are multiple)
    # This is a simple heuristic: swap adjacent assignment lines
    mod_lines = modified.split('\n')
    for i in range(len(mod_lines) - 1):
        if '=' in mod_lines[i] and '=' in mod_lines[i + 1]:
            if '==' not in mod_lines[i] and '==' not in mod_lines[i + 1]:
                if rng.random() > 0.5:
                    mod_lines[i], mod_lines[i + 1] = mod_lines[i + 1], mod_lines[i]
    
    modified = '\n'.join(mod_lines)
    
    return base_code, modified


def generate_type4_pair(base_code: str, seed: int = 42) -> Tuple[str, str]:
    """Generate Type-4 clone pair (semantic equivalent, different syntax).
    
    Args:
        base_code: Base source code.
        seed: Random seed for consistent transformation.
        
    Returns:
        Tuple of (code_a, code_b) with semantically equivalent code.
    """
    rng = random.Random(seed)
    
    # Apply semantic-preserving transformations
    modified = base_code
    
    # Transform 1: while -> for loops (when pattern detected)
    import re
    
    # Transform 2: if-else conditional expressions
    modified = modified.replace("= True", "= not False")
    modified = modified.replace("= False", "= not True")
    
    # Transform 3: Different way to express same operation
    replacements = [
        ("range(len(", "enumerate("),
        ("x + 1", "1 + x"),
        ("y + 1", "1 + y"),
        ("i + 1", "1 + i"),
    ]
    
    for old, new in replacements:
        if old in modified:
            modified = modified.replace(old, new)
    
    # Transform 4: Extra layer of indirection
    if "for i in" in modified:
        modified = modified.replace("for i in", "for idx in")
    
    return base_code, modified


def generate_non_clone_pair(base_code: str, seed: int = 42, language: str = "python") -> Tuple[str, str]:
    """Generate a non-clone pair (completely different code).
    
    Args:
        base_code: Base source code A.
        seed: Random seed for generating code B.
        language: Target language.
        
    Returns:
        Tuple of (code_a, code_b) - completely different.
    """
    rng = random.Random(seed)
    
    # Generate completely different code
    different_codes = {
        "python": [
            '''class DataProcessor:
    """Process and analyze data."""
    def __init__(self, data):
        self._data = data
        self._results = []
    
    def process(self):
        """Process all data items."""
        for item in self._data:
            result = self._transform(item)
            self._results.append(result)
        return self._results
    
    def _transform(self, item):
        """Transform a single item."""
        return item * 2 + 1
''',
            '''def calculate_statistics(numbers):
    """Calculate basic statistics for a list of numbers."""
    if not numbers:
        return {"mean": 0, "min": 0, "max": 0, "count": 0}
    
    n = len(numbers)
    total = sum(numbers)
    mean = total / n
    minimum = min(numbers)
    maximum = max(numbers)
    
    return {
        "mean": mean,
        "min": minimum,
        "max": maximum,
        "count": n,
        "range": maximum - minimum
    }
''',
            '''def binary_search(sorted_list, target):
    """Search for target in sorted list using binary search."""
    left = 0
    right = len(sorted_list) - 1
    
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
        ],
        "java": [
            '''public class Stack<T> {
    private List<T> elements;
    
    public Stack() {
        this.elements = new ArrayList<>();
    }
    
    public void push(T item) {
        elements.add(item);
    }
    
    public T pop() {
        if (elements.isEmpty()) {
            throw new EmptyStackException();
        }
        return elements.remove(elements.size() - 1);
    }
    
    public T peek() {
        if (elements.isEmpty()) {
            throw new EmptyStackException();
        }
        return elements.get(elements.size() - 1);
    }
}
''',
        ],
    }
    
    alternatives = different_codes.get(language, different_codes["python"])
    code_b = rng.choice(alternatives)
    
    return base_code, code_b


# =============================================================================
# Main generator class
# =============================================================================

class SyntheticDatasetGenerator:
    """Generate synthetic code clone datasets with known ground truth.
    
    This generates controlled test cases for measuring detector accuracy
    across different types of code similarity (Type-1 through Type-4 clones).
    
    Usage:
        generator = SyntheticDatasetGenerator(seed=42)
        dataset = generator.generate_pair_count(
            type1=50, type2=50, type3=50, type4=50, non_clone=200
        )
    """
    
    def __init__(
        self,
        base_codes: Optional[List[str]] = None,
        seed: int = 42,
        language: str = "python"
    ):
        """Initialize the generator.
        
        Args:
            base_codes: Optional list of base code snippets to use.
                If not provided, built-in templates are used.
            seed: Random seed for reproducibility.
            language: Programming language identifier.
        """
        self._rng = random.Random(seed)
        self._seed = seed
        self._language = language
        self._base_codes = base_codes or self._get_default_templates(language)
    
    def _get_default_templates(self, language: str) -> List[str]:
        """Get default code templates for the given language.
        
        Args:
            language: Programming language identifier.
            
        Returns:
            List of base code templates.
        """
        if language == "java":
            return [
                '''public int sum(Array{0} arr) {
    int total = 0;
    for (int i = 0; i < arr.length; i++) {
        total = total + arr[i];
    }
    return total;
}
''',
                '''public List<Integer> filter(List<Integer> list) {
    List<Integer> result = new ArrayList<>();
    for (Integer item : list) {
        if (item > 0) {
            result.add(item);
        }
    }
    return result;
}
''',
            ]
        
        # Python default - 50 unique templates for Type-2 clone generation
        return [
            '''def find_max(numbers):
    """Find the maximum value in a list."""
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
''',
            '''def calculate_average(values):
    """Calculate the average of a list of values."""
    if not values:
        return 0.0
    total = sum(values)
    count = len(values)
    return total / count
''',
            '''def filter_positive(numbers):
    """Filter a list to keep only positive numbers."""
    result = []
    for num in numbers:
        if num > 0:
            result.append(num)
    return result
''',
            '''def binary_search(sorted_list, target):
    """Search for target in sorted list using binary search."""
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
            '''def count_words(text):
    """Count the number of words in a text string."""
    words = text.split()
    word_counts = {}
    for word in words:
        if word in word_counts:
            word_counts[word] += 1
        else:
            word_counts[word] = 1
    return word_counts
''',
            # Additional templates for more Type-2 pairs
            '''def reverse_list(items):
    """Reverse a list in place."""
        left = 0
    right = len(items) - 1
    while left < right:
        items[left], items[right] = items[right], items[left]
        left += 1
        right -= 1
    return items
''',
            '''def factorial(n):
    """Calculate the factorial of a number."""
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result = result * i
    return result
''',
            '''def fibonacci(n):
    """Generate fibonacci sequence up to n terms."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    sequence = [0, 1]
    for i in range(2, n):
        next_val = sequence[i-1] + sequence[i-2]
        sequence.append(next_val)
    return sequence
''',
            '''def is_prime(number):
    """Check if a number is prime."""
    if number < 2:
        return False
    for i in range(2, int(number ** 0.5) + 1):
        if number % i == 0:
            return False
    return True
''',
            '''def merge_sorted_lists(list1, list2):
    """Merge two sorted lists into one sorted list."""
    merged = []
    i = 0
    j = 0
    while i < len(list1) and j < len(list2):
        if list1[i] < list2[j]:
            merged.append(list1[i])
            i += 1
        else:
            merged.append(list2[j])
            j += 1
    merged.extend(list1[i:])
    merged.extend(list2[j:])
    return merged
''',
            '''def linear_search(arr, target):
    """Search for target using linear search."""
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
''',
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
            '''def insertion_sort(arr):
    """Sort array using insertion sort."""
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    return arr
''',
            '''def selection_sort(arr):
    """Sort array using selection sort."""
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
''',
            '''def gcd(a, b):
    """Calculate greatest common divisor."""
    while b != 0:
        a, b = b, a % b
    return a
''',
            '''def lcm(a, b):
    """Calculate least common multiple."""
    greater = max(a, b)
    while True:
        if greater % a == 0 and greater % b == 0:
            return greater
        greater += 1
''',
            '''def flatten_list(nested):
    """Flatten a nested list."""
    flat = []
    for item in nested:
        if isinstance(item, list):
            flat.extend(flatten_list(item))
        else:
            flat.append(item)
    return flat
''',
            '''def remove_duplicates(arr):
    """Remove duplicates from list."""
    seen = set()
    result = []
    for item in arr:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
''',
            '''def rotate_list(arr, k):
    """Rotate list by k positions."""
    n = len(arr)
    k = k % n
    return arr[-k:] + arr[:-k]
''',
            '''def matrix_multiply(a, b):
    """Multiply two matrices."""
    rows_a = len(a)
    cols_a = len(a[0])
    cols_b = len(b[0])
    result = [[0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result
''',
            '''def selection_sort(arr):
    """Sort using selection sort."""
    for i in range(len(arr)):
        min_idx = i
        for j in range(i+1, len(arr)):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
''',
            '''def insertion_sort(arr):
    """Sort using insertion sort."""
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    return arr
''',
            '''def quick_sort(arr):
    """Sort using quicksort."""
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)
''',
            '''def merge_sort(arr):
    """Sort using merge sort."""
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
            '''def heap_sort(arr):
    """Sort using heap sort."""
    n = len(arr)
    for i in range(n // 2 - 1, -1, -1):
        heapify(arr, n, i)
    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]
        heapify(arr, i, 0)
    return arr

def heapify(arr, n, i):
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2
    if left < n and arr[left] > arr[largest]:
        largest = left
    if right < n and arr[right] > arr[largest]:
        largest = right
    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        heapify(arr, n, largest)
''',
            '''def counting_sort(arr):
    """Sort using counting sort."""
    if not arr:
        return arr
    max_val = max(arr)
    count = [0] * (max_val + 1)
    for num in arr:
        count[num] += 1
    result = []
    for i, c in enumerate(count):
        result.extend([i] * c)
    return result
''',
            '''def bucket_sort(arr):
    """Sort using bucket sort."""
    if not arr:
        return arr
    max_val = max(arr)
    bucket_count = len(arr)
    buckets = [[] for _ in range(bucket_count + 1)]
    for num in arr:
        idx = int(num * bucket_count / (max_val + 1))
        buckets[idx].append(num)
    for bucket in buckets:
        bucket.sort()
    result = []
    for bucket in buckets:
        result.extend(bucket)
    return result
''',
            '''def shell_sort(arr):
    """Sort using shell sort."""
    n = len(arr)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            temp = arr[i]
            j = i
            while j >= gap and arr[j - gap] > temp:
                arr[j] = arr[j - gap]
                j -= gap
            arr[j] = temp
        gap //= 2
    return arr
''',
            '''def binary_search(arr, target):
    """Find element using binary search."""
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 20
        else:
            right = mid - 1
    return -1
''',
            '''def depth_first_search(graph, start):
    """Traverse graph using DFS."""
    visited = set()
    stack = [start]
    result = []
    while stack:
        node = stack.pop()
        if node not in visited:
            visited.add(node)
            result.append(node)
            stack.extend(reversed(graph.get(node, [])))
    return result
''',
            '''def breadth_first_search(graph, start):
    """Traverse graph using BFS."""
    visited = {start}
    queue = [start]
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return result
''',
            '''def dijkstra(graph, start):
    """Find shortest paths using Dijkstra's algorithm."""
    distances = {node: float('inf') for node in graph}
    distances[start] = 0
    visited = set()
    while len(visited) < len(graph):
        current = min((n for n in graph if n not in visited),
                     key=lambda n: distances[n], default=None)
        if current is None:
            break
        visited.add(current)
        for neighbor, weight in graph[current]:
            new_dist = distances[current] + weight
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
    return distances
''',
            '''def floyd_warshall(graph):
    """Find all-pairs shortest paths."""
    nodes = list(graph.keys())
    n = len(nodes)
    dist = [[float('inf')] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
    for i, u in enumerate(nodes):
        for v, w in graph[u]:
            j = nodes.index(v)
            dist[i][j] = w
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][j] > dist[i][k] + dist[k][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
    return dist
''',
            '''def topological_sort(graph):
    """Topological sort using Kahn's algorithm."""
    in_degree = {node: 0 for node in graph}
    for node in graph:
        for neighbor in graph[node]:
            in_degree[neighbor] += 1
    queue = [n for n in in_degree if in_degree[n] == 0]
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    return result if len(result) == len(graph) else []
''',
            '''def knapsack(items, capacity):
    """Solve 0/1 knapsack problem."""
    n = len(items)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        weight, value = items[i-1]
        for w in range(capacity + 1):
            if weight <= w:
                dp[i][w] = max(dp[i-1][w], dp[i-1][w-weight] + value)
            else:
                dp[i][w] = dp[i-1][w]
    return dp[n][capacity]
''',
            '''def lcs(str1, str2):
    """Find longest common subsequence."""
    m, n = len(str1), len(str2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i-1] == str2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]
''',
            '''def edit_distance(str1, str2):
    """Calculate edit distance between two strings."""
    m, n = len(str1), len(str2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str1[i-1] == str2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[m][n]
''',
            '''def n_queens(n):
    """Solve N-Queens problem."""
    def is_safe(board, row, col):
        for i in range(row):
            if board[i] == col or abs(board[i] - col) == abs(i - row):
                return False
        return True
    def solve(board, row):
        if row == n:
            return 1
        count = 0
        for col in range(n):
            if is_safe(board, row, col):
                board[row] = col
                count += solve(board, row + 1)
        return count
    return solve([0] * n, 0)
''',
            '''def matrix_chain_order(dims):
    """Find optimal matrix chain multiplication order."""
    n = len(dims) - 1
    dp = [[float('inf')] * (n + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][i] = 0
    for length in range(2, n + 1):
        for i in range(1, n - length + 2):
            j = i + length - 1
            for k in range(i, j):
                cost = dp[i][k] + dp[k+1][j] + dims[i-1] * dims[k] * dims[j]
                dp[i][j] = min(dp[i][j], cost)
    return dp[1][n]
''',
            '''def coin_change(coins, amount):
    """Find minimum coins for change."""
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    for coin in coins:
        for i in range(coin, amount + 1):
            dp[i] = min(dp[i], dp[i - coin] + 1)
    return dp[amount] if dp[amount] != float('inf') else -1
''',
            '''def subset_sum(nums, target):
    """Check if subset sums to target."""
    possible = {0}
    for num in nums:
        possible |= {s + num for s in possible}
    return target in possible
''',
            '''def max_subarray(arr):
    """Find maximum subarray sum (Kadane's)."""
    max_sum = float('-inf')
    current = 0
    for num in arr:
        current = max(num, current + num)
        max_sum = max(max_sum, current)
    return max_sum
''',
            '''def longest_increasing_subsequence(arr):
    """Find length of LIS."""
    if not arr:
        return 0
    dp = [1] * len(arr)
    for i in range(1, len(arr)):
        for j in range(i):
            if arr[j] < arr[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)
''',
            '''def word_break(s, word_dict):
    """Check if string can be segmented into words."""
    n = len(s)
    dp = [False] * (n + 1)
    dp[0] = True
    for i in range(1, n + 1):
        for j in range(i):
            if dp[j] and s[j:i] in word_dict:
                dp[i] = True
                break
    return dp[n]
''',
            '''def palindrome_partitioning(s):
    """Find if string can be partitioned into palindromes."""
    n = len(s)
    is_pal = [[False] * n for _ in range(n)]
    for i in range(n):
        is_pal[i][i] = True
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            if s[i] == s[j] and (length == 2 or is_pal[i+1][j-1]):
                is_pal[i][j] = True
    dp = [float('inf')] * (n + 1)
    dp[0] = 0
    for i in range(1, n + 1):
        for j in range(i):
            if is_pal[j][i-1]:
                dp[i] = min(dp[i], dp[j] + 1)
    return dp[n]
''',
            '''def job_scheduling(jobs):
    """Schedule jobs to maximize profit."""
    jobs.sort(key=lambda x: x[1])
    n = len(jobs)
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        start, end, profit = jobs[i-1]
        j = i - 1
        while j > 0 and jobs[j-1][1] > start:
            j -= 1
        dp[i] = max(dp[i-1], dp[j] + profit)
    return dp[n]
''',
            '''def activity_selection(activities):
    """Select maximum non-overlapping activities."""
    activities.sort(key=lambda x: x[1])
    result = [activities[0]]
    for activity in activities[1:]:
        if activity[0] >= result[-1][1]:
            result.append(activity)
    return result
''',
            '''def huffman_encoding(freq):
    """Build Huffman tree for encoding."""
    import heapq
    heap = [(f, [c, ""]) for c, f in freq.items()]
    heapq.heapify(heap)
    while len(heap) > 1:
        lo = heapq.heappop(heap)
        hi = heapq.heappop(heap)
        for pair in lo[1:]:
            pair[1] = '0' + pair[1]
        for pair in hi[1:]:
            pair[1] = '1' + pair[1]
        heapq.heappush(heap, (lo[0] + hi[0], lo[1:] + hi[1:]))
    return sorted(heapq.heappop(heap)[1:], key=lambda p: (len(p[-1]), p))
''',
            '''def kruskal_mst(vertices, edges):
    """Find minimum spanning tree using Kruskal's."""
    parent = {v: v for v in vertices}
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    def union(x, y):
        parent[find(x)] = find(y)
    mst = []
    edges.sort(key=lambda x: x[2])
    for u, v, w in edges:
        if find(u) != find(v):
            union(u, v)
            mst.append((u, v, w))
    return mst
''',
            '''def prim_mst(graph, start):
    """Find minimum spanning tree using Prim's."""
    mst = []
    visited = {start}
    edges = [(w, start, v) for v, w in graph[start]]
    import heapq
    heapq.heapify(edges)
    while edges:
        w, u, v = heapq.heappop(edges)
        if v not in visited:
            visited.add(v)
            mst.append((u, v, w))
            for next_v, next_w in graph[v]:
                if next_v not in visited:
                    heapq.heappush(edges, (next_w, v, next_v))
    return mst
''',
        ]
    
    def generate_pair_count(
        self,
        type1: int = 50,
        type2: int = 50,
        type3: int = 50,
        type4: int = 50,
        non_clone: int = 200
    ) -> SyntheticDataset:
        """Generate a synthetic dataset with specified pair counts.
        
        Args:
            type1: Number of Type-1 (identical) clone pairs.
            type2: Number of Type-2 (renamed) clone pairs.
            type3: Number of Type-3 (restructured) clone pairs.
            type4: Number of Type-4 (semantic) clone pairs.
            non_clone: Number of non-clone pairs.
            
        Returns:
            Generated SyntheticDataset.
        """
        pairs: List[SyntheticPair] = []
        pair_id = 0
        
        generators = {
            1: (generate_type1_pair, "none"),
            2: (generate_type2_pair, "rename"),
            3: (generate_type3_pair, "reorder"),
            4: (generate_type4_pair, "restructure"),
        }
        
        for clone_type, count, label in [
            (1, type1, 1),
            (2, type2, 1),
            (3, type3, 1),
            (4, type4, 1),
            (0, non_clone, 0),
        ]:
            for i in range(count):
                base_code = self._rng.choice(self._base_codes)
                seed = self._seed + pair_id
                
                if clone_type == 0:
                    code_a, code_b = generate_non_clone_pair(
                        base_code, seed, self._language
                    )
                    obfuscation = "different"
                    gen_func = None
                else:
                    gen_func, obfuscation = generators[clone_type]
                    code_a, code_b = gen_func(base_code, seed)
                
                pairs.append(SyntheticPair(
                    id=f"synthetic_{pair_id:05d}",
                    code_a=code_a,
                    code_b=code_b,
                    clone_type=clone_type,
                    label=label,
                    obfuscation=obfuscation,
                    metadata={
                        "base_code_index": self._base_codes.index(base_code),
                        "seed": seed,
                    },
                ))
                pair_id += 1
        
        # Shuffle pairs for unbiased evaluation
        self._rng.shuffle(pairs)
        
        return SyntheticDataset(pairs=pairs)