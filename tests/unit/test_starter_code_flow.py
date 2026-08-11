"""Regression tests for starter-code handling in the upload/detection flow.

Covers two previously broken behaviors:
1. Instructor starter files stored under a reserved ``starter/`` directory must
   not be read back as student submissions.
2. ``BatchDetectionService`` must apply starter-line removal during comparison
   so shared template code does not inflate similarity scores.
"""

from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
)
from src.backend.api import server
from src.backend.engines.features.feature_extractor import FeatureExtractor


def _no_embedding(self, a, b):
    """Disable the embedding feature so tests never hit HuggingFace/network."""
    return None


def _install_no_embedding(monkeypatch):
    """Monkeypatch the embedding runtime off for hermetic test runs."""
    monkeypatch.setattr(FeatureExtractor, "_run_embedding", _no_embedding)


def test_read_files_from_dir_excludes_reserved_starter_dir(tmp_path):
    """Starter/template files under ``starter/`` are never treated as submissions."""
    root = tmp_path / "job"
    root.mkdir()
    (root / "alice.py").write_text("x = 1\nprint(x)\n", encoding="utf-8")
    (root / "bob.py").write_text("x = 2\nprint(x)\n", encoding="utf-8")
    starter_dir = root / "starter"
    starter_dir.mkdir()
    (starter_dir / "template.py").write_text(
        "# starter\ndef base():\n    pass\n", encoding="utf-8"
    )

    submissions = server._read_files_from_dir(root)

    assert set(submissions) == {"alice.py", "bob.py"}
    assert not any("starter" in name for name in submissions)


def test_starter_removal_applied_in_compare_all_pairs(monkeypatch):
    """Shared starter lines must be stripped before scoring so they do not
    inflate similarity between otherwise-independent submissions."""
    _install_no_embedding(monkeypatch)
    starter = "import numpy as np\nimport pandas as pd\n\n"
    submissions = {
        "A.py": starter + "def solve_a(x):\n    return x + 1\n",
        "B.py": starter + "def solve_b(x):\n    return x * 2\n",
    }

    without = BatchDetectionService(threshold=0.5).compare_all_pairs(submissions)
    with_removal = BatchDetectionService(
        threshold=0.5, starter_sources=[starter]
    ).compare_all_pairs(submissions)

    assert without[0].score > with_removal[0].score


def test_starter_removal_applied_in_compare_pairs(monkeypatch):
    """Explicit benchmark pairs also strip starter lines."""
    _install_no_embedding(monkeypatch)
    starter = "import numpy as np\nimport pandas as pd\n\n"
    submissions = {
        "A.py": starter + "def solve_a(x):\n    return x + 1\n",
        "B.py": starter + "def solve_b(x):\n    return x * 2\n",
    }
    pairs = [{"file_a": "A.py", "file_b": "B.py"}]

    without = BatchDetectionService(threshold=0.5).compare_pairs(submissions, pairs)
    with_removal = BatchDetectionService(
        threshold=0.5, starter_sources=[starter]
    ).compare_pairs(submissions, pairs)

    assert without[0].score > with_removal[0].score
    assert "solve_a" in with_removal[0].code_a
    assert "import numpy" not in with_removal[0].code_a


def test_ingest_folder_applies_starter_removal_filtered_source(tmp_path):
    """ingest_folder returns starter-stripped content via filtered_source."""
    starter = "print('template')\n"
    folder = tmp_path / "subs"
    folder.mkdir()
    (folder / "A.py").write_text(starter + "x = 1\n", encoding="utf-8")

    service = BatchDetectionService(threshold=0.5, starter_sources=[starter])
    submissions = service.ingest_folder(folder)

    assert submissions["A.py"] == "x = 1"
    assert "template" not in submissions["A.py"]
