import asyncio
import io
import json
import sys
import types
import zipfile

from starlette.datastructures import UploadFile
from fastapi.testclient import TestClient

from src.backend.api import server


def test_load_benchmark_dataset_supports_legacy_demo_python_extensions(
    tmp_path, monkeypatch
):
    dataset_dir = tmp_path / "demo_legacy_python"
    original_dir = dataset_dir / "original"
    plagiarized_dir = dataset_dir / "plagiarized"
    original_dir.mkdir(parents=True)
    plagiarized_dir.mkdir()

    (dataset_dir / "metadata.json").write_text(
        json.dumps({"language": "python", "name": "Legacy Python Demo"}),
        encoding="utf-8",
    )
    (original_dir / "00.python").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (plagiarized_dir / "00.python").write_text(
        "def sum_numbers(x, y):\n    return x + y\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    submissions = server._load_benchmark_dataset("demo_legacy_python", tmp_path / "job")

    assert submissions == {
        "00.py": "def add(a, b):\n    return a + b\n",
        "00_plagiarized.py": "def sum_numbers(x, y):\n    return x + y\n",
    }


def test_store_benchmark_uploads_accepts_zip_archives(tmp_path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("student_a.py", "def add(a, b):\n    return a + b\n")
        archive.writestr("student_b.py", "def sum_numbers(x, y):\n    return x + y\n")

    zip_buffer.seek(0)
    upload = UploadFile(filename="demo.zip", file=zip_buffer)

    submissions = asyncio.run(server._store_benchmark_uploads([upload], tmp_path))

    assert submissions == {
        "student_a.py": "def add(a, b):\n    return a + b\n",
        "student_b.py": "def sum_numbers(x, y):\n    return x + y\n",
    }


def test_compute_evaluation_metrics_includes_pan_scores():
    metrics = server._compute_evaluation_metrics(
        scores=[0.95, 0.72, 0.12, 0.82],
        labels=[3, 2, 0, 0],
        tool_name="integritydesk",
        dataset_name="pan-smoke",
        runtime_seconds=2.0,
    )

    assert metrics["precision"] == 0.6667
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 0.8
    assert metrics["granularity"] == 1.0
    assert metrics["plagdet"] == 0.8
    assert metrics["plagdet_percent"] == 80.0
    assert metrics["top_10_retrieval"] == 0.5
    assert metrics["top_20_retrieval"] == 0.5
    assert metrics["top_10_recall"] == 1.0
    assert metrics["top_20_recall"] == 1.0
    assert metrics["false_positive_rate"] == 0.5
    assert "auc_pr" in metrics
    assert metrics["engine_contribution"] == {}
    assert metrics["ai_generated_recall"] is None
    assert metrics["runtime_seconds"] == 2.0
    assert metrics["avg_runtime_seconds"] == 0.5
    assert metrics["pan_metrics"] == {
        "precision": 0.6667,
        "recall": 1.0,
        "f1_score": 0.8,
        "granularity": 1.0,
        "plagdet": 0.8,
        "top_10_retrieval": 0.5,
        "top_20_retrieval": 0.5,
        "top_10_recall": 1.0,
        "top_20_recall": 1.0,
        "false_positive_rate": 0.5,
        "auc_pr": metrics["auc_pr"],
        "engine_contribution": {},
        "ai_generated_recall": None,
        "avg_runtime_seconds": 0.5,
        "score_diagnostics": metrics["score_diagnostics"],
    }
    assert metrics["score_diagnostics"]["label_conflict"] is False
    assert metrics["granularity_basis"] == "pair_level_single_detection"
    assert metrics["metric_assumptions"]["span_level_scoring"] is False
    assert metrics["metric_assumptions"]["character_offsets"] is False
    calibration_thresholds = {
        point["threshold"] for point in metrics["calibration_curve"]
    }
    assert calibration_thresholds.issuperset(
        {
            0.5,
            0.75,
            0.9,
        }
    )
    assert metrics["calibration_report"]["confidence_zones"][0]["label"] == "clean"
    assert metrics["calibration_report"]["confidence_zones"][2]["label"] == "flag"


def test_compute_evaluation_metrics_flags_label_conflicts():
    metrics = server._compute_evaluation_metrics(
        scores=[0.8, 0.95, 0.9, 0.2],
        labels=[3, 0, 0, 0],
        tool_name="integritydesk",
        dataset_name="synthetic_small",
    )

    diagnostics = metrics["score_diagnostics"]

    assert diagnostics["label_conflict"] is True
    assert diagnostics["negatives_above_best_positive"] == 2
    assert "labeled negatives" in diagnostics["message"]


def test_compute_top_k_retrieval_uses_ranked_scores():
    scores = [0.9, 0.8, 0.1, 0.7, 0.6]
    labels = [0, 1, 1, 0, 1]

    retrieval = server._compute_top_k_retrieval(scores, labels, k=2)

    assert retrieval == 0.5


def test_ground_truth_labels_infer_demo_original_plagiarized_pairs():
    pair_results = [
        {"file_a": "00.py", "file_b": "00_plagiarized.py"},
        {"file_a": "00.py", "file_b": "01.py"},
        {"file_a": "plagiarized_001.py", "file_b": "original_001.py"},
    ]

    labels = server._get_ground_truth_labels("demo_sample", pair_results)

    assert labels == [3, 0, 3]


def test_ground_truth_labels_use_explicit_pair_metadata():
    pair_results = [
        {"file_a": "pair_a.py", "file_b": "pair_b.py", "ground_truth_label": 3},
        {"file_a": "pair_c.py", "file_b": "pair_d.py", "ground_truth_label": 0},
    ]

    labels = server._get_ground_truth_labels("synthetic", pair_results)

    assert labels == [3, 0]


def test_load_synthetic_pair_dataset_uses_explicit_pairs(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "synthetic"
    dataset_dir.mkdir()
    (dataset_dir / "generated_pairs.jsonl").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "case_001",
                        "code_a": "def add(a, b):\n    return a + b\n",
                        "code_b": "def sum_numbers(x, y):\n    return x + y\n",
                        "label": 1,
                        "clone_type": 2,
                    },
                    {
                        "id": "case_002",
                        "code_a": "def first():\n    return 1\n",
                        "code_b": "def second():\n    return 2\n",
                        "label": 0,
                        "clone_type": 0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    submissions, pairs = server._load_pair_labeled_benchmark_dataset(
        "synthetic", tmp_path / "job"
    )

    assert sorted(submissions) == [
        "case_001_a.py",
        "case_001_b.py",
        "case_002_a.py",
        "case_002_b.py",
    ]
    assert pairs == [
        {
            "file_a": "case_001_a.py",
            "file_b": "case_001_b.py",
            "label": 2,
            "case_category": "true_positive",
            "split": "unspecified",
        },
        {
            "file_a": "case_002_a.py",
            "file_b": "case_002_b.py",
            "label": 0,
            "case_category": "true_negative",
            "split": "unspecified",
        },
    ]


def test_load_generated_pair_dataset_supports_controlled_corpus(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "controlled_custom"
    dataset_dir.mkdir()
    (dataset_dir / "generated_pairs.jsonl").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "controlled_001",
                        "code_a": "def median(values):\n    return sorted(values)[0]\n",
                        "code_b": "def midpoint(items):\n    return sorted(items)[0]\n",
                        "label": 1,
                        "clone_type": 3,
                    },
                    {
                        "id": "controlled_002",
                        "code_a": "def first():\n    return 1\n",
                        "code_b": "def second():\n    return 2\n",
                        "label": 0,
                        "clone_type": 0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    submissions, pairs = server._load_pair_labeled_benchmark_dataset(
        "controlled_custom", tmp_path / "job"
    )

    assert sorted(submissions) == [
        "controlled_001_a.py",
        "controlled_001_b.py",
        "controlled_002_a.py",
        "controlled_002_b.py",
    ]
    assert pairs == [
        {
            "file_a": "controlled_001_a.py",
            "file_b": "controlled_001_b.py",
            "label": 3,
            "case_category": "true_positive",
            "split": "unspecified",
        },
        {
            "file_a": "controlled_002_a.py",
            "file_b": "controlled_002_b.py",
            "label": 0,
            "case_category": "true_negative",
            "split": "unspecified",
        },
    ]


def test_generated_pair_dataset_exposes_quality_certificate(tmp_path):
    dataset_dir = tmp_path / "controlled_quality"
    dataset_dir.mkdir()
    (dataset_dir / "metadata.json").write_text(
        json.dumps(
            {
                "generated_by_tools": [],
                "labeling_process": {
                    "required_reviewers_per_pair": 2,
                    "adjudicator_required": True,
                    "minimum_cohens_kappa": 0.7,
                    "status": "completed",
                },
                "inter_rater_agreement": {"cohens_kappa": 0.82},
                "split_protocol": {
                    "sets": ["train", "validation", "test"],
                    "rule": "locked test",
                },
                "external_validation": {
                    "pan_source_code_corpora": "included",
                    "results": {"plagdet": 0.8},
                },
            }
        ),
        encoding="utf-8",
    )
    pairs = [
        ("exact", 1, 1, "verbatim_copy", "true_positive", "train"),
        ("rename", 1, 2, "identifier_renaming", "true_positive", "train"),
        ("comments", 1, 2, "comments_and_formatting", "edge_case", "validation"),
        ("reorder", 1, 3, "statement_reordering", "edge_case", "train"),
        ("control", 1, 3, "control_flow_rewrite", "edge_case", "validation"),
        ("semantic", 1, 3, "semantic_rewrite", "edge_case", "test"),
        ("library", 1, 3, "library_substitution", "edge_case", "train"),
        ("split", 1, 3, "helper_extraction", "edge_case", "test"),
        (
            "cross_language",
            1,
            4,
            "cross_language_translation",
            "edge_case",
            "validation",
        ),
        (
            "obfuscated",
            1,
            3,
            "dead_code_and_identifier_obfuscation",
            "edge_case",
            "test",
        ),
        ("negative_1", 0, 0, "same_domain_different_task", "hard_negative", "train"),
        (
            "negative_2",
            0,
            0,
            "shared_boilerplate_only",
            "hard_negative",
            "validation",
        ),
        (
            "negative_3",
            0,
            0,
            "same_algorithm_family_different_behavior",
            "hard_negative",
            "test",
        ),
        ("negative_4", 0, 0, "unrelated", "true_negative", "train"),
    ]
    (dataset_dir / "generated_pairs.jsonl").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": f"cs_{pair_id}",
                        "code_a": "def a():\n    return 1\n",
                        "code_b": "def b():\n    return 1\n",
                        "label": label,
                        "clone_type": clone_type,
                        "obfuscation": obfuscation,
                        "language_a": (
                            "python"
                            if obfuscation == "cross_language_translation"
                            else None
                        ),
                        "language_b": (
                            "java"
                            if obfuscation == "cross_language_translation"
                            else None
                        ),
                        "case_category": case_category,
                        "split": split,
                    }
                    for (
                        pair_id,
                        label,
                        clone_type,
                        obfuscation,
                        case_category,
                        split,
                    ) in pairs
                ]
            }
        ),
        encoding="utf-8",
    )
    quality = server._build_benchmark_quality_certificate(dataset_dir)

    assert quality["certification_level"] == "gold_standard_external"
    assert quality["score_percent"] == 100.0
    assert quality["pair_count"] == 14
    assert quality["positive_pairs"] == 10
    assert quality["negative_pairs"] == 4
    assert quality["hard_negative_pairs"] == 3
    assert quality["leaked_tools"] == []
    assert set(quality["case_categories"]) == {
        "edge_case",
        "hard_negative",
        "true_negative",
        "true_positive",
    }
    assert set(quality["splits"]) == {"test", "train", "validation"}
    assert all(gate["passed"] for gate in quality["gates"])


def test_quality_certificate_flags_tool_derived_ground_truth(tmp_path):
    dataset_dir = tmp_path / "tool_leakage"
    dataset_dir.mkdir()
    (dataset_dir / "metadata.json").write_text(
        json.dumps({"generated_by_tools": ["moss"]}), encoding="utf-8"
    )
    (dataset_dir / "generated_pairs.jsonl").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "case_001",
                        "code_a": "def a():\n    return 1\n",
                        "code_b": "def b():\n    return 1\n",
                        "label": 1,
                        "clone_type": 1,
                        "obfuscation": "verbatim_copy",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    quality = server._build_benchmark_quality_certificate(dataset_dir)
    label_leakage_gate = next(
        gate for gate in quality["gates"] if gate["id"] == "label_leakage"
    )

    assert quality["leaked_tools"] == ["moss"]
    assert label_leakage_gate["passed"] is False


def test_builtin_controlled_corpus_available_without_data_directory(
    tmp_path, monkeypatch
):
    missing_data_dir = tmp_path / "missing_datasets"
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", missing_data_dir)

    response = asyncio.run(server.get_benchmark_datasets())
    payload = json.loads(response.body)
    datasets = {dataset["id"]: dataset for dataset in payload["datasets"]}

    controlled = datasets["clough_stevenson_style"]
    assert controlled["has_ground_truth"] is True
    assert controlled["size"] == "14 labeled pairs"
    assert (
        controlled["benchmark_quality"]["certification_level"]
        == "controlled_internal_ready"
    )
    assert controlled["benchmark_quality"]["score_percent"] < 100.0
    assert set(controlled["benchmark_quality"]["case_categories"]) == {
        "edge_case",
        "hard_negative",
        "true_negative",
        "true_positive",
    }


def test_load_pair_labeled_dataset_uses_builtin_controlled_corpus(
    tmp_path, monkeypatch
):
    missing_data_dir = tmp_path / "missing_datasets"
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", missing_data_dir)

    submissions, pairs = server._load_pair_labeled_benchmark_dataset(
        "clough_stevenson_style", tmp_path / "job"
    )

    assert len(submissions) == 28
    assert len(pairs) == 14
    assert any(name.endswith(".java") for name in submissions)
    assert sum(1 for pair in pairs if pair["label"] >= 2) == 10
    assert sum(1 for pair in pairs if pair["label"] == 0) == 4


def test_dataset_has_ground_truth_for_pair_labeled_sources(tmp_path):
    synthetic_dir = tmp_path / "synthetic"
    controlled_dir = tmp_path / "clough_stevenson_style"
    kaggle_dir = tmp_path / "kaggle_student_code"
    codexglue_dir = tmp_path / "codexglue_clone" / "huggingface"
    synthetic_dir.mkdir()
    controlled_dir.mkdir()
    kaggle_dir.mkdir()
    codexglue_dir.mkdir(parents=True)
    (synthetic_dir / "generated_pairs.jsonl").write_text("{}", encoding="utf-8")
    (controlled_dir / "generated_pairs.jsonl").write_text("{}", encoding="utf-8")
    (kaggle_dir / "cheating_dataset.csv").write_text("", encoding="utf-8")
    (codexglue_dir / "dataset_dict.json").write_text("{}", encoding="utf-8")

    assert server._dataset_has_pair_ground_truth("synthetic", synthetic_dir)
    assert server._dataset_has_pair_ground_truth(
        "clough_stevenson_style", controlled_dir
    )
    assert server._dataset_has_pair_ground_truth("kaggle_student_code", kaggle_dir)
    assert server._dataset_has_pair_ground_truth(
        "codexglue_clone", tmp_path / "codexglue_clone"
    )


def test_pan_benchmark_rejects_unlabeled_dataset(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "unlabeled"
    dataset_dir.mkdir()
    (dataset_dir / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (dataset_dir / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    client = TestClient(server.app)
    response = client.post(
        "/api/benchmark",
        data={
            "benchmark_type": "pan_optimization",
            "dataset": "unlabeled",
            "tools": ["integritydesk"],
        },
    )

    assert response.status_code == 400
    assert "PAN metrics require labeled ground truth" in response.json()["error"]


def test_pan_benchmark_reports_tool_errors_with_ground_truth(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "synthetic"
    dataset_dir.mkdir()
    (dataset_dir / "generated_pairs.jsonl").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "case_001",
                        "code_a": "def add(a, b):\n    return a + b\n",
                        "code_b": "def sum_numbers(x, y):\n    return x + y\n",
                        "label": 1,
                        "clone_type": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def failing_tool(tool, submissions, pairs):
        raise RuntimeError(f"{tool} failed before scoring")

    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "_run_competitor_tool", failing_tool)

    client = TestClient(server.app)
    response = client.post(
        "/api/benchmark",
        data={
            "benchmark_type": "pan_optimization",
            "dataset": "synthetic",
            "tools": ["moss"],
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["has_ground_truth"] is True
    assert payload["tool_scores"]["moss"]["pairs"] == 0
    assert payload["tool_scores"]["moss"]["error"] == "moss failed before scoring"
    assert "evaluation" not in payload


def test_extract_code_entries_from_row_supports_pair_fields():
    row = {
        "func1": "public class A { public static void main(String[] args) {} }\n",
        "func2": "public class B { public static void main(String[] args) {} }\n",
    }

    entries = server._extract_code_entries_from_row(row, "poj104", 0)

    assert [entry["filename"] for entry in entries] == [
        "poj104_0000_0.java",
        "poj104_0000_1.java",
    ]
    assert [entry["code"] for entry in entries] == [row["func1"], row["func2"]]


def test_load_benchmark_dataset_supports_pair_based_huggingface_rows(
    tmp_path, monkeypatch
):
    dataset_root = tmp_path / "poj104" / "huggingface" / "train"
    dataset_root.mkdir(parents=True)

    fake_module = types.SimpleNamespace(
        load_from_disk=lambda _: [
            {
                "func1": "public class A { public static void main(String[] args) {} }\n",
                "func2": "public class B { public static void main(String[] args) {} }\n",
            }
        ],
    )
    monkeypatch.setitem(sys.modules, "datasets", fake_module)
    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    submissions = server._load_benchmark_dataset("poj104", tmp_path / "job")

    assert sorted(submissions) == ["poj104_0000_0.java", "poj104_0000_1.java"]


def test_benchmark_dataset_cards_derive_metadata_from_huggingface_layout(
    tmp_path, monkeypatch
):
    dataset_root = tmp_path / "poj104" / "huggingface" / "train"
    dataset_root.mkdir(parents=True)
    (dataset_root / "dataset_info.json").write_text(
        json.dumps(
            {
                "features": {
                    "func1": {"dtype": "string", "_type": "Value"},
                    "func2": {"dtype": "string", "_type": "Value"},
                },
                "splits": {
                    "train": {"num_examples": 12},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    response = asyncio.run(server.get_benchmark_datasets())
    payload = json.loads(response.body)
    datasets = {dataset["id"]: dataset for dataset in payload["datasets"]}

    assert datasets["poj104"] == {
        "id": "poj104",
        "name": "Poj104",
        "desc": "Dataset: poj104",
        "icon": "📚",
        "color": "blue",
        "language": "mixed",
        "size": "24 files",
        "created_by": "System",
        "created_at": "",
        "is_demo": False,
        "has_ground_truth": False,
    }


def test_benchmark_dataset_cards_support_test_only_huggingface_layout(
    tmp_path, monkeypatch
):
    dataset_root = tmp_path / "human_eval" / "huggingface" / "test"
    dataset_root.mkdir(parents=True)
    (dataset_root / "dataset_info.json").write_text(
        json.dumps(
            {
                "features": {
                    "task_id": {"dtype": "string", "_type": "Value"},
                    "prompt": {"dtype": "string", "_type": "Value"},
                    "canonical_solution": {"dtype": "string", "_type": "Value"},
                },
                "splits": {
                    "test": {"num_examples": 164},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    response = asyncio.run(server.get_benchmark_datasets())
    payload = json.loads(response.body)
    datasets = {dataset["id"]: dataset for dataset in payload["datasets"]}

    assert datasets["human_eval"] == {
        "id": "human_eval",
        "name": "Human Eval",
        "desc": "Dataset: human_eval",
        "icon": "⚙️",
        "color": "slate",
        "language": "python",
        "size": "164 files",
        "created_by": "System",
        "created_at": "",
        "is_demo": False,
        "has_ground_truth": False,
    }


def test_read_files_from_dir_preserves_nested_duplicate_filenames(tmp_path):
    case_a = tmp_path / "case_a"
    case_b = tmp_path / "case_b"
    case_a.mkdir()
    case_b.mkdir()
    (case_a / "Main.java").write_text("class Main { int a = 1; }\n", encoding="utf-8")
    (case_b / "Main.java").write_text("class Main { int b = 2; }\n", encoding="utf-8")

    submissions = server._read_files_from_dir(tmp_path)

    assert submissions == {
        "case_a__Main.java": "class Main { int a = 1; }\n",
        "case_b__Main.java": "class Main { int b = 2; }\n",
    }


def test_benchmark_dataset_cards_count_unique_nested_files(tmp_path, monkeypatch):
    dataset_root = tmp_path / "IR-Plag-Dataset"
    (dataset_root / "case-01").mkdir(parents=True)
    (dataset_root / "case-02").mkdir(parents=True)
    (dataset_root / "case-01" / "Main.java").write_text(
        "class Main { int a = 1; }\n",
        encoding="utf-8",
    )
    (dataset_root / "case-02" / "Main.java").write_text(
        "class Main { int b = 2; }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "BENCHMARK_DATA_DIR", tmp_path)

    response = asyncio.run(server.get_benchmark_datasets())
    payload = json.loads(response.body)
    datasets = {dataset["id"]: dataset for dataset in payload["datasets"]}

    assert datasets["IR-Plag-Dataset"] == {
        "id": "IR-Plag-Dataset",
        "name": "Ir-Plag-Dataset",
        "desc": "Dataset: IR-Plag-Dataset",
        "icon": "⚙️",
        "color": "slate",
        "language": "java",
        "size": "2 files",
        "created_by": "System",
        "created_at": "",
        "is_demo": False,
        "has_ground_truth": False,
    }
