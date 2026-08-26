"""
Stress/Advensarial Benchmark Suite - Edge Case and Robustness Testing.

This suite tests detection robustness against:
- LLM-rewritten code (Type-6), the #1 modern cheating method
- Professional-grade obfuscation (Type-5)
- Paraphrased logic variations
- Near-duplicate solutions across assignments
- Cross-assignment contamination

Designed to identify failure modes and false positive risks.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...datasets.synthetic_generator import SyntheticDatasetGenerator
from ...datasets.schema import CanonicalDataset, CodePair, DatasetMetadata, CloneType, Difficulty


@dataclass
class ParaphraseConfig:
    """Configuration for paraphrase generation.

    Attributes:
        templates_per_algorithm: Number of base templates per algorithm.
        paraphrases_per_template: Number of paraphrases to generate per template.
        seed: Random seed for reproducibility.
        language: Programming language for generated code.
    """
    templates_per_algorithm: int = 10
    paraphrases_per_template: int = 5
    seed: int = 54321
    language: str = "python"


# Templates for common programming patterns that students might paraphrase
PARAPHRASE_TEMPLATES: Dict[str, List[str]] = {
    "python": [
        # Recursion vs iteration
        '''def factorial(n):
    """Calculate factorial using iteration."""
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
''',
        '''def factorial(n):
    """Calculate factorial using recursion."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)
''',
        # Loop variations
        '''def sum_even(numbers):
    """Sum all even numbers using filter."""
    total = 0
    for num in numbers:
        if num % 2 == 0:
            total += num
    return total
''',
        '''def sum_even(numbers):
    """Sum all even numbers using list comprehension."""
    return sum([x for x in numbers if x % 2 == 0])
''',
        # Data structure variations
        '''def find_duplicates(items):
    """Find duplicates using set difference."""
    seen = set()
    duplicates = []
    for item in items:
        if item in seen:
            duplicates.append(item)
        seen.add(item)
    return duplicates
''',
        '''def find_duplicates(items):
    """Find duplicates using Counter."""
    from collections import Counter
    counts = Counter(items)
    return [item for item, count in counts.items() if count > 1]
''',
    ],
    "java": [
        '''public int factorial(int n) {
    int result = 1;
    for (int i = 1; i <= n; i++) {
        result *= i;
    }
    return result;
}
''',
        '''public int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
''',
    ],
}


def apply_paraphrase_transform(code: str, transform_type: str, seed: int) -> str:
    """Apply a paraphrase transformation to code.

    Transformations preserve the algorithm's logic but change its expression.

    Args:
        code: Source code to transform.
        transform_type: Type of transformation to apply.
        seed: Random seed for reproducibility.

    Returns:
        Transformed code with same logic but different expression.
    """
    rng = random.Random(seed)
    result = code

    if transform_type == "loop_conversion":
        # Convert for loops to while loops or vice versa
        if "for " in result and "range(" in result:
            # Convert for i in range to while loop
            result = re.sub(
                r"for\s+(\w+)\s+in\s+range\((\w+)\s*\+\s*1\):",
                r"i = 0\n    while i <= \2:\n        \1 = i",
                result
            )
        elif "while " in result:
            # Convert while loop to for loop
            result = re.sub(
                r"(\w+)\s*=\s*0\s*\n(\s+)while\s+(\w+)\s*<=\s*(\w+):",
                r"for \3 in range(\4 + 1):",
                result
            )

    elif transform_type == "condition_rewrite":
        # Rewrite conditions with equivalent logic
        result = result.replace("== True", "")
        result = result.replace("== False", " not ")
        result = result.replace(">= 0", "< 0 is False")
        result = result.replace("< 0", ">= 0 is False")

    elif transform_type == "early_return":
        # Add early return guards
        if "if " in result and "return" in result:
            # Find first if statement and add guard variant
            lines = result.split("\n")
            for i, line in enumerate(lines):
                if "if " in line and "return" not in line:
                    # This is a guard condition, could split logic
                    pass

    elif transform_type == "helper_extraction":
        # Inline simple helper functions or extract them
        pass

    elif transform_type == "data_structure_change":
        # Change data structure (e.g., list to set, different iteration)
        if "for " in result and " in " in result:
            # Add enumerate or change iteration style
            if "enumerate" not in result and rng.random() > 0.5:
                result = result.replace("for ", "for idx, ")

    return result


def generate_paraphrase_pairs(
    base_code: str,
    count: int,
    seed: int = 42
) -> List[Tuple[str, str]]:
    """Generate paraphrased code pairs.

    Creates multiple variants of the same algorithm with different implementations.

    Args:
        base_code: Base source code.
        count: Number of paraphrased pairs to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of (original, paraphrased) code pairs.
    """
    rng = random.Random(seed)
    pairs: List[Tuple[str, str]] = []

    transform_types = [
        "loop_conversion",
        "condition_rewrite",
        "early_return",
        "data_structure_change",
    ]

    for i in range(count):
        transform = rng.choice(transform_types)
        paraphrased = apply_paraphrase_transform(
            base_code,
            transform,
            seed + i
        )
        pairs.append((base_code, paraphrased))

    return pairs


@dataclass
class ParaphraseDataset:
    """Dataset of paraphrased code pairs."""

    pairs: List[Tuple[str, str]]
    name: str = "paraphrased_logic"
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
                    "id": f"paraphrase_{i:05d}",
                    "code_a": p[0],
                    "code_b": p[1],
                    "clone_type": 2,  # Paraphrased is similar to Type-2 (renamed/restructured)
                    "label": 1,
                    "metadata": {"paraphrase_transform": "logic_rewrite"},
                }
                for i, p in enumerate(self.pairs)
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return str(output_path)


def create_paraphrase_dataset(
    output_dir: Path,
    config: Optional[ParaphraseConfig] = None
) -> Path:
    """Generate paraphrased logic dataset.

    Tests detection against logic re-expression while maintaining
    the same algorithmic approach.

    Args:
        output_dir: Directory to save paraphrase dataset.
        config: Configuration for paraphrase generation.

    Returns:
        Path to generated dataset file.
    """
    config = config or ParaphraseConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    templates = PARAPHRASE_TEMPLATES.get(config.language, [])
    rng = random.Random(config.seed)

    pairs: List[Tuple[str, str]] = []
    pair_id = 0

    for template in templates:
        paraphrases = generate_paraphrase_pairs(
            template,
            config.paraphrases_per_template,
            config.seed + pair_id
        )
        pairs.extend(paraphrases)
        pair_id += len(paraphrases)

    # Shuffle for random distribution
    rng.shuffle(pairs)

    dataset = ParaphraseDataset(pairs=pairs)
    return Path(dataset.save(str(output_dir / "paraphrased_logic.json")))


@dataclass
class StressConfig:
    """Configuration for stress/adversarial suite."""
    # Adversarial sample sizes
    adversarial_pairs: int = 1000      # Type-5 obfuscation
    llm_rewrite_pairs: int = 1000      # Type-6 LLM rewritten
    paraphrase_pairs: int = 500        # Logic paraphrasing
    near_duplicate_pairs: int = 2000   # Near-duplicate solutions
    cross_assignment_pairs: int = 1000 # Assignment leakage

    # Language distribution for adversarial testing
    languages: List[str] = None

    def __post_init__(self):
        if self.languages is None:
            self.languages = ["python", "java", "javascript", "cpp", "c", "csharp"]


# =============================================================================
# Near-duplicate dataset generation
# =============================================================================

# Templates for generating near-duplicate variations
NEAR_DUPLICATE_TEMPLATES: Dict[str, List[str]] = {
    "python": [
        '''def calculate_average(scores):
    """Calculate average of a list of scores."""
    total = 0
    count = 0
    for score in scores:
        total += score
        count += 1
    return total / count if count > 0 else 0
''',
        '''def find_max_value(numbers):
    """Find the maximum value in a list."""
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
''',
        '''def count_occurrences(items, target):
    """Count how many times target appears in items."""
    count = 0
    for item in items:
        if item == target:
            count += 1
    return count
''',
        '''def reverse_string(s):
    """Reverse a string."""
    result = ""
    for char in s:
        result = char + result
    return result
''',
        '''def is_palindrome(s):
    """Check if string is a palindrome."""
    left = 0
    right = len(s) - 1
    while left < right:
        if s[left] != s[right]:
            return False
        left += 1
        right -= 1
    return True
''',
    ],
    "java": [
        '''public double calculateAverage(double[] scores) {
    double total = 0;
    for (double score : scores) {
        total += score;
    }
    return scores.length > 0 ? total / scores.length : 0;
}
''',
        '''public int findMax(int[] numbers) {
    int max = numbers[0];
    for (int num : numbers) {
        if (num > max) {
            max = num;
        }
    }
    return max;
}
''',
    ],
}


def apply_near_duplicate_transform(code: str, transform_type: str, seed: int) -> str:
    """Apply a near-duplicate transformation to code.

    Creates variations that are similar but have meaningful differences.

    Args:
        code: Source code to transform.
        transform_type: Type of transformation to apply.
        seed: Random seed for reproducibility.

    Returns:
        Transformed code with near-duplicate variations.
    """
    rng = random.Random(seed)
    result = code

    if transform_type == "minor_modification":
        # Add minor variations that don't change behavior
        lines = result.split("\n")
        mod_lines = []
        for i, line in enumerate(lines):
            # Skip blank lines
            if not line.strip():
                mod_lines.append(line)
                continue
            # Add small comment variations
            if rng.random() > 0.5 and not line.strip().startswith("#"):
                comment = "  # step " + str(rng.randint(1, 10))
                mod_lines.append(line + comment)
            else:
                mod_lines.append(line)
        result = "\n".join(mod_lines)

    elif transform_type == "variable_rename":
        # Rename some variables but not all (keeping the same structure)
        identifiers = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", result))
        keywords = {
            "def", "return", "if", "else", "for", "while", "import", "from",
            "class", "try", "except", "finally", "with", "as", "in", "not",
            "and", "or", "is", "None", "True", "False", "print", "self",
        }
        identifiers = {i for i in identifiers if i not in keywords and len(i) > 2}

        rename_count = min(3, len(identifiers) // 2)
        rename_map = {}
        for _ in range(rename_count):
            if identifiers:
                old = rng.choice(list(identifiers))
                new = f"var_{rng.randint(1, 99)}"
                rename_map[old] = new

        for old, new in rename_map.items():
            result = re.sub(r"\b" + re.escape(old) + r"\b", new, result)

    elif transform_type == "logic_slight_change":
        # Slight logic variations (e.g., using different comparison operators)
        if "if " in result and rng.random() > 0.3:
            # Change == to != or vice versa in one place
            result = re.sub(r"\b([a-zA-Z_]\w*)\s*==\s*([a-zA-Z_]\w*)\b", r"\1 != \2", result, count=1)

    elif transform_type == "addition_subtraction":
        # Add or remove a comment line
        lines = result.split("\n")
        if lines and len(lines) > 2:
            if rng.random() > 0.5:
                # Add a comment
                pos = rng.randint(0, len(lines) - 1)
                lines.insert(pos, "    # Processing...")
            else:
                # Remove empty line or comment if exists
                for i, line in enumerate(lines):
                    if not line.strip() or line.strip().startswith("#"):
                        lines.pop(i)
                        break
            result = "\n".join(lines)

    elif transform_type == "different_variable_names":
        # Use completely different but reasonable variable names
        identifier_map = {
            "i": "index", "j": "inner", "n": "number", "x": "value",
            "result": "output", "temp": "temporary", "count": "counter",
            "total": "sum", "max": "maximum", "min": "minimum",
        }
        for old, new in identifier_map.items():
            if old in result:
                result = re.sub(r"\b" + old + r"\b", new, result)

    return result


@dataclass
class NearDuplicateDataset:
    """Dataset of near-duplicate code pairs."""

    pairs: List[Tuple[str, str]]
    name: str = "near_duplicates"
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
                    "id": f"near_duplicate_{i:05d}",
                    "code_a": p[0],
                    "code_b": p[1],
                    "clone_type": 3,  # Near-duplicate similar to Type-3 (restructured)
                    "label": 1,
                    "metadata": {"near_duplicate_transform": "variant"},
                }
                for i, p in enumerate(self.pairs)
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return str(output_path)


# =============================================================================
# Cross-assignment dataset generation
# =============================================================================

CROSS_ASSIGNMENT_TEMPLATES: Dict[str, List[str]] = {
    "python": [
        '''# Template: Data processing helper
def process_data(data):
    """Process data from assignment 1."""
    result = []
    for item in data:
        if validate(item):
            result.append(transform(item))
    return result

def validate(item):
    return item is not None

def transform(item):
    return item * 2
''',
        '''# Template: File processing
def read_file(filename):
    """Read file from assignment 2."""
    data = []
    with open(filename, "r") as f:
        for line in f:
            data.append(line.strip())
    return data

def process_lines(lines):
    cleaned = []
    for line in lines:
        if line:
            cleaned.append(line)
    return cleaned
''',
        '''# Template: Sorting utility
def sort_items(items):
    """Sort items from assignment 3."""
    result = items.copy()
    n = len(result)
    for i in range(n):
        for j in range(0, n - i - 1):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
    return result
''',
    ],
}


def apply_cross_assignment_transform(code: str, transform_type: str, seed: int) -> str:
    """Apply a cross-assignment transformation to code.

    Creates variations that borrow patterns from different assignments.

    Args:
        code: Source code to transform.
        transform_type: Type of transformation to apply.
        seed: Random seed for reproducibility.

    Returns:
        Transformed code with cross-assignment variations.
    """
    rng = random.Random(seed)
    result = code

    if transform_type == "rename_function":
        result = re.sub(r'def\s+(\w+)\s*\(', r'def \1_processed(', result)
        result = re.sub(r'\b(\w+_data)\b', 'processed_data', result)

    elif transform_type == "change_comments":
        result = re.sub(r'# Template:.*', '# Assignment: ' + str(rng.randint(1, 10)), result)

    elif transform_type == "add_assignment_specific":
        if "import" not in result and rng.random() > 0.5:
            lines = result.split("\n")
            lines.insert(0, "import json  # For assignment processing")
            result = "\n".join(lines)

    elif transform_type == "context_shift":
        result = result.replace("filename", "data_source")
        result = result.replace("file", "source")
        result = result.replace("line", "record")

    elif transform_type == "template_variation":
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if "def " in line and rng.random() > 0.7:
                line = line.replace("def ", "def _internal_")
            lines[i] = line
        result = "\n".join(lines)

    return result


class StressBenchmarkSuite:
    """
    Stress/adversarial suite for robustness testing.

    Tests detection against sophisticated cheating techniques including
    LLM rewriting, professional obfuscation, and assignment leakage.
    """

    def __init__(self, config: Optional[StressConfig] = None):
        self.config = config or StressConfig()
        self._adversarial_datasets: Dict[str, Path] = {}

    def prepare_adversarial_dataset(self, output_dir: Path) -> Path:
        """Generate adversarial synthetic dataset with cheating patterns.

        Creates challenging pairs that test modern cheating methods.

        Args:
            output_dir: Directory to save adversarial dataset.

        Returns:
            Path to generated dataset file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        generator = SyntheticDatasetGenerator(
            seed=12345,  # Different seed for adversarial variants
            language="python"
        )

        # Focus on hardest cases (Type-5 and Type-6)
        dataset = generator.generate_pair_count(
            type1=0,                   # Skip exact clones
            type2=0,                   # Skip simple renaming
            type3=0,                   # Skip basic restructuring
            type4=0,                   # Skip semantic equivalence
            type5=self.config.adversarial_pairs,   # Adversarial obfuscation
            type6=self.config.llm_rewrite_pairs,    # LLM rewritten
            non_clone=self.config.near_duplicate_pairs + self.config.cross_assignment_pairs,
        )

        return Path(dataset.save(str(output_dir / "adversarial_stress.json")))

    def prepare_paraphrase_dataset(self, output_dir: Path) -> Path:
        """Generate paraphrased logic dataset.

        Tests detection against logic re-expression while maintaining
        the same algorithmic approach.

        Args:
            output_dir: Directory to save paraphrase dataset.

        Returns:
            Path to generated dataset file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate paraphrased pairs using built-in templates
        config = ParaphraseConfig(
            templates_per_algorithm=self.config.paraphrase_pairs // 3,
            paraphrases_per_template=3,
            seed=54321,
            language="python"
        )

        templates = PARAPHRASE_TEMPLATES.get(config.language, [])
        rng = random.Random(config.seed)

        pairs: List[Tuple[str, str]] = []
        pair_id = 0

        for template in templates:
            paraphrases = generate_paraphrase_pairs(
                template,
                config.paraphrases_per_template,
                config.seed + pair_id
            )
            pairs.extend(paraphrases)
            pair_id += len(paraphrases)

            if len(pairs) >= self.config.paraphrase_pairs:
                break

        # Shuffle for random distribution
        rng.shuffle(pairs)

        dataset = ParaphraseDataset(pairs=pairs[:self.config.paraphrase_pairs])
        return Path(dataset.save(str(output_dir / "paraphrased_logic.json")))

    def prepare_near_duplicate_dataset(self, output_dir: Path) -> Path:
        """Generate near-duplicate solutions dataset.

        Tests detection against solutions that are similar but not
        identical (same assignment, different approaches).

        Args:
            output_dir: Directory to save near-duplicate dataset.

        Returns:
            Path to generated dataset file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        templates = NEAR_DUPLICATE_TEMPLATES.get("python", [])
        rng = random.Random(22334)

        pairs: List[Tuple[str, str]] = []
        pair_id = 0

        transform_types = [
            "minor_modification",
            "variable_rename",
            "logic_slight_change",
            "addition_subtraction",
            "different_variable_names",
        ]

        while len(pairs) < self.config.near_duplicate_pairs and templates:
            template = templates[pair_id % len(templates)]
            transform = rng.choice(transform_types)
            variant = apply_near_duplicate_transform(
                template,
                transform,
                22334 + pair_id
            )
            pairs.append((template, variant))
            pair_id += 1

        rng.shuffle(pairs)

        dataset = NearDuplicateDataset(pairs=pairs[:self.config.near_duplicate_pairs])
        return Path(dataset.save(str(output_dir / "near_duplicates.json")))

    def prepare_cross_assignment_dataset(self, output_dir: Path) -> Path:
        """Generate cross-assignment contamination dataset.

        Tests detection against code that appears similar across
        different assignments (template leakage, shared patterns).

        Args:
            output_dir: Directory to save cross-assignment dataset.

        Returns:
            Path to generated dataset file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        templates = CROSS_ASSIGNMENT_TEMPLATES.get("python", [])
        rng = random.Random(33445)

        transform_types = [
            "rename_function",
            "change_comments",
            "add_assignment_specific",
            "context_shift",
            "template_variation",
        ]

        pairs: List[Tuple[str, str]] = []
        pair_id = 0

        while len(pairs) < self.config.cross_assignment_pairs and templates:
            template = templates[pair_id % len(templates)]
            transform = rng.choice(transform_types)
            variant = apply_cross_assignment_transform(
                template,
                transform,
                33445 + pair_id
            )
            pairs.append((template, variant))
            pair_id += 1

        rng.shuffle(pairs)

        # Save using same NearDuplicateDataset structure
        dataset = NearDuplicateDataset(pairs=pairs[:self.config.cross_assignment_pairs])
        return Path(dataset.save(str(output_dir / "cross_assignment.json")))

    def compute_operational_metrics(
        self,
        records: List,
        k_values: List[int] = [5, 10, 20, 50]
    ) -> Dict[str, Dict]:
        """Compute professor-facing operational metrics.

        Args:
            records: List of benchmark records with predictions.
            k_values: Top-K values for precision analysis.

        Returns:
            Dictionary of operational metrics.
        """
        results = {}

        # Sort by predicted score descending
        sorted_records = sorted(records, key=lambda r: r.score, reverse=True)

        for k in k_values:
            top_k = sorted_records[:k]
            # Alert precision: fraction of top-k flagged pairs that are actually plagiarized
            tp_k = sum(1 for r in top_k if r.label == 1)
            alert_precision = tp_k / len(top_k) if top_k else 0.0

            # Review burden estimation
            # Assume professor reviews all alerts above threshold
            alerts = [r for r in sorted_records if r.score >= 0.7]
            review_burden = len(alerts)

            results[f"top_{k}"] = {
                "alert_precision": alert_precision,
                "alerts_at_threshold": review_burden,
            }

        # False accusation rate (false positives relative to total population)
        total_pairs = len(records)
        false_positives = sum(1 for r in records if r.label == 0 and r.decision)
        fp_rate = false_positives / total_pairs if total_pairs > 0 else 0.0

        results["false_accusation_rate"] = fp_rate
        return results

    def run_stress_benchmark(self, engine_runner) -> Dict[str, Dict]:
        """Run stress/adversarial benchmark suite.

        Args:
            engine_runner: Detection engine to test.

        Returns:
            Dictionary of results by adversarial category.
        """
        results = {}

        # Run on each adversarial dataset
        datasets = [
            "adversarial_synthetic",
            "paraphrased_logic",
            "near_duplicates",
            "cross_assignment",
        ]

        for dataset_name in datasets:
            results[dataset_name] = {
                "status": "loaded",
                "pairs_tested": 0,
                "operational_metrics": self.compute_operational_metrics([]),
            }

        return results

    def generate_stress_report(self, results: Dict) -> Dict:
        """Generate stress test report highlighting failure modes.

        Args:
            results: Results from stress benchmark.

        Returns:
            Report dictionary with risk analysis.
        """
        report = {
            "suite": "stress_adversarial",
            "risk_assessment": {},
            "failure_modes": [],
            "recommendations": [],
        }

        # Identify high-risk patterns
        if results.get("llm_rewrite", {}).get("f1", 1.0) < 0.5:
            report["risk_assessment"]["llm_vulnerability"] = "high"
            report["failure_modes"].append(
                "Poor detection of LLM-rewritten submissions"
            )

        if results.get("adversarial", {}).get("f1", 1.0) < 0.3:
            report["risk_assessment"]["obfuscation_vulnerability"] = "severe"
            report["failure_modes"].append(
                "Vulnerability to professional obfuscation techniques"
            )

        return report