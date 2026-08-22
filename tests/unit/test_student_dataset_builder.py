"""Unit tests for the student-code holdout ingestion pipeline.

Verifies ``build_student_dataset`` materialises labelled student submissions
into the AIGCodeSet-compatible ``<output>/data/{ai,human,samples.jsonl}`` layout
from three input formats (folder, CSV, JSONL), preserves the ``problem_id``
grouping needed for grouped-holdout evaluation, and that
``benchmark_classifier`` can be pointed at a non-default dataset dir.
"""

import json
from pathlib import Path

import pytest

from src.backend.engines.ai import build_student_dataset as builder

AI_CODE = 'def solve(data):\n    """Compute the result.\n\n    Args:\n        data: input.\n\n    Returns:\n        The result.\n    """\n    return sum(data)\n'
HUMAN_CODE = "def solve(data):\n    total = 0\n    for x in data:\n        total += x\n    return total\n"


@pytest.fixture
def sample_folder(tmp_path: Path) -> Path:
    """A labelled ai/ + human/ folder with one sample each."""
    folder = tmp_path / "labelled"
    (folder / "ai").mkdir(parents=True)
    (folder / "human").mkdir(parents=True)
    (folder / "human" / "problem.txt").write_text("prob-abc", encoding="utf-8")
    (folder / "human" / "sol.py").write_text(HUMAN_CODE, encoding="utf-8")
    (folder / "ai" / "sol.py").write_text(AI_CODE, encoding="utf-8")
    return folder


def _read_meta(out_dir: Path) -> list:
    """Read the materialised samples.jsonl index."""
    lines = (
        (out_dir / "data" / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    )
    return [json.loads(line) for line in lines if line.strip()]


class TestMaterialiseFolder:
    """Ingestion from an ai/ + human/ folder layout."""

    def test_writes_data_layout(self, sample_folder: Path, tmp_path: Path) -> None:
        """Files land under <out>/data/{ai,human} with an index."""
        out = tmp_path / "out"
        counts = builder.materialise(sample_folder, out)
        assert counts == {"ai": 1, "human": 1, "skipped": 0}
        assert (out / "data" / "ai").is_dir()
        assert (out / "data" / "human").is_dir()
        assert (out / "data" / "samples.jsonl").exists()

    def test_labels_assigned_by_directory(
        self, sample_folder: Path, tmp_path: Path
    ) -> None:
        """ai/ files are labelled 1, human/ files 0."""
        out = tmp_path / "out"
        builder.materialise(sample_folder, out)
        meta = _read_meta(out)
        assert len(meta) == 2
        by_label = {entry["label"] for entry in meta}
        assert by_label == {0, 1}
        ai_entry = [e for e in meta if e["submission_id"].startswith("ai")]
        assert all(e["label"] == 1 for e in ai_entry)

    def test_problem_id_from_problem_txt(
        self, sample_folder: Path, tmp_path: Path
    ) -> None:
        """problem_id comes from problem.txt when present, else file stem."""
        out = tmp_path / "out"
        builder.materialise(sample_folder, out)
        meta = _read_meta(out)
        human = [e for e in meta if e["label"] == 0][0]
        assert human["problem_id"] == "prob-abc"
        ai = [e for e in meta if e["label"] == 1][0]
        assert ai["problem_id"] == "sol"

    def test_files_are_written(self, sample_folder: Path, tmp_path: Path) -> None:
        """Each index entry references a real file under data/."""
        out = tmp_path / "out"
        builder.materialise(sample_folder, out)
        for entry in _read_meta(out):
            label_dir = "ai" if entry["label"] == 1 else "human"
            path = out / "data" / label_dir / entry["file"]
            assert path.exists()
            assert (
                len(path.read_text(encoding="utf-8").strip()) >= builder.MIN_CODE_CHARS
            )

    def test_short_code_skipped(self, tmp_path: Path) -> None:
        """Samples shorter than MIN_CODE_CHARS are dropped."""
        folder = tmp_path / "short"
        (folder / "human").mkdir(parents=True)
        (folder / "human" / "t.py").write_text("x = 1\n", encoding="utf-8")
        out = tmp_path / "out"
        with pytest.raises(RuntimeError, match="No valid records"):
            builder.materialise(folder, out)


class TestMaterialiseRecords:
    """Ingestion from CSV / JSONL record files."""

    def _csv(self, tmp_path: Path) -> Path:
        import csv

        path = tmp_path / "records.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["code", "label", "problem_id", "llm"])
            writer.writerow([HUMAN_CODE, 0, "prob1", "STUDENT"])
            writer.writerow([AI_CODE, 1, "prob2", "STUDENT"])
        return path

    def test_csv_ingestion(self, tmp_path: Path) -> None:
        """CSV records materialise with explicit labels."""
        out = tmp_path / "out"
        builder.materialise(self._csv(tmp_path), out)
        meta = _read_meta(out)
        assert {entry["label"] for entry in meta} == {0, 1}
        assert {entry["problem_id"] for entry in meta} == {"prob1", "prob2"}

    def test_jsonl_ingestion(self, tmp_path: Path) -> None:
        """JSONL records materialise with explicit labels."""
        path = tmp_path / "records.jsonl"
        path.write_text(
            "\n".join(
                [
                    json.dumps({"code": HUMAN_CODE, "label": 0, "problem_id": "prob1"}),
                    json.dumps({"code": AI_CODE, "label": 1, "problem_id": "prob2"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        out = tmp_path / "out"
        builder.materialise(path, out)
        meta = _read_meta(out)
        assert {entry["label"] for entry in meta} == {0, 1}

    def test_invalid_label_row_skipped(self, tmp_path: Path) -> None:
        """Rows with a non-integer label are dropped without crashing."""
        import csv

        path = tmp_path / "bad.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["code", "label"])
            writer.writerow([HUMAN_CODE, "maybe"])
            writer.writerow([AI_CODE, 1])
        out = tmp_path / "out"
        builder.materialise(path, out)
        meta = _read_meta(out)
        assert len(meta) == 1
        assert meta[0]["label"] == 1

    def test_dedupe_by_code(self, tmp_path: Path) -> None:
        """Duplicate code is materialised once."""
        import csv

        path = tmp_path / "dup.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["code", "label"])
            writer.writerow([HUMAN_CODE, 0])
            writer.writerow([HUMAN_CODE, 0])
        out = tmp_path / "out"
        builder.materialise(path, out)
        assert len(_read_meta(out)) == 1

    def test_missing_input_raises(self, tmp_path: Path) -> None:
        """A non-existent input path raises a clear error."""
        with pytest.raises(RuntimeError, match="does not exist"):
            builder.materialise(tmp_path / "nope", tmp_path / "out")


class TestBenchmarkDatasetDir:
    """The classifier benchmark can be pointed at a student dataset."""

    def test_set_dataset_dir_redirects(self, tmp_path: Path) -> None:
        """set_dataset_dir re-points DATA_DIR/REPORT_PATH at a new dataset."""
        import src.backend.engines.ai.benchmark_classifier as bench

        dataset = tmp_path / "dataset"
        (dataset / "data" / "ai").mkdir(parents=True)
        (dataset / "data" / "human").mkdir(parents=True)
        (dataset / "data" / "samples.jsonl").write_text("", encoding="utf-8")

        bench.set_dataset_dir(dataset)
        assert bench.DATA_DIR == dataset / "data"
        assert bench.REPORT_PATH == dataset / "benchmark_report.json"

    def test_load_dataset_reads_samples_jsonl(self, tmp_path: Path) -> None:
        """load_dataset reads the materialised student index + files."""
        import src.backend.engines.ai.benchmark_classifier as bench

        out = tmp_path / "dataset"
        folder = tmp_path / "labelled"
        (folder / "human").mkdir(parents=True)
        (folder / "human" / "a.py").write_text(HUMAN_CODE, encoding="utf-8")
        (folder / "ai").mkdir(parents=True)
        (folder / "ai" / "b.py").write_text(AI_CODE, encoding="utf-8")
        builder.materialise(folder, out)
        bench.set_dataset_dir(out)

        codes, labels, problems, llms = bench.load_dataset()
        assert len(codes) == 2
        assert set(labels) == {0, 1}
        assert all(llm == "STUDENT" for llm in llms)


class TestFolderIndexRoundTrip:
    """A folder carrying a materialised samples.jsonl index round-trips."""

    def test_index_metadata_is_reused(self, tmp_path: Path) -> None:
        """problem_id/llm/submission_id come from the sibling index."""
        folder = tmp_path / "dataset_data"
        (folder / "ai").mkdir(parents=True)
        (folder / "human").mkdir(parents=True)
        (folder / "ai" / "gen_a.py").write_text(AI_CODE, encoding="utf-8")
        (folder / "human" / "gen_b.py").write_text(HUMAN_CODE, encoding="utf-8")
        (folder / "samples.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "file": "gen_a.py",
                            "label": 1,
                            "problem_id": "p-canonical-ai",
                            "llm": "GEMINI",
                            "submission_id": "s-ai-1",
                        }
                    ),
                    json.dumps(
                        {
                            "file": "gen_b.py",
                            "label": 0,
                            "problem_id": "p-canonical-human",
                            "llm": "HUMAN",
                            "submission_id": "s-human-1",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        out = tmp_path / "out"
        builder.materialise(folder, out)
        meta = _read_meta(out)
        by_problem = {entry["problem_id"]: entry for entry in meta}
        assert set(by_problem) == {"p-canonical-ai", "p-canonical-human"}
        assert by_problem["p-canonical-ai"]["llm"] == "GEMINI"
        assert by_problem["p-canonical-ai"]["submission_id"] == "s-ai-1"

    def test_folder_position_still_decides_label(self, tmp_path: Path) -> None:
        """A contradictory index label never overrides the ai/ vs human/ dir."""
        folder = tmp_path / "dataset_data"
        (folder / "ai").mkdir(parents=True)
        (folder / "ai" / "gen_a.py").write_text(AI_CODE, encoding="utf-8")
        (folder / "samples.jsonl").write_text(
            json.dumps({"file": "gen_a.py", "label": 0, "problem_id": "p1"}) + "\n",
            encoding="utf-8",
        )

        out = tmp_path / "out"
        builder.materialise(folder, out)
        meta = _read_meta(out)
        assert len(meta) == 1
        assert meta[0]["label"] == 1

    def test_reingestion_preserves_grouping(self, tmp_path: Path) -> None:
        """materialise(output) keeps every (problem, label, llm, submission) key."""
        folder = tmp_path / "labelled"
        (folder / "ai").mkdir(parents=True)
        (folder / "human").mkdir(parents=True)
        (folder / "ai" / "gen_a.py").write_text(AI_CODE, encoding="utf-8")
        (folder / "human" / "gen_b.py").write_text(HUMAN_CODE, encoding="utf-8")
        first = tmp_path / "first"
        builder.materialise(folder, first)

        second = tmp_path / "second"
        builder.materialise(first / "data", second)

        def grouping(rows):
            return {
                (e["problem_id"], e["label"], e["llm"], e["submission_id"])
                for e in rows
            }

        assert grouping(_read_meta(first)) == grouping(_read_meta(second))
