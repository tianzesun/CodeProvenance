#!/usr/bin/env python3
"""Download external benchmark datasets.

Downloads and prepares:
- POJ-104 (C programs from PKU Online Judge)
- CodeXGLUE Clone Detection (BigCloneBench subset)
- CodeXGLUE Defect Detection
- CodeSearchNet (multi-language)
- Kaggle Student Code Similarity

Usage:
    python scripts/download_datasets.py [--data-root DIR] [--max-pairs N]
"""
import sys
import os
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def install_if_missing(package_name, import_name=None):
    """Install a package if it can't be imported."""
    import_name = import_name or package_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        print(f"  Installing {package_name}...")
        os.system(f"{sys.executable} -m pip install {package_name} -q")
        try:
            __import__(import_name)
            return True
        except ImportError:
            print(f"  WARNING: Failed to install {package_name}")
            return False


def download_poj104(data_root: Path) -> bool:
    """Download POJ-104 dataset."""
    target = data_root / "poj104" / "huggingface"
    if target.exists():
        print(f"  POJ-104 already exists at {target}")
        return True

    print("  Downloading POJ-104 from HuggingFace...")
    try:
        from datasets import load_dataset
        ds = load_dataset("code_x_glue_cc_clone_detection_big_clone_bench")
        ds.save_to_disk(str(target))
        print(f"  Saved to {target}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_codexglue_clone(data_root: Path) -> bool:
    """Download CodeXGLUE Clone Detection dataset."""
    target = data_root / "codexglue_clone" / "huggingface"
    if target.exists():
        print(f"  CodeXGLUE Clone already exists at {target}")
        return True

    print("  Downloading CodeXGLUE Clone Detection...")
    try:
        from datasets import load_dataset
        ds = load_dataset("code_x_glue_cc_clone_detection_big_clone_bench")
        ds.save_to_disk(str(target))
        print(f"  Saved to {target}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_codexglue_defect(data_root: Path) -> bool:
    """Download CodeXGLUE Defect Detection dataset."""
    target = data_root / "codexglue_defect" / "huggingface"
    if target.exists():
        print(f"  CodeXGLUE Defect already exists at {target}")
        return True

    print("  Downloading CodeXGLUE Defect Detection...")
    try:
        from datasets import load_dataset
        ds = load_dataset("code_x_glue_cc_defect_detection")
        ds.save_to_disk(str(target))
        print(f"  Saved to {target}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_codesearchnet(data_root: Path) -> bool:
    """Download CodeSearchNet dataset."""
    target = data_root / "codesearchnet" / "huggingface"
    if target.exists():
        print(f"  CodeSearchNet already exists at {target}")
        return True

    print("  Downloading CodeSearchNet...")
    try:
        from datasets import load_dataset
        ds = load_dataset("code_search_net", "all")
        ds.save_to_disk(str(target))
        print(f"  Saved to {target}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_kaggle_student_code(data_root: Path) -> bool:
    """Download Kaggle Student Code Similarity dataset."""
    target = data_root / "kaggle_student_code"
    if target.exists():
        print(f"  Kaggle Student Code already exists at {target}")
        return True

    print("  Kaggle Student Code dataset requires manual download.")
    print(f"  Please download from Kaggle and place files in: {target}")
    print("  URL: https://www.kaggle.com/datasets/rtatman/student-code-similarity")
    target.mkdir(parents=True, exist_ok=True)
    return False


def main():
    parser = argparse.ArgumentParser(description="Download external benchmark datasets")
    parser.add_argument("--data-root", default="data/datasets", help="Root directory for datasets")
    parser.add_argument("--datasets", nargs="*", default=None,
                        help="Specific datasets to download (default: all)")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    data_root.mkdir(parents=True, exist_ok=True)

    # Ensure datasets package is available
    install_if_missing("datasets")

    datasets = {
        "poj104": download_poj104,
        "codexglue_clone": download_codexglue_clone,
        "codexglue_defect": download_codexglue_defect,
        "codesearchnet": download_codesearchnet,
        "kaggle": download_kaggle_student_code,
    }

    if args.datasets:
        datasets = {k: v for k, v in datasets.items() if k in args.datasets}

    print(f"\nDownloading datasets to: {data_root}\n")
    results = {}
    for name, download_fn in datasets.items():
        print(f"[{name}]")
        results[name] = download_fn(data_root)
        print()

    print("=" * 50)
    print("Download Summary:")
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {name}: {status}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
