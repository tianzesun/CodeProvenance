#!/usr/bin/env python3
"""Download benchmark datasets for code similarity detection."""

import os
from pathlib import Path
from datasets import load_dataset

DATA_DIR = Path("/home/tsun/CodeProvenance/benchmark/data")

DATASETS = {
    "poj104": {
        "name": "code_x_glue_cc_clone_detection_poj104",
        "target_dir": "poj104/huggingface",
    },
    "codesearchnet": {
        "name": "code_search_net",
        "target_dir": "codesearchnet/huggingface",
    },
    "codexglue_clone": {
        "name": "code_x_glue_cc_clone_detection_big_clone_bench",
        "target_dir": "codexglue_clone/huggingface",
    },
    "codexglue_defect": {
        "name": "code_x_glue_cc_defect_detection",
        "target_dir": "codexglue_defect/huggingface",
    },
    "poolc_600k_python": {
        "name": "PoolC/1-fold-clone-detection-600k-5fold",
        "target_dir": "poolc_600k_python/huggingface",
    },
}


def download_dataset(key, config, splits=["train", "validation", "test"]):
    """Download a dataset from HuggingFace."""
    target_dir = DATA_DIR / config["target_dir"]

    if target_dir.exists():
        print(f"  {key}: Already exists, skipping")
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {config['name']}...")

    try:
        dataset = load_dataset(config["name"], trust_remote_code=True)

        for split in splits:
            if split in dataset:
                split_dir = target_dir / split
                split_dir.mkdir(parents=True, exist_ok=True)

                print(f"  Saving {split} split...")
                dataset[split].save_to_disk(str(split_dir))
                print(f"  {split} saved to {split_dir}")

        print(f"  {key}: Downloaded successfully")

    except Exception as e:
        print(f"  Error downloading {key}: {e}")


def main():
    print("Starting dataset downloads...")
    print(f"Target directory: {DATA_DIR}\n")

    for key, config in DATASETS.items():
        download_dataset(key, config)

    print("\nDownload complete!")


if __name__ == "__main__":
    main()
