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
        """Load POJ-104 dataset (C programs from PKU Online Judge).

        Programs solving the same problem are considered clones (Type-3).

        Args:
            split: Dataset split to load (train, validation, test).
            max_pairs: Maximum number of pairs to create.

        Returns:
            CanonicalDataset with C code pairs labeled.
        """
        cache_key = f"poj104_{split}"
        if cache_key in self._dataset_cache:
            data = self._dataset_cache[cache_key]
        else:
            dataset_path = str(self._data_root / "poj104" / "huggingface")
            ds = self._load_hf_dataset(dataset_path)
            self._dataset_cache[cache_key] = ds[split]
            data = self._dataset_cache[cache_key]

        by_label: Dict[int, List[Dict[str, Any]]] = {}
        for item in data:
            label_val = item.get("label", 0)
            by_label.setdefault(label_val, []).append(item)

        pairs: List[CodePair] = []
        pair_id = 0

        for label_val, samples in by_label.items():
            limit = max_pairs if max_pairs else len(samples) * 2
            added = 0
            for i in range(len(samples)):
                if added >= limit:
                    break
                for j in range(i + 1, len(samples)):
                    if added >= limit:
                        break
                    pairs.append(CodePair(
                        id_a=f"poj104_{pair_id}_a",
                        code_a=samples[i].get("code", ""),
                        id_b=f"poj104_{pair_id}_b",
                        code_b=samples[j].get("code", ""),
                        label=1,
                        clone_type=3,
                    ))
                    added += 1
                    pair_id += 1

        label_keys = list(by_label.keys())
        for idx_a in range(len(label_keys)):
            if max_pairs and len(pairs) >= max_pairs:
                break
            for idx_b in range(idx_a + 1, len(label_keys)):
                if max_pairs and len(pairs) >= max_pairs:
                    break
                sa = self._rng.choice(by_label[label_keys[idx_a]])
                sb = self._rng.choice(by_label[label_keys[idx_b]])
                pairs.append(CodePair(
                    id_a=f"poj104_nc_{pair_id}_a",
                    code_a=sa.get("code", ""),
                    id_b=f"poj104_nc_{pair_id}_b",
                    code_b=sb.get("code", ""),
                    label=0,
                    clone_type=0,
                ))
                pair_id += 1

        self._rng.shuffle(pairs)
        ds = CanonicalDataset(name="poj104", version="1.0", pairs=pairs)
        ds.language = "c"  # type: ignore
        return ds

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

        ds = CanonicalDataset(name="codexglue_clone", version="1.0", pairs=pairs)
        ds.language = "java"  # type: ignore
        return ds

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
        ds = CanonicalDataset(name="codexglue_defect", version="1.0", pairs=pairs)
        ds.language = "c"  # type: ignore
        return ds

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

        ds = CanonicalDataset(name=f"codesearchnet_{language}", version="1.0", pairs=pairs)
        ds.language = language  # type: ignore
        return ds

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
        ds = CanonicalDataset(name="kaggle_student_code", version="1.0", pairs=pairs)
        ds.language = "python"  # type: ignore
        return ds

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
            "codexglue_clone": lambda: self.load_codexglue_clone(split, max_pairs),
            "codexglue_defect": lambda: self.load_codexglue_defect(split, max_pairs),
            "codesearchnet": lambda: self.load_codesearchnet("python", split, max_pairs or 500),
            "codesearchnet_python": lambda: self.load_codesearchnet("python", split, max_pairs or 500),
            "codesearchnet_java": lambda: self.load_codesearchnet("java", split, max_pairs or 500),
            "kaggle": lambda: self.load_kaggle_student_code(max_pairs),
        }
        if name not in loaders:
            raise ValueError(
                f"Unknown dataset '{name}'. "
                f"Available: {list(loaders.keys())}"
            )
        return loaders[name]()