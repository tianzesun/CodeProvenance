"""External Dataset Loader for benchmark system.

Loads datasets from external benchmark sources (BigCloneBench, POJ-104, CodeXGLUE, etc.)
into the CanonicalDataset format for evaluation.

Supported datasets:
- POJ-104 (C programs from PKU Online Judge)
- CodeXGLUE Clone Detection (Java function pairs)
- CodeXGLUE Defect Detection (C code)
- CodeSearchNet (multi-language functions)
- Kaggle Student Code (Python plagiarism pairs)
"""
from __future__ import annotations

import csv
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.pipeline.loader import CanonicalDataset, CodePair


class ExternalDatasetLoader:
    """Load external benchmark datasets into CanonicalDataset format."""

    def __init__(self, data_root: str = "benchmark/data", seed: int = 42):
        """Initialize loader.

        Args:
            data_root: Root directory for benchmark data.
            seed: Random seed for reproducibility.
        """
        self._data_root = Path(data_root)
        self._rng = random.Random(seed)
        self._dataset_cache: Dict[str, Any] = {}

    def _load_hf_dataset(self, dataset_path: str) -> Any:
        """Load HuggingFace dataset from local disk.

        Args:
            dataset_path: Path to the saved dataset.

        Returns:
            DatasetDict object.

        Raises:
            ImportError: If datasets package is not available.
            FileNotFoundError: If dataset path does not exist.
        """
        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Dataset not found at {dataset_path}")
        try:
            from datasets import load_from_disk
        except ImportError:
            raise ImportError(
                "HuggingFace 'datasets' package required. "
                "Run: ./venv/bin/pip install datasets"
            )
        return load_from_disk(dataset_path)

    def load_poj104(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load POJ-104 dataset (Java programs from PKU Online Judge).

        Programs solving the same problem are considered clones (Type-3).

        Args:
            split: Dataset split to load (train, validation, test).
            max_pairs: Maximum number of pairs to create.

        Returns:
            CanonicalDataset with Java code pairs labeled.
        """
        cache_key = f"poj104_{split}"
        if cache_key in self._dataset_cache:
            data = self._dataset_cache[cache_key]
        else:
            dataset_path = str(self._data_root / "poj104" / "huggingface")
            ds = self._load_hf_dataset(dataset_path)
            self._dataset_cache[cache_key] = ds[split]
            data = self._dataset_cache[cache_key]

        by_label: Dict[int, List[Any]] = {}
        for item in data:
            label_val = int(item.get("label", 0))
            by_label.setdefault(label_val, []).append(item)

        pairs: List[CodePair] = []
        pair_id = 0

        if max_pairs:
            n_clones = len(by_label.get(1, []))
            n_non_clones = len(by_label.get(0, []))
            total = n_clones + n_non_clones
            target_clones = max(1, int(max_pairs * n_clones / total)) if total > 0 else 0
            target_non_clones = max_pairs - target_clones

            for item in by_label.get(1, [])[:target_clones]:
                pairs.append(CodePair(
                    id_a=f"poj104_{item.get('id1', pair_id)}",
                    code_a=item.get("func1", ""),
                    id_b=f"poj104_{item.get('id2', pair_id)}",
                    code_b=item.get("func2", ""),
                    label=1,
                    clone_type=3,
                ))
                pair_id += 1

            for item in by_label.get(0, [])[:target_non_clones]:
                pairs.append(CodePair(
                    id_a=f"poj104_{item.get('id1', pair_id)}",
                    code_a=item.get("func1", ""),
                    id_b=f"poj104_{item.get('id2', pair_id)}",
                    code_b=item.get("func2", ""),
                    label=0,
                    clone_type=0,
                ))
                pair_id += 1

            self._rng.shuffle(pairs)
        else:
            for item in data:
                lbl = int(item.get("label", 0))
                pairs.append(CodePair(
                    id_a=f"poj104_{item.get('id1', pair_id)}",
                    code_a=item.get("func1", ""),
                    id_b=f"poj104_{item.get('id2', pair_id)}",
                    code_b=item.get("func2", ""),
                    label=lbl,
                    clone_type=3 if lbl == 1 else 0,
                ))
                pair_id += 1

        return CanonicalDataset(name="poj104", version="1.0", pairs=pairs, language="java")

    def load_codexglue_clone(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load CodeXGLUE Clone Detection dataset (BigCloneBench subset).

        Standard Java code clone detection benchmark with labeled function pairs.

        Args:
            split: Dataset split (train, validation, test).
            max_pairs: Maximum number of pairs to load.

        Returns:
            CanonicalDataset with Java function pairs.
        """
        dataset_path = str(self._data_root / "codexglue_clone" / "huggingface")
        ds = self._load_hf_dataset(dataset_path)
        data = ds[split]

        pairs: List[CodePair] = []
        for idx, item in enumerate(data):
            if max_pairs and idx >= max_pairs:
                break
            lbl = int(item.get("label", 0))
            pairs.append(CodePair(
                id_a=f"codexglue_{idx}_a",
                code_a=item.get("func1", ""),
                id_b=f"codexglue_{idx}_b",
                code_b=item.get("func2", ""),
                label=lbl,
                clone_type=3 if lbl == 1 else 0,
            ))

        return CanonicalDataset(name="codexglue_clone", version="1.0", pairs=pairs, language="java")

    def load_codexglue_defect(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load CodeXGLUE Defect Detection dataset (C code).

        Contains C functions labeled as defective or not.

        Args:
            split: Dataset split (train, validation, test).
            max_pairs: Maximum number of pairs to create.

        Returns:
            CanonicalDataset with C function pairs.
        """
        dataset_path = str(self._data_root / "codexglue_defect" / "huggingface")
        ds = self._load_hf_dataset(dataset_path)
        data = ds[split]

        by_target: Dict[int, List[Dict[str, Any]]] = {0: [], 1: []}
        for item in data:
            by_target.setdefault(int(item.get("target", 0)), []).append(item)

        pairs: List[CodePair] = []
        pair_id = 0
        limit_each = (max_pairs // 4) if max_pairs else 100

        for target in [0, 1]:
            samples = by_target[target]
            added = 0
            for i in range(len(samples)):
                if added >= limit_each:
                    break
                for j in range(i + 1, min(i + 5, len(samples))):
                    if added >= limit_each:
                        break
                    pairs.append(CodePair(
                        id_a=f"defect_{pair_id}_a",
                        code_a=samples[i].get("func", ""),
                        id_b=f"defect_{pair_id}_b",
                        code_b=samples[j].get("func", ""),
                        label=target,
                        clone_type=4 if target == 1 else 0,
                    ))
                    added += 1
                    pair_id += 1

        limit_nc = (max_pairs // 2) if max_pairs else 100
        for i in range(min(len(by_target[0]), limit_nc)):
            for j in range(min(len(by_target[1]), limit_nc)):
                if len(pairs) >= (max_pairs or 999999):
                    break
                pairs.append(CodePair(
                    id_a=f"defect_nc_{pair_id}_a",
                    code_a=by_target[0][i].get("func", ""),
                    id_b=f"defect_nc_{pair_id}_b",
                    code_b=by_target[1][j].get("func", ""),
                    label=0,
                    clone_type=0,
                ))
                pair_id += 1

        self._rng.shuffle(pairs)
        return CanonicalDataset(name="codexglue_defect", version="1.0", pairs=pairs, language="c")

    def load_codesearchnet(
        self,
        language: str = "python",
        split: str = "test",
        max_functions: int = 500,
    ) -> CanonicalDataset:
        """Load CodeSearchNet dataset for embedding training.

        Available languages: python, java, javascript, go, php, ruby.

        Args:
            language: Programming language to load.
            split: Dataset split (train, test, validation).
            max_functions: Max number of functions to load.

        Returns:
            CanonicalDataset with code/docstring pairs.
        """
        dataset_path = str(self._data_root / "codesearchnet" / "huggingface")
        ds = self._load_hf_dataset(dataset_path)
        data = ds[split]

        samples = [item for item in data if item.get("language") == language]
        samples = samples[:max_functions]

        pairs: List[CodePair] = []
        pair_id = 0
        for i, item_a in enumerate(samples):
            pairs.append(CodePair(
                id_a=f"csn_{pair_id}_a",
                code_a=item_a.get("func_code_string", ""),
                id_b=f"csn_{pair_id}_b",
                code_b=item_a.get("func_documentation_string", ""),
                label=1,
                clone_type=4,
            ))
            pair_id += 1
            if i < len(samples) - 1:
                item_b = self._rng.choice(samples)
                if item_b.get("func_code_url") != item_a.get("func_code_url"):
                    pairs.append(CodePair(
                        id_a=f"csn_nc_{pair_id}_a",
                        code_a=item_a.get("func_code_string", ""),
                        id_b=f"csn_nc_{pair_id}_b",
                        code_b=item_b.get("func_code_string", ""),
                        label=0,
                        clone_type=0,
                    ))
                    pair_id += 1

        return CanonicalDataset(name=f"codesearchnet_{language}", version="1.0", pairs=pairs, language=language)

    def load_kaggle_student_code(
        self, max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load Kaggle Student Code Similarity dataset.

        Args:
            max_pairs: Maximum number of pairs to load.

        Returns:
            CanonicalDataset with student code pairs.
        """
        dataset_path = self._data_root / "kaggle_student_code"
        if not dataset_path.exists():
            raise FileNotFoundError(
                f"Kaggle dataset not found at {dataset_path}"
            )

        pairs: List[CodePair] = []
        pair_id = 0
        # Try different CSV file names
        csv_files = ["train.csv", "cheating_dataset.csv", "cheating_features_dataset.csv"]
        csv_path = None
        for csv_name in csv_files:
            candidate = dataset_path / csv_name
            if candidate.exists():
                csv_path = candidate
                break
        
        if csv_path and csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if max_pairs and pair_id >= max_pairs:
                        break
                    # Handle different column name formats
                    code_a = row.get("source", "") or row.get("code_a", "") or row.get("File_1", "")
                    code_b = row.get("target", "") or row.get("code_b", "") or row.get("File_2", "")
                    label = int(row.get("similarity", row.get("label", row.get("Label", 0))))
                    
                    # Read code from files if paths are provided
                    if code_a.endswith(".py"):
                        file_a = dataset_path / code_a
                        if file_a.exists():
                            try:
                                with open(file_a, "r", encoding="utf-8") as code_file:
                                    code_a = code_file.read()
                            except Exception:
                                pass
                    if code_b.endswith(".py"):
                        file_b = dataset_path / code_b
                        if file_b.exists():
                            try:
                                with open(file_b, "r", encoding="utf-8") as code_file:
                                    code_b = code_file.read()
                            except Exception:
                                pass
                    
                    pairs.append(CodePair(
                        id_a=f"kaggle_{pair_id}_a",
                        code_a=code_a,
                        id_b=f"kaggle_{pair_id}_b",
                        code_b=code_b,
                        label=label,
                        clone_type=1 if label == 1 else 0,
                    ))
                    pair_id += 1

        py_files = list(dataset_path.glob("*.py"))
        if py_files and len(py_files) >= 2:
            with open(py_files[0], "r", encoding="utf-8") as f:
                code_a = f.read()
            for py_file in py_files[1:]:
                if max_pairs and pair_id >= max_pairs:
                    break
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        code_b = f.read()
                    pairs.append(CodePair(
                        id_a=f"kaggle_py_{pair_id}_a",
                        code_a=code_a,
                        id_b=f"kaggle_py_{pair_id}_b",
                        code_b=code_b,
                        label=0,
                        clone_type=0,
                    ))
                    pair_id += 1
                except Exception:
                    continue

        self._rng.shuffle(pairs)
        return CanonicalDataset(name="kaggle_student_code", version="1.0", pairs=pairs, language="python")

    def load_human_eval(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load HumanEval dataset (Python coding problems).

        Contains 164 Python problems with test cases.
        Creates clone pairs by pairing problems with similar functionality.

        Args:
            split: Dataset split (test).
            max_pairs: Maximum number of pairs to create.

        Returns:
            CanonicalDataset with Python function pairs.
        """
        dataset_path = str(self._data_root / "human_eval" / "huggingface")
        ds = self._load_hf_dataset(dataset_path)
        data = ds[split]

        pairs: List[CodePair] = []
        pair_id = 0
        limit = max_pairs if max_pairs else len(data) * 2

        # Create positive pairs from problems with similar prompts
        for i in range(len(data)):
            if max_pairs and len(pairs) >= max_pairs:
                break
            item_a = data[i]
            code_a = item_a.get("canonical_solution", "")
            for j in range(i + 1, min(i + 5, len(data))):
                if max_pairs and len(pairs) >= max_pairs:
                    break
                item_b = data[j]
                code_b = item_b.get("canonical_solution", "")
                # Label based on prompt similarity (simple heuristic)
                prompt_a = item_a.get("prompt", "").lower()
                prompt_b = item_b.get("prompt", "").lower()
                # Very different problems = non-clone
                label = 0
                pairs.append(CodePair(
                    id_a=f"humaneval_{pair_id}_a",
                    code_a=code_a,
                    id_b=f"humaneval_{pair_id}_b",
                    code_b=code_b,
                    label=label,
                    clone_type=0,
                ))
                pair_id += 1

        # Add some negative pairs (random different problems)
        added_neg = 0
        for _ in range(min(len(data), 50)):
            if max_pairs and len(pairs) >= max_pairs:
                break
            i = self._rng.randint(0, len(data) - 1)
            j = self._rng.randint(0, len(data) - 1)
            if i != j:
                pairs.append(CodePair(
                    id_a=f"humaneval_neg_{pair_id}_a",
                    code_a=data[i].get("canonical_solution", ""),
                    id_b=f"humaneval_neg_{pair_id}_b",
                    code_b=data[j].get("canonical_solution", ""),
                    label=0,
                    clone_type=0,
                ))
                pair_id += 1
                added_neg += 1

        self._rng.shuffle(pairs)
        return CanonicalDataset(name="human_eval", version="1.0", pairs=pairs, language="python")

    def load_mbpp(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load MBPP dataset (Python programming problems).

        Contains 374 Python problems with test cases.

        Args:
            split: Dataset split (train, test, validation).
            max_pairs: Maximum number of pairs to create.

        Returns:
            CanonicalDataset with Python function pairs.
        """
        dataset_path = str(self._data_root / "mbpp" / "huggingface")
        ds = self._load_hf_dataset(dataset_path)
        data = ds[split]

        pairs: List[CodePair] = []
        pair_id = 0

        # Create pairs from different problems (mostly negative)
        limit = max_pairs if max_pairs else 200
        for _ in range(limit):
            if len(data) < 2:
                break
            i = self._rng.randint(0, len(data) - 1)
            j = self._rng.randint(0, len(data) - 1)
            while j == i:
                j = self._rng.randint(0, len(data) - 1)
            pairs.append(CodePair(
                id_a=f"mbpp_{pair_id}_a",
                code_a=data[i].get("code", ""),
                id_b=f"mbpp_{pair_id}_b",
                code_b=data[j].get("code", ""),
                label=0,
                clone_type=0,
            ))
            pair_id += 1

        self._rng.shuffle(pairs)
        return CanonicalDataset(name="mbpp", version="1.0", pairs=pairs, language="python")

    def load_bigclonebench(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load BigCloneBench subset (Java clone pairs).

        Uses HuggingFace dataset if available, otherwise generates
        synthetic pairs from CodeSearchNet Java.

        Args:
            split: Dataset split.
            max_pairs: Maximum pairs to load.

        Returns:
            CanonicalDataset with Java clone pairs.
        """
        dataset_path = str(self._data_root / "bigclonebench" / "huggingface")
        if os.path.exists(dataset_path):
            return self._load_bigclonebench_local(dataset_path, split, max_pairs)

        try:
            from datasets import load_dataset
            ds = load_dataset("code_x_glue_cc_clone_detection_big_clone_bench")
            return self._load_bigclonebench_hf(ds, split, max_pairs)
        except Exception as e:
            raise FileNotFoundError(
                f"BigCloneBench data not found locally or on HuggingFace: {e}\n"
                f"Expected path: {dataset_path}\n"
                f"Try: huggingface-cli download code_x_glue_cc_clone_detection_big_clone_bench"
            )

    def _load_bigclonebench_local(
        self, path: str, split: str, max_pairs: Optional[int]
    ) -> CanonicalDataset:
        ds = self._load_hf_dataset(path)
        data = ds[split]
        return self._build_bigclonebench_pairs(data, max_pairs)

    def _load_bigclonebench_hf(
        self, ds, split: str, max_pairs: Optional[int]
    ) -> CanonicalDataset:
        data = ds[split]
        return self._build_bigclonebench_pairs(data, max_pairs)

    def _build_bigclonebench_pairs(
        self, data, max_pairs: Optional[int]
    ) -> CanonicalDataset:
        by_label: Dict[int, List[Any]] = {}
        for item in data:
            label_val = int(item.get("label", 0))
            by_label.setdefault(label_val, []).append(item)

        pairs: List[CodePair] = []
        pair_id = 0

        if max_pairs:
            n_clones = len(by_label.get(1, []))
            n_non_clones = len(by_label.get(0, []))
            total = n_clones + n_non_clones
            target_clones = max(1, int(max_pairs * n_clones / total)) if total > 0 else 0
            target_non_clones = max_pairs - target_clones

            for item in by_label.get(1, [])[:target_clones]:
                ctype = int(item.get("clone_type", 0)) if "clone_type" in item else 1
                pairs.append(CodePair(
                    id_a=f"bcb_{item.get('id1', pair_id)}",
                    code_a=item.get("func1", item.get("code1", "")),
                    id_b=f"bcb_{item.get('id2', pair_id)}",
                    code_b=item.get("func2", item.get("code2", "")),
                    label=1,
                    clone_type=ctype,
                ))
                pair_id += 1

            for item in by_label.get(0, [])[:target_non_clones]:
                pairs.append(CodePair(
                    id_a=f"bcb_{item.get('id1', pair_id)}",
                    code_a=item.get("func1", item.get("code1", "")),
                    id_b=f"bcb_{item.get('id2', pair_id)}",
                    code_b=item.get("func2", item.get("code2", "")),
                    label=0,
                    clone_type=0,
                ))
                pair_id += 1

            self._rng.shuffle(pairs)
        else:
            for idx, item in enumerate(data):
                lbl = int(item.get("label", 0))
                ctype = int(item.get("clone_type", 0)) if "clone_type" in item else (1 if lbl == 1 else 0)
                pairs.append(CodePair(
                    id_a=f"bcb_{item.get('id1', idx)}",
                    code_a=item.get("func1", item.get("code1", "")),
                    id_b=f"bcb_{item.get('id2', idx)}",
                    code_b=item.get("func2", item.get("code2", "")),
                    label=lbl,
                    clone_type=ctype,
                ))
                pair_id += 1

        return CanonicalDataset(name="bigclonebench", version="1.0", pairs=pairs, language="java")

    def load_google_codejam(
        self, split: str = "test", max_pairs: Optional[int] = None
    ) -> CanonicalDataset:
        """Load Google Code Jam dataset (Python solutions).

        Uses HuggingFace dataset if available, otherwise generates
        synthetic pairs from available local data.

        Args:
            split: Dataset split.
            max_pairs: Maximum pairs to load.

        Returns:
            CanonicalDataset with Python code pairs.
        """
        dataset_path = str(self._data_root / "google_codejam" / "huggingface")
        if os.path.exists(dataset_path):
            return self._load_codejam_local(dataset_path, split, max_pairs)

        try:
            from datasets import load_dataset
            ds = load_dataset("codeparrot/codecontest", split="train")
            return self._load_codejam_hf(ds, split, max_pairs)
        except Exception as e:
            raise FileNotFoundError(
                f"Google Code Jam data not found locally or on HuggingFace: {e}\n"
                f"Expected path: {dataset_path}\n"
                f"Try: huggingface-cli download codeparrot/codecontest"
            )

    def _load_codejam_local(
        self, path: str, split: str, max_pairs: Optional[int]
    ) -> CanonicalDataset:
        ds = self._load_hf_dataset(path)
        data = ds[split]
        return self._build_codejam_pairs(data, max_pairs)

    def _load_codejam_hf(self, ds, split: str, max_pairs: Optional[int]) -> CanonicalDataset:
        data = list(ds) if hasattr(ds, '__iter__') else ds[split]
        return self._build_codejam_pairs(data, max_pairs)

    def _build_codejam_pairs(self, data, max_pairs: Optional[int]) -> CanonicalDataset:
        solutions: Dict[str, List[str]] = {}
        for item in data:
            problem = item.get("name", item.get("problem_id", "unknown"))
            code = item.get("solution", item.get("code", ""))
            if code.strip():
                solutions.setdefault(problem, []).append(code)

        pairs: List[CodePair] = []
        pair_id = 0
        for problem, codes in solutions.items():
            if max_pairs and pair_id >= max_pairs:
                break
            for i in range(len(codes)):
                if max_pairs and pair_id >= max_pairs:
                    break
                for j in range(i + 1, min(i + 3, len(codes))):
                    if max_pairs and pair_id >= max_pairs:
                        break
                    pairs.append(CodePair(
                        id_a=f"gcj_{problem}_{pair_id}_a",
                        code_a=codes[i],
                        id_b=f"gcj_{problem}_{pair_id}_b",
                        code_b=codes[j],
                        label=1,
                        clone_type=3,
                    ))
                    pair_id += 1

        if not pairs:
            raise ValueError("No valid pairs found in Google Code Jam data")

        self._rng.shuffle(pairs)
        return CanonicalDataset(name="google_codejam", version="1.0", pairs=pairs, language="python")

    def load_by_name(
        self,
        name: str,
        split: str = "test",
        max_pairs: Optional[int] = None,
    ) -> CanonicalDataset:
        """Load dataset by name (dispatches to appropriate loader).

        Args:
            name: Dataset name (poj104, codexglue_clone, codexglue_defect,
                  codesearchnet, codesearchnet_python, kaggle).
            split: Dataset split where applicable.
            max_pairs: Maximum number of pairs to load.

        Returns:
            CanonicalDataset for the requested dataset.

        Raises:
            ValueError: If dataset name is not recognized.
        """
        loaders = {
            "poj104": lambda: self.load_poj104(split, max_pairs),
            "bigclonebench": lambda: self.load_bigclonebench(split, max_pairs),
            "google_codejam": lambda: self.load_google_codejam(split, max_pairs),
            "codexglue_clone": lambda: self.load_codexglue_clone(split, max_pairs),
            "codexglue_defect": lambda: self.load_codexglue_defect(split, max_pairs),
            "codesearchnet": lambda: self.load_codesearchnet("python", split, max_pairs if max_pairs is not None else 500),
            "codesearchnet_python": lambda: self.load_codesearchnet("python", split, max_pairs if max_pairs is not None else 500),
            "codesearchnet_java": lambda: self.load_codesearchnet("java", split, max_pairs if max_pairs is not None else 500),
            "kaggle": lambda: self.load_kaggle_student_code(max_pairs),
            "human_eval": lambda: self.load_human_eval(split, max_pairs),
            "mbpp": lambda: self.load_mbpp(split, max_pairs),
        }
        if name not in loaders:
            raise ValueError(
                f"Unknown dataset '{name}'. "
                f"Available: {list(loaders.keys())}"
            )
        try:
            return loaders[name]()
        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to load dataset '{name}': {e}"
            ) from e