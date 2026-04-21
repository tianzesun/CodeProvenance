import asyncio
import io
import json
import sys
import types
import zipfile

from starlette.datastructures import UploadFile

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

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.5
    assert metrics["f1_score"] == 0.6667
    assert metrics["granularity"] == 1.0
    assert metrics["plagdet"] == 0.6667
    assert metrics["plagdet_percent"] == 66.67
    assert metrics["top_10_retrieval"] == 0.5
    assert metrics["top_20_retrieval"] == 0.5
    assert metrics["top_10_recall"] == 1.0
    assert metrics["top_20_recall"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
    assert "auc_pr" in metrics
    assert metrics["engine_contribution"] == {}
    assert metrics["ai_generated_recall"] is None
    assert metrics["runtime_seconds"] == 2.0
    assert metrics["avg_runtime_seconds"] == 0.5
    assert metrics["pan_metrics"] == {
        "precision": 1.0,
        "recall": 0.5,
        "f1_score": 0.6667,
        "granularity": 1.0,
        "plagdet": 0.6667,
        "top_10_retrieval": 0.5,
        "top_20_retrieval": 0.5,
        "top_10_recall": 1.0,
        "top_20_recall": 1.0,
        "false_positive_rate": 0.0,
        "auc_pr": metrics["auc_pr"],
        "engine_contribution": {},
        "ai_generated_recall": None,
        "avg_runtime_seconds": 0.5,
        "score_diagnostics": metrics["score_diagnostics"],
    }
    assert metrics["score_diagnostics"]["label_conflict"] is False
    assert metrics["granularity_basis"] == "pair_level_single_detection"


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
        {"file_a": "case_001_a.py", "file_b": "case_001_b.py", "label": 2},
        {"file_a": "case_002_a.py", "file_b": "case_002_b.py", "label": 0},
    ]


def test_build_benchmark_pairs_refuses_oversized_all_pairs(monkeypatch):
    monkeypatch.setattr(server, "ALL_PAIRS_BENCHMARK_MAX_PAIRS", 3)
    submissions = {f"student_{idx}.py": "print('hello')\n" for idx in range(4)}

    pairs, error = server._build_benchmark_pairs(submissions, [])

    assert pairs == []
    assert "6 file pairs" in error
    assert "interactive benchmark limit is 3 pairs" in error


def test_build_benchmark_pairs_allows_explicit_pairs_over_all_pairs_limit(monkeypatch):
    monkeypatch.setattr(server, "ALL_PAIRS_BENCHMARK_MAX_PAIRS", 1)
    submissions = {
        "a.py": "print('a')\n",
        "b.py": "print('b')\n",
        "c.py": "print('c')\n",
    }
    explicit_pairs = [
        {"file_a": "a.py", "file_b": "b.py", "label": 3},
        {"file_a": "a.py", "file_b": "missing.py", "label": 0},
    ]

    pairs, error = server._build_benchmark_pairs(submissions, explicit_pairs)

    assert error == ""
    assert pairs == [("a.py", "b.py")]


def test_upload_engine_weights_respect_optional_runtime_toggles(monkeypatch):
    payload = {
        "engine_weights": {
            "token": 0.2,
            "ast": 0.2,
            "winnowing": 0.2,
            "gst": 0.2,
            "semantic": 0.1,
            "web": 0.1,
            "ai_detection": 0.1,
            "execution_cfg": 0.1,
        },
        "web_analysis_enabled": False,
        "ai_detection_enabled": False,
        "execution_cfg_enabled": False,
    }
    monkeypatch.setattr(server, "_build_settings_payload", lambda _tenant_id: payload)

    weights = server._get_upload_engine_weights("tenant-1")

    assert weights["token"] == 0.2
    assert weights["web"] == 0.0
    assert weights["ai_detection"] == 0.0
    assert weights["execution_cfg"] == 0.0


def test_upload_engine_weights_keep_enabled_optional_engines(monkeypatch):
    payload = {
        "engine_weights": {
            "token": 0.2,
            "ast": 0.2,
            "winnowing": 0.2,
            "gst": 0.2,
            "semantic": 0.1,
            "web": 0.1,
            "ai_detection": 0.1,
            "execution_cfg": 0.1,
        },
        "web_analysis_enabled": True,
        "ai_detection_enabled": True,
        "execution_cfg_enabled": True,
    }
    monkeypatch.setattr(server, "_build_settings_payload", lambda _tenant_id: payload)

    weights = server._get_upload_engine_weights(
        "tenant-1", ["web", "ai_detection", "execution_cfg"]
    )

    assert weights["token"] == 0.0
    assert weights["web"] == 0.1
    assert weights["ai_detection"] == 0.1
    assert weights["execution_cfg"] == 0.1


def test_dataset_has_ground_truth_for_pair_labeled_sources(tmp_path):
    synthetic_dir = tmp_path / "synthetic"
    kaggle_dir = tmp_path / "kaggle_student_code"
    codexglue_dir = tmp_path / "codexglue_clone" / "huggingface"
    synthetic_dir.mkdir()
    kaggle_dir.mkdir()
    codexglue_dir.mkdir(parents=True)
    (synthetic_dir / "generated_pairs.jsonl").write_text("{}", encoding="utf-8")
    (kaggle_dir / "cheating_dataset.csv").write_text("", encoding="utf-8")
    (codexglue_dir / "dataset_dict.json").write_text("{}", encoding="utf-8")

    assert server._dataset_has_pair_ground_truth("synthetic", synthetic_dir)
    assert server._dataset_has_pair_ground_truth("kaggle_student_code", kaggle_dir)
    assert server._dataset_has_pair_ground_truth(
        "codexglue_clone", tmp_path / "codexglue_clone"
    )


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

    assert payload["datasets"] == [
        {
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
    ]


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

    assert payload["datasets"] == [
        {
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
    ]


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

    assert payload["datasets"] == [
        {
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
    ]
