#!/usr/bin/env python3
"""
Dataset Downloader - Easy script to download datasets to data/datasets/

Usage:
    python scripts/download_dataset.py <dataset_name>
    
Available datasets:
    - poj104
    - codesearchnet
    - codexglue_clone
    - codexglue_defect
    - bigclonebench
    - kaggle_student_code (requires Kaggle API)
    - humaneval
    - mbpp
    - xiangtan

Example:
    python scripts/download_dataset.py poj104
"""

import sys
import os
from pathlib import Path
import subprocess
import shutil

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATASETS_DIR = PROJECT_ROOT / "data" / "datasets"

# Ensure datasets directory exists
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

def download_poj104():
    """Download POJ-104 dataset from HuggingFace."""
    print("Downloading POJ-104 dataset...")
    target = DATASETS_DIR / "poj104"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        from datasets import load_dataset
        ds = load_dataset("/code_provenance/poj104")  # Replace with actual dataset
        ds.save_to_disk(str(target / "huggingface"))
        print(f"✅ POJ-104 downloaded to {target}")
    except ImportError:
        print("❌ Please install: pip install datasets")
    except Exception as e:
        print(f"❌ Error downloading POJ-104: {e}")

def download_codesearchnet():
    """Download CodeSearchNet Python subset."""
    print("Downloading CodeSearchNet Python subset...")
    target = DATASETS_DIR / "codesearchnet"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        from datasets import load_dataset
        ds = load_dataset("code_search_net", "python")
        ds.save_to_disk(str(target / "huggingface"))
        print(f"✅ CodeSearchNet downloaded to {target}")
    except ImportError:
        print("❌ Please install: pip install datasets")
    except Exception as e:
        print(f"❌ Error downloading CodeSearchNet: {e}")

def download_codexglue_clone():
    """Download CodeXGLUE clone detection dataset."""
    print("Downloading CodeXGLUE clone detection dataset...")
    target = DATASETS_DIR / "codexglue_clone"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        from datasets import load_dataset
        ds = load_dataset("code_x_glue_ct_code_to_code", "clone")
        ds.save_to_disk(str(target / "huggingface"))
        print(f"✅ CodeXGLUE Clone downloaded to {target}")
    except ImportError:
        print("❌ Please install: pip install datasets")
    except Exception as e:
        print(f"❌ Error downloading CodeXGLUE: {e}")

def download_codexglue_defect():
    """Download CodeXGLUE defect detection dataset."""
    print("Downloading CodeXGLUE defect detection dataset...")
    target = DATASETS_DIR / "codexglue_defect"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        from datasets import load_dataset
        ds = load_dataset("code_x_glue_ct_code_to_code", "defect")
        ds.save_to_disk(str(target / "huggingface"))
        print(f"✅ CodeXGLUE Defect downloaded to {target}")
    except ImportError:
        print("❌ Please install: pip install datasets")
    except Exception as e:
        print(f"❌ Error downloading CodeXGLUE: {e}")

def download_kaggle_student_code():
    """Download Kaggle Student Code Similarity dataset."""
    print("Downloading Kaggle Student Code Similarity dataset...")
    target = DATASETS_DIR / "kaggle_student_code"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        subprocess.run([
            "kaggle", "datasets", "download", 
            "ehsankhani/student-code-similarity-and-plagiarism-labels",
            "-p", str(target), "--unzip"
        ], check=True)
        print(f"✅ Kaggle dataset downloaded to {target}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error downloading Kaggle dataset: {e}")
        print("   Make sure you have Kaggle API installed and configured:")
        print("   pip install kaggle")
        print("   kaggle config set -n username -v <your_username>")
        print("   kaggle config set -n key -v <your_api_key>")

def download_humaneval():
    """Download HumanEval dataset."""
    print("Downloading HumanEval dataset...")
    target = DATASETS_DIR / "humaneval"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        from datasets import load_dataset
        ds = load_dataset("openai_humaneval")
        ds.save_to_disk(str(target / "huggingface"))
        print(f"✅ HumanEval downloaded to {target}")
    except ImportError:
        print("❌ Please install: pip install datasets")
    except Exception as e:
        print(f"❌ Error downloading HumanEval: {e}")

def download_mbpp():
    """Download MBPP dataset."""
    print("Downloading MBPP dataset...")
    target = DATASETS_DIR / "mbpp"
    target.mkdir(parents=True, exist_ok=True)
    
    try:
        from datasets import load_dataset
        ds = load_dataset("mbpp")
        ds.save_to_disk(str(target / "huggingface"))
        print(f"✅ MBPP downloaded to {target}")
    except ImportError:
        print("❌ Please install: pip install datasets")
    except Exception as e:
        print(f"❌ Error downloading MBPP: {e}")

def download_bigclonebench():
    """Download BigCloneBench dataset."""
    print("Downloading BigCloneBench dataset...")
    target = DATASETS_DIR / "bigclonebench"
    target.mkdir(parents=True, exist_ok=True)
    
    print("ℹ️  BigCloneBench requires manual download from:")
    print("   https://github.com/clonebench/BigCloneBench")
    print(f"   Extract to: {target}")

def download_xiangtan():
    """Download Xiangtan dataset."""
    print("Downloading Xiangtan dataset...")
    target = DATASETS_DIR / "xiangtan"
    target.mkdir(parents=True, exist_ok=True)
    
    print("ℹ️  Xiangtan dataset requires manual download.")
    print("   Contact authors or search academic repositories.")
    print(f"   Expected structure in: {target}")

def list_available_datasets():
    """List all available datasets."""
    print("\nAvailable datasets in data/datasets/:")
    print("=" * 50)
    
    if not DATASETS_DIR.exists():
        print("No datasets directory found.")
        return
    
    for item in sorted(DATASETS_DIR.iterdir()):
        if item.is_dir():
            size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
            size_mb = size / (1024 * 1024)
            print(f"📁 {item.name:30} ({size_mb:.1f} MB)")
        elif item.is_file() and item.suffix in ['.gz', '.zip', '.tar']:
            size_mb = item.stat().st_size / (1024 * 1024)
            print(f"📦 {item.name:30} ({size_mb:.1f} MB)")
    
    print("\nDownloadable datasets:")
    print("=" * 50)
    downloadable = [
        "poj104", "codesearchnet", "codexglue_clone", "codexglue_defect",
        "kaggle_student_code", "humaneval", "mbpp", "bigclonebench", "xiangtan"
    ]
    for name in downloadable:
        print(f"   • {name}")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        list_available_datasets()
        return
    
    dataset_name = sys.argv[1].lower()
    
    downloaders = {
        "poj104": download_poj104,
        "codesearchnet": download_codesearchnet,
        "codexglue_clone": download_codexglue_clone,
        "codexglue_defect": download_codexglue_defect,
        "kaggle_student_code": download_kaggle_student_code,
        "humaneval": download_humaneval,
        "mbpp": download_mbpp,
        "bigclonebench": download_bigclonebench,
        "xiangtan": download_xiangtan,
    }
    
    if dataset_name in ["list", "ls", "-l"]:
        list_available_datasets()
        return
    
    if dataset_name not in downloaders:
        print(f"❌ Unknown dataset: {dataset_name}")
        print("\nAvailable datasets:")
        for name in downloaders.keys():
            print(f"   • {name}")
        return
    
    print(f"🚀 Downloading {dataset_name} to data/datasets/{dataset_name}/")
    print("=" * 60)
    downloaders[dataset_name]()
    print("\n✅ Done!")

if __name__ == "__main__":
    main()