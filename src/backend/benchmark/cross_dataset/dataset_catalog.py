"""Central dataset registry for cross-dataset benchmarking.

Defines all known datasets with metadata, loading strategies, and
pair generation rules for real-world, synthetic, and HuggingFace sources.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ======================================================================
# Dataset definitions
# ======================================================================

DATASETS = [
    {
        "id": "bigclonebench",
        "type": "real",
        "language": "java",
        "source": "local",
        "path": "data/datasets/bigclonebench",
        "description": "BigCloneBench - 5.5GB H2 DB + 55,499 Java files",
    },
    {
        "id": "bigclonebench_reduced",
        "type": "real",
        "language": "java",
        "source": "local",
        "path": "data/datasets/bcb_reduced",
        "description": "BigCloneBench Reduced - Java source files by functionality",
    },
    {
        "id": "google_code_jam",
        "type": "real",
        "language": "python",
        "source": "local",
        "path": "data/datasets/google_code_jam",
        "description": "Google Code Jam - 9 Python solutions with ground truth",
    },
    {
        "id": "synthetic_python",
        "type": "synthetic",
        "language": "python",
        "source": "local",
        "path": "data/datasets/synthetic_python",
        "description": "Synthetic Python - 400 labeled pairs",
    },
    {
        "id": "synthetic_python_large",
        "type": "synthetic",
        "language": "python",
        "source": "local",
        "path": "data/datasets/synthetic_python_large",
        "description": "Synthetic Python Large - 1,600 labeled pairs",
    },
    {
        "id": "synthetic_java",
        "type": "synthetic",
        "language": "java",
        "source": "local",
        "path": "data/datasets/synthetic_java",
        "description": "Synthetic Java - 800 labeled pairs",
    },
    {
        "id": "synthetic_js",
        "type": "synthetic",
        "language": "javascript",
        "source": "local",
        "path": "data/datasets/synthetic_js",
        "description": "Synthetic JavaScript - 600 labeled pairs",
    },
    {
        "id": "humaneval",
        "type": "huggingface",
        "language": "python",
        "source": "hf",
        "hf_id": "openai_humaneval",
        "description": "HumanEval - 164 Python problems with test cases",
    },
    {
        "id": "mbpp",
        "type": "huggingface",
        "language": "python",
        "source": "hf",
        "hf_id": "mbpp",
        "description": "MBPP - 374 Python problems with test cases",
    },
    {
        "id": "codesearchnet",
        "type": "huggingface",
        "language": "python",
        "source": "hf",
        "hf_id": "code_search_net",
        "description": "CodeSearchNet - 1,000 Python code snippets",
    },
    {
        "id": "poj104",
        "type": "real",
        "language": "c",
        "source": "hf",
        "hf_id": "code_x_glue_cc_clone_detection_big_clone_bench",
        "description": "POJ-104 C programs from PKU Online Judge",
    },
    {
        "id": "codexglue_clone",
        "type": "real",
        "language": "java",
        "source": "hf",
        "hf_id": "code_x_glue_cc_clone_detection_big_clone_bench",
        "description": "CodeXGLUE Clone Detection (BigCloneBench subset)",
    },
    {
        "id": "codexglue_defect",
        "type": "real",
        "language": "c",
        "source": "hf",
        "hf_id": "code_x_glue_cc_defect_detection",
        "description": "CodeXGLUE Defect Detection",
    },
]


@dataclass
class DatasetEntry:
    """A single dataset definition."""
    id: str
    type: str          # "real", "synthetic", "huggingface"
    language: str
    source: str        # "local" or "hf"
    path: str = ""
    hf_id: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DatasetEntry":
        return cls(
            id=d["id"],
            type=d.get("type", "real"),
            language=d.get("language", ""),
            source=d.get("source", "local"),
            path=d.get("path", ""),
            hf_id=d.get("hf_id", ""),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
        )


class DatasetCatalog:
    """Central catalog of all known datasets."""

    _entries: Dict[str, DatasetEntry] = {}

    @classmethod
    def register_all(cls) -> None:
        for d in DATASETS:
            entry = DatasetEntry.from_dict(d)
            cls._entries[entry.id] = entry

    @classmethod
    def get(cls, dataset_id: str) -> Optional[DatasetEntry]:
        if not cls._entries:
            cls.register_all()
        return cls._entries.get(dataset_id)

    @classmethod
    def list_all(cls) -> List[DatasetEntry]:
        if not cls._entries:
            cls.register_all()
        return list(cls._entries.values())

    @classmethod
    def list_by_type(cls, dtype: str) -> List[DatasetEntry]:
        return [e for e in cls.list_all() if e.type == dtype]

    @classmethod
    def list_by_language(cls, lang: str) -> List[DatasetEntry]:
        return [e for e in cls.list_all() if e.language == lang]


# ======================================================================
# Code normalization
# ======================================================================

def normalize_code(code: str, language: str = "") -> str:
    """Normalize code for fair comparison.

    - Strip comments
    - Normalize whitespace
    - Ensure UTF-8
    - Language-specific rules
    """
    if not code:
        return ""

    code = code.encode("utf-8", errors="replace").decode("utf-8")

    if language == "python":
        return _normalize_python(code)
    elif language == "java":
        return _normalize_java(code)
    elif language == "javascript":
        return _normalize_js(code)
    else:
        return _normalize_generic(code)


def _strip_python_comments(code: str) -> str:
    lines = []
    in_docstring = False
    docstring_char = None
    for line in code.splitlines():
        stripped = line.strip()
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                if stripped.count(docstring_char) >= 2 and len(stripped) > 3:
                    continue
                in_docstring = True
                continue
            if stripped.startswith("#"):
                continue
            code_part = line.split("#")[0]
            lines.append(code_part)
        else:
            if docstring_char and docstring_char in stripped:
                in_docstring = False
            continue
    return "\n".join(lines)


def _normalize_python(code: str) -> str:
    code = _strip_python_comments(code)
    code = re.sub(r"[ \t]+", " ", code)
    code = re.sub(r"\n\s*\n", "\n", code)
    return code.strip()


def _normalize_java(code: str) -> str:
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"^\s*import\s+.*?;$", "", code, flags=re.MULTILINE)
    code = re.sub(r"[ \t]+", " ", code)
    code = re.sub(r"\n\s*\n", "\n", code)
    return code.strip()


def _normalize_js(code: str) -> str:
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"[ \t]+", " ", code)
    code = re.sub(r"\n\s*\n", "\n", code)
    return code.strip()


def _normalize_generic(code: str) -> str:
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"#[ \t]*.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"[ \t]+", " ", code)
    code = re.sub(r"\n\s*\n", "\n", code)
    return code.strip()


# ======================================================================
# Pair generation
# ======================================================================

def generate_pairs(dataset: DatasetEntry, max_pairs: Optional[int] = None, seed: int = 42) -> List[Dict[str, Any]]:
    """Generate labeled code pairs from a dataset.

    Real-world / synthetic: load pre-labeled pairs from disk.
    HuggingFace: generate pairs programmatically.
    """
    if dataset.type in ("synthetic", "real") and dataset.source == "local":
        return _load_local_pairs(dataset, max_pairs)
    elif dataset.source == "hf":
        return _generate_hf_pairs(dataset, max_pairs, seed)
    return []


def _load_local_pairs(dataset: DatasetEntry, max_pairs: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load pre-labeled pairs from a JSON file."""
    path = Path(dataset.path)
    candidates = [
        path / "pairs.json",
        path / "dataset.json",
        path / "data.json",
    ]
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            pairs = data if isinstance(data, list) else data.get("pairs", [])
            if max_pairs:
                pairs = pairs[:max_pairs]
            for pair in pairs:
                pair["code_a"] = normalize_code(pair.get("code_a", ""), dataset.language)
                pair["code_b"] = normalize_code(pair.get("code_b", ""), dataset.language)
                pair.setdefault("source", dataset.id)
            return pairs
    return []


def _generate_hf_pairs(dataset: DatasetEntry, max_pairs: Optional[int] = None, seed: int = 42) -> List[Dict[str, Any]]:
    """Generate pairs from a HuggingFace dataset."""
    import random
    rng = random.Random(seed)

    try:
        from datasets import load_from_disk
        ds_path = Path(dataset.path) if dataset.path else None
        if ds_path and ds_path.exists():
            ds = load_from_disk(str(ds_path))
        else:
            ds = load_from_disk(f"data/datasets/{dataset.id}/huggingface")
    except Exception:
        return []

    split = "test" if "test" in ds else ("train" if "train" in ds else list(ds.keys())[0])
    data = ds[split]

    pairs = []
    code_field = _detect_code_field(data)
    label_field = _detect_label_field(data)

    if not code_field:
        return []

    items = []
    for i in range(len(data)):
        code = data[i].get(code_field, "")
        if code and isinstance(code, str):
            items.append({
                "code": normalize_code(code, dataset.language),
                "label": data[i].get(label_field, 1) if label_field else 1,
                "idx": i,
            })

    if len(items) < 2:
        return []

    # Positive pairs: adjacent items with same label=1
    pos_items = [x for x in items if x["label"] == 1]
    neg_items = [x for x in items if x["label"] == 0]

    # Generate positive pairs
    for i in range(0, len(pos_items) - 1, 2):
        if max_pairs and len(pairs) >= max_pairs:
            break
        pairs.append({
            "id": f"{dataset.id}_pos_{i}",
            "code_a": pos_items[i]["code"],
            "code_b": pos_items[i + 1]["code"],
            "label": 1,
            "type": "hf_positive",
            "source": dataset.id,
        })

    # Generate negative pairs: random pairs from different items
    for _ in range(len(pos_items)):
        if max_pairs and len(pairs) >= max_pairs:
            break
        if len(items) < 2:
            break
        a, b = rng.sample(items, 2)
        pairs.append({
            "id": f"{dataset.id}_neg_{len(pairs)}",
            "code_a": a["code"],
            "code_b": b["code"],
            "label": 0,
            "type": "hf_negative",
            "source": dataset.id,
        })

    rng.shuffle(pairs)
    return pairs


def _detect_code_field(data) -> Optional[str]:
    """Detect the code field in a HuggingFace dataset."""
    if len(data) == 0:
        return None
    sample = data[0]
    candidates = ["code", "func", "func1", "func2", "canonical_solution", "content", "body"]
    for c in candidates:
        if c in sample:
            return c
    for k, v in sample.items():
        if isinstance(v, str) and len(v) > 20:
            return k
    return None


def _detect_label_field(data) -> Optional[str]:
    """Detect the label field in a HuggingFace dataset."""
    if len(data) == 0:
        return None
    sample = data[0]
    candidates = ["label", "clone_type", "is_clone", "duplicate"]
    for c in candidates:
        if c in sample:
            return c
    return None
