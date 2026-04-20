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

    assert metrics["precision"] == 0.6667
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 0.8
    assert metrics["granularity"] == 1.0
    assert metrics["plagdet"] == 0.8
    assert metrics["plagdet_percent"] == 80.0
    assert metrics["top_10_retrieval"] == 1.0
    assert metrics["top_20_retrieval"] == 1.0
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
        "top_10_retrieval": 1.0,
        "top_20_retrieval": 1.0,
        "false_positive_rate": 0.5,
        "auc_pr": metrics["auc_pr"],
        "engine_contribution": {},
        "ai_generated_recall": None,
        "avg_runtime_seconds": 0.5,
    }
    assert metrics["granularity_basis"] == "pair_level_single_detection"


def test_compute_top_k_retrieval_uses_ranked_scores():
    scores = [0.9, 0.8, 0.1, 0.7, 0.6]
    labels = [0, 1, 1, 0, 1]

    retrieval = server._compute_top_k_retrieval(scores, labels, k=2)

    assert retrieval == 1 / 3


def test_ground_truth_labels_infer_demo_original_plagiarized_pairs():
    pair_results = [
        {"file_a": "00.py", "file_b": "00_plagiarized.py"},
        {"file_a": "00.py", "file_b": "01.py"},
        {"file_a": "plagiarized_001.py", "file_b": "original_001.py"},
    ]

    labels = server._get_ground_truth_labels("demo_sample", pair_results)

    assert labels == [3, 0, 3]


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
