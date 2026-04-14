"""
Dataset Ground Truth Loader and Evaluation Protocol.

Provides:
- Ground truth dataset loading (JSON, CSV, YAML)
- Pair-level label management
- Evaluation protocol definition
- Synthetic dataset generation with controlled clone types
- BigCloneBench, POJ-104, and other standard dataset adapters
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GroundTruthPair:
    """A single pair with ground truth label."""
    file1: str
    file2: str
    label: int
    clone_type: Optional[int] = None
    difficulty: Optional[str] = None
    language: Optional[str] = None
    code_a: str = ""
    code_b: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationProtocol:
    """Defines how evaluation should be conducted."""
    name: str
    description: str
    threshold: float = 0.5
    ci_level: float = 0.95
    n_bootstrap: int = 1000
    min_pairs: int = 100
    clone_types: List[int] = field(default_factory=lambda: [1, 2, 3, 4])
    metrics: List[str] = field(default_factory=lambda: ["precision", "recall", "f1", "auc_roc"])
    significance_tests: List[str] = field(default_factory=lambda: ["mcnemar", "bootstrap_ci"])
    seed: int = 42

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "threshold": self.threshold,
            "ci_level": self.ci_level,
            "n_bootstrap": self.n_bootstrap,
            "min_pairs": self.min_pairs,
            "clone_types": self.clone_types,
            "metrics": self.metrics,
            "significance_tests": self.significance_tests,
            "seed": self.seed,
        }


DEFAULT_PROTOCOL = EvaluationProtocol(
    name="default",
    description="Default evaluation protocol with bootstrap CI and McNemar's test",
    threshold=0.5,
    ci_level=0.95,
    n_bootstrap=1000,
    clone_types=[1, 2, 3, 4],
)


class GroundTruthLoader(ABC):
    """Abstract base for loading ground truth datasets."""

    @abstractmethod
    def load(self, path: Path) -> List[GroundTruthPair]:
        pass


class JSONGroundTruthLoader(GroundTruthLoader):
    """Loads ground truth from JSON format.

    Expected format:
    {
        "dataset_name": "poj-104",
        "language": "c",
        "pairs": [
            {"file1": "a.c", "file2": "b.c", "label": 1, "clone_type": 2},
            ...
        ]
    }
    """

    def load(self, path: Path) -> List[GroundTruthPair]:
        data = json.loads(path.read_text())
        pairs = []
        for p in data.get("pairs", []):
            pairs.append(GroundTruthPair(
                file1=p["file1"],
                file2=p["file2"],
                label=int(p["label"]),
                clone_type=p.get("clone_type"),
                difficulty=p.get("difficulty"),
                language=p.get("language", data.get("language")),
                code_a=p.get("code_a", ""),
                code_b=p.get("code_b", ""),
                metadata=p.get("metadata", {}),
            ))
        return pairs


class CSVGroundTruthLoader(GroundTruthLoader):
    """Loads ground truth from CSV format.

    Expected columns: file1, file2, label, clone_type (optional), difficulty (optional)
    """

    def load(self, path: Path) -> List[GroundTruthPair]:
        pairs = []
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pairs.append(GroundTruthPair(
                    file1=row["file1"],
                    file2=row["file2"],
                    label=int(row["label"]),
                    clone_type=int(row["clone_type"]) if "clone_type" in row and row["clone_type"] else None,
                    difficulty=row.get("difficulty"),
                    code_a=row.get("code_a", ""),
                    code_b=row.get("code_b", ""),
                ))
        return pairs


class BigCloneBenchLoader(GroundTruthLoader):
    """
    Loads BigCloneBench dataset.

    BigCloneBench contains Java clones with Type-1 through Type-4 labels.
    Requires the BigCloneBench directory structure.
    """

    CLONE_TYPE_MAP = {
        "Type-I": 1,
        "Type-II": 2,
        "Type-III": 3,
        "Type-IV": 4,
    }

    def load(self, path: Path) -> List[GroundTruthPair]:
        pairs = []
        bcb_pairs = path / "pairs.csv"
        if bcb_pairs.exists():
            with open(bcb_pairs, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    clone_type_str = row.get("type", "")
                    clone_type = self.CLONE_TYPE_MAP.get(clone_type_str)
                    if clone_type is None:
                        try:
                            clone_type = int(clone_type_str)
                        except (ValueError, TypeError):
                            clone_type = None
                    pairs.append(GroundTruthPair(
                        file1=row.get("func1", ""),
                        file2=row.get("func2", ""),
                        label=1,
                        clone_type=clone_type,
                        language="java",
                    ))

        non_clones_file = path / "non_clones.csv"
        if non_clones_file.exists():
            with open(non_clones_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pairs.append(GroundTruthPair(
                        file1=row.get("func1", ""),
                        file2=row.get("func2", ""),
                        label=0,
                        language="java",
                    ))

        return pairs


class POJ104Loader(GroundTruthLoader):
    """
    Loads POJ-104 dataset.

    POJ-104 contains C programs from a programming contest,
    grouped by problem. Programs in the same group are clones.
    """

    def load(self, path: Path) -> List[GroundTruthPair]:
        pairs = []
        groups = {}
        for f in sorted(path.iterdir()):
            if f.is_file() and f.suffix == ".c":
                problem_id = f.stem.split("_")[0] if "_" in f.stem else f.stem
                groups.setdefault(problem_id, []).append(f)

        for problem_id, files in groups.items():
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    pairs.append(GroundTruthPair(
                        file1=str(files[i].name),
                        file2=str(files[j].name),
                        label=1,
                        clone_type=3,
                        language="c",
                        code_a=files[i].read_text(errors="ignore"),
                        code_b=files[j].read_text(errors="ignore"),
                    ))

        cross_problem = list(groups.values())
        rng = random.Random(42)
        for i in range(len(cross_problem)):
            for j in range(i + 1, min(i + 5, len(cross_problem))):
                f1 = rng.choice(cross_problem[i])
                f2 = rng.choice(cross_problem[j])
                pairs.append(GroundTruthPair(
                    file1=str(f1.name),
                    file2=str(f2.name),
                    label=0,
                    language="c",
                ))

        return pairs


class SyntheticDatasetGenerator:
    """
    Generates synthetic datasets with controlled clone types for testing.

    Creates realistic code pairs with known ground truth labels.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate(
        self,
        num_type1: int = 20,
        num_type2: int = 20,
        num_type3: int = 20,
        num_type4: int = 10,
        num_non_clone: int = 50,
        language: str = "python",
    ) -> List[GroundTruthPair]:
        pairs = []
        pairs.extend(self._generate_type1(num_type1, language))
        pairs.extend(self._generate_type2(num_type2, language))
        pairs.extend(self._generate_type3(num_type3, language))
        pairs.extend(self._generate_type4(num_type4, language))
        pairs.extend(self._generate_non_clones(num_non_clone, language))
        return pairs

    def _generate_type1(self, n: int, lang: str) -> List[GroundTruthPair]:
        pairs = []
        for i in range(n):
            code = self._random_function(lang)
            pairs.append(GroundTruthPair(
                file1=f"type1_a_{i}.{lang[:2]}",
                file2=f"type1_b_{i}.{lang[:2]}",
                label=1,
                clone_type=1,
                difficulty="easy",
                language=lang,
                code_a=code,
                code_b=code,
            ))
        return pairs

    def _generate_type2(self, n: int, lang: str) -> List[GroundTruthPair]:
        pairs = []
        for i in range(n):
            code_a = self._random_function(lang)
            code_b = self._rename_variables(code_a)
            pairs.append(GroundTruthPair(
                file1=f"type2_a_{i}.{lang[:2]}",
                file2=f"type2_b_{i}.{lang[:2]}",
                label=1,
                clone_type=2,
                difficulty="medium",
                language=lang,
                code_a=code_a,
                code_b=code_b,
            ))
        return pairs

    def _generate_type3(self, n: int, lang: str) -> List[GroundTruthPair]:
        pairs = []
        for i in range(n):
            code_a = self._random_function(lang)
            code_b = self._modify_statements(code_a)
            pairs.append(GroundTruthPair(
                file1=f"type3_a_{i}.{lang[:2]}",
                file2=f"type3_b_{i}.{lang[:2]}",
                label=1,
                clone_type=3,
                difficulty="hard",
                language=lang,
                code_a=code_a,
                code_b=code_b,
            ))
        return pairs

    def _generate_type4(self, n: int, lang: str) -> List[GroundTruthPair]:
        pairs = []
        for i in range(n):
            code_a, code_b = self._semantic_equivalent_pair(lang)
            pairs.append(GroundTruthPair(
                file1=f"type4_a_{i}.{lang[:2]}",
                file2=f"type4_b_{i}.{lang[:2]}",
                label=1,
                clone_type=4,
                difficulty="very_hard",
                language=lang,
                code_a=code_a,
                code_b=code_b,
            ))
        return pairs

    def _generate_non_clones(self, n: int, lang: str) -> List[GroundTruthPair]:
        pairs = []
        for i in range(n):
            code_a = self._random_function(lang)
            code_b = self._random_function(lang)
            while self._similarity(code_a, code_b) > 0.3:
                code_b = self._random_function(lang)
            pairs.append(GroundTruthPair(
                file1=f"nonclone_a_{i}.{lang[:2]}",
                file2=f"nonclone_b_{i}.{lang[:2]}",
                label=0,
                language=lang,
                code_a=code_a,
                code_b=code_b,
            ))
        return pairs

    def _random_function(self, lang: str) -> str:
        templates = {
            "python": [
                "def func_{name}(x, y):\n    result = x + y\n    return result * {factor}",
                "def func_{name}(data):\n    total = 0\n    for item in data:\n        total += item * {factor}\n    return total",
                "def func_{name}(n):\n    if n <= 1:\n        return n\n    return func_{name}(n-1) + func_{name}(n-2)",
                "def func_{name}(lst):\n    return sorted(lst, reverse={reverse})[:{limit}]",
                "def func_{name}(s):\n    return ''.join(reversed(s.split())) if len(s) > {limit} else s",
            ],
            "java": [
                "public int func{Name}(int x, int y) {{\n    return (x + y) * {factor};\n}}",
                "public int func{Name}(int[] data) {{\n    int total = 0;\n    for (int item : data) total += item * {factor};\n    return total;\n}}",
                "public int func{Name}(int n) {{\n    if (n <= 1) return n;\n    return func{Name}(n-1) + func{Name}(n-2);\n}}",
            ],
            "c": [
                "int func_{name}(int x, int y) {{\n    return (x + y) * {factor};\n}}",
                "int func_{name}(int arr[], int n) {{\n    int total = 0;\n    for (int i = 0; i < n; i++) total += arr[i] * {factor};\n    return total;\n}}",
            ],
        }
        templates = templates.get(lang, templates["python"])
        template = self.rng.choice(templates)
        name = self.rng.randint(1000, 9999)
        factor = self.rng.randint(2, 10)
        reverse = self.rng.choice([True, False])
        limit = self.rng.randint(3, 10)
        return template.format(name=name, factor=factor, reverse=reverse, limit=limit)

    def _rename_variables(self, code: str) -> str:
        import re
        reserved = {
            'def', 'return', 'if', 'for', 'in', 'while', 'import',
            'from', 'class', 'self', 'True', 'False', 'None',
            'int', 'float', 'str', 'list', 'dict', 'set', 'tuple',
            'range', 'len', 'print', 'sorted', 'reversed', 'join',
            'split', 'public', 'static', 'void', 'else',
        }
        var_map = {}
        for match in re.findall(r'\b([a-z_]\w*)\b', code):
            if match not in reserved and match not in var_map:
                var_map[match] = f"var_{self.rng.randint(100, 999)}"
        result = code
        for old, new in var_map.items():
            result = re.sub(r'\b' + re.escape(old) + r'\b', new, result)
        return result

    def _modify_statements(self, code: str) -> str:
        lines = code.split("\n")
        modified = []
        for line in lines:
            if self.rng.random() < 0.3:
                if "+" in line:
                    line = line.replace("+", "- -", 1)
                elif "return" in line and "*" in line:
                    line = line.replace("*", "* 1 *", 1)
            modified.append(line)
        if self.rng.random() < 0.5:
            idx = self.rng.randint(1, max(1, len(modified) - 1))
            modified.insert(idx, "    # optimization")
        return "\n".join(modified)

    def _semantic_equivalent_pair(self, lang: str) -> Tuple[str, str]:
        if lang == "python":
            a = "def func(n):\n    result = 0\n    for i in range(n):\n        result += i\n    return result"
            b = "def func(n):\n    return n * (n - 1) // 2"
        elif lang == "java":
            a = "public int func(int n) {\n    int result = 0;\n    for (int i = 0; i < n; i++) result += i;\n    return result;\n}"
            b = "public int func(int n) {\n    return n * (n - 1) / 2;\n}"
        else:
            a = "int func(int n) {\n    int result = 0;\n    for (int i = 0; i < n; i++) result += i;\n    return result;\n}"
            b = "int func(int n) {\n    return n * (n - 1) / 2;\n}"
        return a, b

    def _similarity(self, a: str, b: str) -> float:
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def load_ground_truth(
    path: Path,
    format: Optional[str] = None,
) -> List[GroundTruthPair]:
    """
    Auto-detect and load ground truth dataset.

    Args:
        path: Path to dataset file or directory.
        format: Optional format override ('json', 'csv', 'bigclonebench', 'poj104').

    Returns:
        List of GroundTruthPair objects.
    """
    if format is None:
        if path.is_dir():
            if (path / "pairs.csv").exists():
                format = "bigclonebench"
            elif any(f.suffix == ".c" for f in path.iterdir()):
                format = "poj104"
            else:
                format = "json"
        elif path.suffix == ".json":
            format = "json"
        elif path.suffix == ".csv":
            format = "csv"
        else:
            format = "json"

    loaders = {
        "json": JSONGroundTruthLoader,
        "csv": CSVGroundTruthLoader,
        "bigclonebench": BigCloneBenchLoader,
        "poj104": POJ104Loader,
    }

    loader_cls = loaders.get(format)
    if not loader_cls:
        raise ValueError(f"Unknown format: {format}. Available: {list(loaders.keys())}")

    return loader_cls().load(path)


def build_score_label_arrays(
    tool_findings: Dict[str, List[Dict[str, Any]]],
    ground_truth: Dict[Tuple[str, str], int],
) -> Tuple[Dict[str, List[float]], List[int]]:
    """
    Build aligned score and label arrays for evaluation.

    Args:
        tool_findings: Dict mapping tool name to list of finding dicts with file1, file2, similarity.
        ground_truth: Dict mapping (file1, file2) tuples to labels.

    Returns:
        Tuple of (tool_scores dict, shared labels list).
    """
    all_pairs = set()
    for findings in tool_findings.values():
        for f in findings:
            key = tuple(sorted([f.get("file1", ""), f.get("file2", "")]))
            all_pairs.add(key)

    for pair in ground_truth.keys():
        all_pairs.add(tuple(sorted(pair)))

    all_pairs = sorted(all_pairs)
    labels = [ground_truth.get(p, 0) for p in all_pairs]

    tool_scores = {}
    for tool_name, findings in tool_findings.items():
        pair_scores = {tuple(sorted([f.get("file1", ""), f.get("file2", "")])): f.get("similarity", 0.0)
                       for f in findings}
        tool_scores[tool_name] = [pair_scores.get(p, 0.0) for p in all_pairs]

    return tool_scores, labels
