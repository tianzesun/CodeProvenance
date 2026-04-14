import asyncio
import io
import json
import zipfile

from starlette.datastructures import UploadFile

from src.backend.backend.api import server


def test_load_benchmark_dataset_supports_legacy_demo_python_extensions(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "demo_legacy_python"
    original_dir = dataset_dir / "original"
    plagiarized_dir = dataset_dir / "plagiarized"
    original_dir.mkdir(parents=True)
    plagiarized_dir.mkdir()

    (dataset_dir / "metadata.json").write_text(
        json.dumps({"language": "python", "name": "Legacy Python Demo"}),
        encoding="utf-8",
    )
    (original_dir / "00.python").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (plagiarized_dir / "00.python").write_text("def sum_numbers(x, y):\n    return x + y\n", encoding="utf-8")

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
