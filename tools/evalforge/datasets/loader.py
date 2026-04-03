"""Dataset loader."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_dataset(name, data_dir=Path("benchmark/data")):
    loaders = {
        "synthetic": _load_synthetic,
        "xiangtan_style": _load_xiangtan,
        "google_code_jam": _load_codejam,
        "kaggle_student_code": _load_kaggle,
        "bigclonebench": _load_bigclonebench,
    }
    loader = loaders.get(name)
    if loader is None:
        raise ValueError(f"Unknown dataset: {name}")
    return loader(data_dir)


def _load_synthetic(data_dir):
    gen_file = data_dir / "synthetic" / "generated_pairs.jsonl"
    if not gen_file.exists():
        raise FileNotFoundError(f"Synthetic dataset not found: {gen_file}")
    with open(gen_file, 'r') as f:
        data = json.load(f)
    pairs = [(p["code_a"], p["code_b"]) for p in data.get("pairs", [])]
    labels = [p["label"] for p in data.get("pairs", [])]
    clone_types = [p.get("clone_type", 0) for p in data.get("pairs", [])]
    return {"pairs": pairs, "labels": labels, "clone_types": clone_types, "name": "synthetic"}


def _load_xiangtan(data_dir):
    csv_file = data_dir / "xiangtan" / "pairs.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"Xiangtan pairs not found: {csv_file}")
    base = data_dir / "xiangtan" / "source"
    pairs, labels, clone_types = [], [], []
    with open(csv_file, 'r') as f:
        f.readline()
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 3: continue
            ctype = parts[0]
            f1, f2 = parts[1].strip(), parts[2].strip()
            code1 = _read_file(base / f1)
            code2 = _read_file(base / f2)
            if code1 and code2:
                pairs.append((code1, code2))
                labels.append(1)
                clone_types.append({"T1": 1, "T2": 2, "T3": 3}.get(ctype, 0))
    return {"pairs": pairs, "labels": labels, "clone_types": clone_types, "name": "xiangtan_style"}


def _load_codejam(data_dir):
    gt_file = data_dir / "google_codejam" / "ground_truth.json"
    if not gt_file.exists():
        raise FileNotFoundError(f"Code Jam ground truth not found: {gt_file}")
    gt = json.loads(gt_file.read_text())
    base = data_dir / "google_codejam" / "submissions"
    pairs, labels = [], []
    for item in gt.get("pairs", []):
        code1 = _read_file(base / item["file1"])
        code2 = _read_file(base / item["file2"])
        if code1 and code2:
            pairs.append((code1, code2))
            labels.append(item.get("label", 0))
    return {"pairs": pairs, "labels": labels, "name": "google_code_jam"}


def _load_kaggle(data_dir):
    csv_file = data_dir / "kaggle_student_code" / "cheating_dataset.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"Kaggle dataset not found: {csv_file}")
    import csv
    pairs, labels = [], []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            f1 = data_dir / "kaggle_student_code" / row.get("File_1", "").strip()
            f2 = data_dir / "kaggle_student_code" / row.get("File_2", "").strip()
            code1 = _read_file(f1)
            code2 = _read_file(f2)
            if code1 and code2:
                pairs.append((code1, code2))
                labels.append(int(float(row.get("Label", 0))))
    return {"pairs": pairs, "labels": labels, "name": "kaggle_student_code"}


def _load_bigclonebench(data_dir):
    from benchmark.datasets.bigclonebench import BigCloneBenchDataset
    bcb = BigCloneBenchDataset(data_dir / "bigclonebench")
    if not bcb.check_availability()["bcb_reduced"]:
        raise FileNotFoundError("BigCloneBench data not available")
    sample = bcb.load(max_pairs=200, max_non_clones=200)
    pairs, labels, clone_types = [], [], []
    for cp in sample.clone_pairs:
        code1 = bcb.get_source_code(cp.file1)
        code2 = bcb.get_source_code(cp.file2)
        if code1 and code2:
            pairs.append((code1, code2))
            labels.append(1)
            clone_types.append(cp.clone_type)
    for ncp in sample.non_clone_pairs:
        code1 = bcb.get_source_code(ncp.file1)
        code2 = bcb.get_source_code(ncp.file2)
        if code1 and code2:
            pairs.append((code1, code2))
            labels.append(0)
            clone_types.append(0)
    return {"pairs": pairs, "labels": labels, "clone_types": clone_types, "name": "bigclonebench"}


def _read_file(path):
    try:
        if path.exists():
            return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        pass
    return None
