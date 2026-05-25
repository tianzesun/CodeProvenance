"""Unit tests for the Karnalim classroom dataset loader."""

from __future__ import annotations

import json

from src.backend.benchmark.datasets.karnalim import KarnalimDataset


def test_karnalim_loader_uses_canonical_dataset_contract(tmp_path) -> None:
    """Karnalim should load samples and labels into the shared benchmark schema."""
    dataset_root = tmp_path / "karnalim"
    submissions_dir = dataset_root / "assignment1" / "submissions"
    submissions_dir.mkdir(parents=True)
    (submissions_dir / "alice.java").write_text(
        "class Alice { int add(int a, int b) { return a + b; } }\n",
        encoding="utf-8",
    )
    (submissions_dir / "bob.java").write_text(
        "class Bob { int sum(int x, int y) { return x + y; } }\n",
        encoding="utf-8",
    )
    (dataset_root / "ground_truth.json").write_text(
        json.dumps(
            {
                "plagiarism_pairs": [
                    {
                        "assignment": "assignment1",
                        "a": "alice",
                        "b": "bob",
                        "clone_type": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    dataset = KarnalimDataset(dataset_root).load()

    assert dataset.name == "karnalim_classroom"
    assert dataset.language == "java"
    assert len(dataset.submissions) == 2
    assert len(dataset.pairs) == 1
    assert dataset.pairs[0].id_a == "assignment1_alice"
    assert dataset.pairs[0].id_b == "assignment1_bob"
    assert dataset.pairs[0].label == 1
    assert dataset.pairs[0].clone_type == 2
