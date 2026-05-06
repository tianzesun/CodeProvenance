"""Tests for benchmark dataset wiring beyond the built-in fixtures."""

from pathlib import Path

from src.backend.api import server


def test_code_similarity_dataset_wiring(tmp_path, monkeypatch) -> None:
    """CodeSimilarityDataset should expose balanced explicit pairs."""
    dataset_root = tmp_path / "CodeSimilarityDataset"
    for problem in ("reverse_string", "fibonacci"):
        snippets = dataset_root / problem / "snippets"
        snippets.mkdir(parents=True)
        for index in range(3):
            (snippets / f"snip_0{index}.py").write_text(
                f"def solve_{problem}_{index}():\n    return {index}\n",
                encoding="utf-8",
            )
    (dataset_root / "full_metadata.csv").write_text(
        "\n".join(
            [
                "problem_type,id,filename,language,method,notes",
                "reverse_string,1,snip_00.py,Python,Loop,",
                "reverse_string,2,snip_01.py,Python,Loop,",
                "reverse_string,3,snip_02.py,Python,Loop,",
                "fibonacci,4,snip_00.py,Python,Loop,",
                "fibonacci,5,snip_01.py,Python,Loop,",
                "fibonacci,6,snip_02.py,Python,Loop,",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    readiness = server._build_benchmark_dataset_readiness(
        "CodeSimilarityDataset", dataset_root
    )
    submissions, pairs = server._load_pair_labeled_benchmark_dataset(
        "CodeSimilarityDataset", tmp_path / "job"
    )

    assert readiness["runnable"] is True
    assert readiness["positive_pairs"] > 0
    assert readiness["negative_pairs"] > 0
    assert len(submissions) == len(pairs) * 2
    assert any(pair["label"] >= 2 for pair in pairs)
    assert any(pair["label"] == 0 for pair in pairs)


def test_bigclonebench_reduced_wiring(tmp_path, monkeypatch) -> None:
    """BigCloneBench reduced folders should become balanced explicit pairs."""
    dataset_root = tmp_path / "bigclonebench"
    for function_id in ("10", "11"):
        sample = dataset_root / "bcb_reduced" / function_id / "sample"
        sample.mkdir(parents=True)
        for index in range(2):
            (sample / f"Sample{index}.java").write_text(
                f"class Sample{function_id}{index} {{ int value() {{ return {index}; }} }}",
                encoding="utf-8",
            )
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    readiness = server._build_benchmark_dataset_readiness("bigclonebench", dataset_root)
    submissions, pairs = server._load_pair_labeled_benchmark_dataset(
        "bigclonebench", tmp_path / "job"
    )

    assert readiness["runnable"] is True
    assert len(submissions) == len(pairs) * 2
    assert any(pair["label"] >= 2 for pair in pairs)
    assert any(pair["label"] == 0 for pair in pairs)


def test_conplag_wiring_uses_labels_and_version_dirs(tmp_path, monkeypatch) -> None:
    """CONPLAG should load labeled Java pairs from labels.csv and version_1."""
    dataset_root = tmp_path / "conplag"
    versions = dataset_root / "versions"
    for pair_id in ("aaa_bbb", "ccc_ddd"):
        pair_dir = versions / "version_1" / pair_id
        pair_dir.mkdir(parents=True)
        left, right = pair_id.split("_")
        (pair_dir / f"{left}.java").write_text("class A {}", encoding="utf-8")
        (pair_dir / f"{right}.java").write_text("class B {}", encoding="utf-8")
    (versions / "labels.csv").write_text(
        "\n".join(
            [
                "sub1,sub2,problem,verdict",
                "aaa,bbb,1,1",
                "ccc,ddd,2,0",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    readiness = server._build_benchmark_dataset_readiness("conplag", dataset_root)
    submissions, pairs = server._load_pair_labeled_benchmark_dataset(
        "conplag", tmp_path / "job"
    )

    assert readiness["runnable"] is True
    assert readiness["positive_pairs"] == 1
    assert readiness["negative_pairs"] == 1
    assert len(submissions) == 4
    assert [pair["label"] for pair in pairs] == [3, 0]
