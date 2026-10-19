"""Unit tests for the learned fusion training runner helpers."""

import json
from pathlib import Path

import pytest

from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair
from src.backend.benchmark.runners.learned_fusion_training_runner import (
    LearnedFusionTrainingRunner,
    run_learned_fusion_training,
)


class TestNormalizePair:
    """Order-independent pair key normalization."""

    def test_sorts_files(self):
        """Pair keys are normalized by sorted file names."""
        assert LearnedFusionTrainingRunner._normalize_pair("b.java", "a.java") == (
            "a.java",
            "b.java",
        )

    def test_idempotent(self):
        """Normalization is order independent and stable."""
        key = LearnedFusionTrainingRunner._normalize_pair("a.java", "b.java")
        assert LearnedFusionTrainingRunner._normalize_pair("a.java", "b.java") == key


class TestAuc:
    """ROC-AUC concordance estimator."""

    def test_perfect_separation(self):
        """Perfectly separated scores yield AUC 1.0."""
        auc = LearnedFusionTrainingRunner._auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0])
        assert auc == 1.0

    def test_requires_both_classes(self):
        """AUC requires both classes present in labels."""
        assert LearnedFusionTrainingRunner._auc([0.9, 0.8], [1, 1]) == 0.0


class TestBestThreshold:
    """Best-F1 threshold sweep."""

    def test_picks_perfect_split(self):
        """Threshold sweep finds the perfect F1 split."""
        best = LearnedFusionTrainingRunner(
            output_dir=Path("/tmp/unused")
        )._best_threshold([0.9, 0.85, 0.2, 0.1], [1, 1, 0, 0])
        assert best["f1"] == 1.0
        assert best["threshold"] <= 0.9

    def test_metrics_at_threshold(self):
        """Precision/recall/F1 computed at a cutoff."""
        metrics = LearnedFusionTrainingRunner._metrics_at_threshold(
            [0.9, 0.4, 0.6, 0.1], [1, 1, 0, 0], 0.5
        )
        assert metrics["precision"] == 0.5
        assert metrics["recall"] == 0.5
        assert metrics["f1"] == 0.5


class TestReportSerialization:
    """Report JSON round-trip includes learned coefficients."""

    def _report(self):
        """Build a representative report instance for serialization tests."""
        from src.backend.benchmark.runners.learned_fusion_training_runner import (
            LearnedFusionReport,
        )

        return LearnedFusionReport(
            generated_at="2026-01-01T00:00:00",
            train_datasets=["IR-Plag-Dataset", "conplag"],
            pair_count=2,
            positive_pairs=1,
            negative_pairs=1,
            feature_names=[
                "ast",
                "fingerprint",
                "embedding",
                "ngram",
                "winnowing",
                "logic_flow",
                "coverage",
            ],
            production_fused_auc=0.7,
            production_fused_f1_best=0.6,
            production_fused_threshold=0.2,
            cv_mode="grouped 5-fold",
            cv_auc=0.9,
            cv_f1_best=0.8,
            cv_threshold=0.4,
            cv_fold_count=2,
            coefficient_weights={"ast": -2.5, "winnowing": 4.2},
            intercept=-2.0,
            artifact_path="/tmp/model.json",
        )

    def test_to_json_dict(self):
        """Report serializes learned coefficients and metadata."""
        report = self._report()
        payload = report.to_json_dict()
        assert payload["feature_names"] == [
            "ast",
            "fingerprint",
            "embedding",
            "ngram",
            "winnowing",
            "logic_flow",
            "coverage",
        ]
        assert payload["coefficient_weights"].get("ast") is not None

    def test_save_json(self, tmp_path):
        """Report persists to a JSON file."""
        report = self._report()
        path = report.save_json(tmp_path / "report.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["pair_count"] == 2
        assert payload["cv_auc"] == 0.9
        assert payload["cv_mode"] == "grouped 5-fold"


class TestLanguageExtensions:
    """Corpus language decides the file extension seen by the engines."""

    def test_known_languages(self):
        """Known corpus languages map to their real extension."""
        runner = LearnedFusionTrainingRunner(output_dir=Path("/tmp/unused"))
        assert runner._extension_for("java") == ".java"
        assert runner._extension_for("Python") == ".py"
        assert runner._extension_for(" c ") == ".c"

    def test_unknown_language_falls_back(self):
        """An unknown language gets a neutral extension rather than .java."""
        runner = LearnedFusionTrainingRunner(output_dir=Path("/tmp/unused"))
        assert runner._extension_for("") == ".txt"
        assert runner._extension_for("brainfuck") == ".txt"


class TestGroupKey:
    """Fold keys are per dataset, so unrelated ids never share a fold."""

    def test_namespaced_by_dataset(self):
        """Same numeric group in two corpora yields two different keys."""
        from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair

        poolc = LabeledPair(
            "a", "x", "y", 1, "python", {"dataset": "poolc_600k_python", "group": "12"}
        )
        conplag = LabeledPair(
            "b", "x", "y", 1, "java", {"dataset": "conplag", "problem": "12"}
        )
        assert LearnedFusionTrainingRunner._group_key(poolc) == (
            "poolc_600k_python::12"
        )
        assert LearnedFusionTrainingRunner._group_key(conplag) == "conplag::12"

    def test_poolc_group_is_order_independent(self):
        """PoolC groups are unordered endpoint-group pairs."""
        assert (
            LearnedFusionTrainingRunner._poolc_group_key(
                {"code1_group": 96, "code2_group": 60}
            )
            == "60-96"
        )
        assert (
            LearnedFusionTrainingRunner._poolc_group_key(
                {"code1_group": 60, "code2_group": 96}
            )
            == "60-96"
        )


class TestLimitPairs:
    """A per-dataset cap never collapses a corpus to a single class."""

    def _pairs(self, positives: int, negatives: int):
        """Build a simple labelled pair list."""
        from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair

        pairs = []
        for index in range(positives):
            pairs.append(LabeledPair(f"p{index}", "a", "b", 1, "python", {}))
        for index in range(negatives):
            pairs.append(LabeledPair(f"n{index}", "a", "b", 0, "python", {}))
        return pairs

    def test_cap_keeps_both_classes(self):
        """A cap samples both classes down together."""
        runner = LearnedFusionTrainingRunner(
            output_dir=Path("/tmp/unused"), max_pairs_per_dataset=10
        )
        capped = runner._limit_pairs(self._pairs(50, 50))
        assert len(capped) == 10
        assert sum(pair.label for pair in capped) == 5

    def test_cap_is_deterministic(self):
        """The same seed picks the same pairs."""
        runner = LearnedFusionTrainingRunner(
            output_dir=Path("/tmp/unused"), max_pairs_per_dataset=10
        )
        first = [pair.pair_id for pair in runner._limit_pairs(self._pairs(40, 40))]
        second = [pair.pair_id for pair in runner._limit_pairs(self._pairs(40, 40))]
        assert first == second

    def test_without_cap_returns_input(self):
        """No cap means no sampling."""
        runner = LearnedFusionTrainingRunner(output_dir=Path("/tmp/unused"))
        pairs = self._pairs(3, 3)
        assert runner._limit_pairs(pairs) == pairs


class TestGroupedKFold:
    """Grouped k-fold must never split one group across train and test."""

    def _runner(self, tmp_path):
        """Build a runner that writes its report into a temp directory."""
        return LearnedFusionTrainingRunner(output_dir=tmp_path, cv_folds=3)

    def test_each_group_lands_in_exactly_one_fold(self, tmp_path, monkeypatch):
        """Capture the held-out sets and check group integrity."""
        runner = self._runner(tmp_path)
        groups = [f"g{index // 4}" for index in range(40)]
        captured = {}

        def fake_score(rows, labels, held_out_sets, fold_label, sample_weights=None):
            captured["sets"] = list(held_out_sets.values())
            return (
                {index: 0.5 for indices in held_out_sets.values() for index in indices},
                len(held_out_sets),
            )

        monkeypatch.setattr(runner, "_score_held_out_sets", fake_score)
        oof, fold_count = runner._group_kfold_cross_validate(
            [{} for _ in groups], [1, 0] * 20, groups, 3
        )

        assert fold_count == 3
        assert sorted(oof) == list(range(40))
        for group_index in range(10):
            members = set(range(group_index * 4, group_index * 4 + 4))
            holders = [
                index
                for index, indices in enumerate(captured["sets"])
                if members & set(indices)
            ]
            assert len(holders) == 1
            assert members <= set(captured["sets"][holders[0]])

    def test_rejects_single_fold(self, tmp_path):
        """Fewer than two folds is a programming error, not a silent full fit."""
        runner = self._runner(tmp_path)
        with pytest.raises(ValueError):
            runner._group_kfold_cross_validate([{}], [1], ["g"], 1)


class TestKaggleLoader:
    """The same-classroom student corpus loads with its real labels."""

    def test_loads_pairs_from_csv(self, tmp_path):
        """Pairs, labels and language come from the CSV and files."""
        dataset = tmp_path / "kaggle_student_code"
        dataset.mkdir()
        (dataset / "submission1.py").write_text("print(1)\n", encoding="utf-8")
        (dataset / "submission2.py").write_text("print(2)\n", encoding="utf-8")
        (dataset / "cheating_dataset.csv").write_text(
            "File_1,File_2,Label\nsubmission1.py,submission2.py,1\n",
            encoding="utf-8",
        )
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path / "reports", dataset_roots=[tmp_path]
        )
        pairs = runner._load_kaggle_pairs()
        assert len(pairs) == 1
        assert pairs[0].label == 1
        assert pairs[0].language == "python"
        assert pairs[0].metadata["group"] == "classroom"

    def test_skips_missing_files(self, tmp_path):
        """A row whose files are absent is skipped, not fatal."""
        dataset = tmp_path / "kaggle_student_code"
        dataset.mkdir()
        (dataset / "cheating_dataset.csv").write_text(
            "File_1,File_2,Label\ngone1.py,gone2.py,0\n", encoding="utf-8"
        )
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path / "reports", dataset_roots=[tmp_path]
        )
        assert runner._load_kaggle_pairs() == []


class TestPoolcLoader:
    """PoolC sampling honours the cap and the negative ratio."""

    def _shard(self, tmp_path, rows):
        """Write one parquet shard with the PoolC schema."""
        pytest.importorskip("pyarrow")
        import pyarrow as pa
        import pyarrow.parquet as pq

        dataset = tmp_path / "poolc_600k_python" / "data"
        dataset.mkdir(parents=True, exist_ok=True)
        table = pa.table(
            {
                "code1": [row[0] for row in rows],
                "code2": [row[1] for row in rows],
                "similar": pa.array([row[2] for row in rows], type=pa.int64()),
                "code1_group": pa.array([row[3] for row in rows], type=pa.int64()),
                "code2_group": pa.array([row[4] for row in rows], type=pa.int64()),
            }
        )
        pq.write_table(table, dataset / "train-00000-of-00001.parquet")
        return tmp_path

    def _rows(self):
        """Ten same-group positives and ten cross-group negatives."""
        rows = []
        for index in range(10):
            rows.append((f"print({index})", f"print({index} + 1)", 1, 1, 1))
        for index in range(10):
            rows.append((f"print({index})", f"x = {index}", 0, 1, 2))
        return rows

    def test_positives_only_by_default(self, tmp_path):
        """Default ratio 0 admits no cross-problem negatives."""
        root = self._shard(tmp_path, self._rows())
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path / "reports",
            dataset_roots=[root],
            max_pairs_per_dataset=10,
        )
        pairs = runner._load_poolc_pairs()
        assert len(pairs) == 5
        assert all(pair.label == 1 for pair in pairs)
        assert all(pair.language == "python" for pair in pairs)
        assert pairs[0].metadata["dataset"] == "poolc_600k_python"

    def test_negative_ratio_admits_cross_group_pairs(self, tmp_path):
        """A 1.0 ratio admits one negative per positive."""
        root = self._shard(tmp_path, self._rows())
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path / "reports",
            dataset_roots=[root],
            max_pairs_per_dataset=10,
            poolc_negative_ratio=1.0,
        )
        pairs = runner._load_poolc_pairs()
        assert len(pairs) == 10
        assert sum(pair.label for pair in pairs) == 5
        assert {pair.metadata["group"] for pair in pairs} == {"1-1", "1-2"}


class TestFeatureCache:
    """The feature cache stores, reloads and invalidates rows."""

    def _pair(self, code_a="a", code_b="b", pair_id="p1", label=1):
        """Build one labelled pair for cache tests."""
        from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair

        return LabeledPair(
            pair_id, code_a, code_b, label, "python", {"dataset": "conplag"}
        )

    def test_append_and_reload(self, tmp_path):
        """Written rows come back keyed by the pair digest."""
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path, cache_path=tmp_path / "cache.jsonl"
        )
        pair = self._pair()
        key = runner._cache_key(pair)
        runner._append_feature_cache([(key, {"ast": 0.5, "raw_score": 0.25})])
        assert runner._load_feature_cache() == {key: {"ast": 0.5, "raw_score": 0.25}}

    def test_edited_code_changes_the_key(self, tmp_path):
        """Editing a corpus file invalidates its cached row."""
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path, cache_path=tmp_path / "cache.jsonl"
        )
        assert runner._cache_key(self._pair(code_a="x")) != runner._cache_key(
            self._pair(code_a="y")
        )

    def test_corrupt_line_is_skipped(self, tmp_path):
        """A truncated line does not abort a resumable run."""
        cache = tmp_path / "cache.jsonl"
        cache.write_text(
            '{"key": "abc", "row": {"ast": 1.0}}\nnot json\n', encoding="utf-8"
        )
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path, cache_path=cache)
        assert runner._load_feature_cache() == {"abc": {"ast": 1.0}}

    def test_no_cache_path_is_a_no_op(self, tmp_path):
        """Without a cache path nothing is read or written."""
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        assert runner._load_feature_cache() == {}
        runner._append_feature_cache([("key", {"ast": 1.0})])
        assert list(tmp_path.glob("*.jsonl")) == []


class TestDatasetWeighting:
    """Equal weighting keeps small corpora relevant next to large ones."""

    def _pairs(self, dataset: str, count: int):
        """Build ``count`` labelled pairs belonging to one dataset."""
        from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair

        return [
            LabeledPair(
                f"{dataset}-{index}",
                "a",
                "b",
                index % 2,
                "python",
                {"dataset": dataset},
            )
            for index in range(count)
        ]

    def test_proportional_counts_every_pair_once(self, tmp_path):
        """The default mode passes no weights at all."""
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        assert runner._sample_weights(self._pairs("poolc", 10)) is None

    def test_equal_gives_each_dataset_the_same_total_weight(self, tmp_path):
        """A 10x larger corpus does not get 10x the influence."""
        runner = LearnedFusionTrainingRunner(
            output_dir=tmp_path, dataset_weighting="equal"
        )
        pairs = self._pairs("big", 100) + self._pairs("small", 10)
        weights = runner._sample_weights(pairs)

        assert weights is not None
        by_dataset: dict[str, float] = {}
        for pair, weight in zip(pairs, weights):
            name = pair.metadata["dataset"]
            by_dataset[name] = by_dataset.get(name, 0.0) + weight
        assert by_dataset["big"] == pytest.approx(by_dataset["small"])
        assert sum(weights) / len(weights) == pytest.approx(1.0)

    def test_rejects_unknown_mode(self, tmp_path):
        """A typo in the weighting mode fails fast."""
        with pytest.raises(ValueError):
            LearnedFusionTrainingRunner(output_dir=tmp_path, dataset_weighting="even")

    def test_weights_reach_the_estimator(self, tmp_path):
        """Sample weights actually change the fitted model."""
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        row_high = {name: 0.9 for name in runner.feature_names}
        row_low = {name: 0.1 for name in runner.feature_names}
        rows = [row_high, row_high, row_low, row_low]
        labels = [1, 1, 0, 0]

        plain = runner._fit_logistic(rows, labels)
        weighted = runner._fit_logistic(rows, labels, [1.0, 1.0, 50.0, 50.0])
        assert plain.intercept_[0] != weighted.intercept_[0]


class TestCvNotes:
    """The report states what the evaluation did and did not cover."""

    def test_notes_mention_excluded_poolc_negatives(self, tmp_path):
        """Positives-only PoolC is disclosed in the note."""
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        notes = runner._cv_notes(
            "grouped 5-fold", ["IR-Plag-Dataset", "poolc_600k_python"]
        )
        assert "grouped 5-fold" in notes
        assert "negatives excluded" in notes

    def test_notes_are_quiet_without_poolc(self, tmp_path):
        """Other corpora get the plain protocol note."""
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        assert "negatives excluded" not in runner._cv_notes(
            "leave-one-group-out", ["IR-Plag-Dataset", "conplag"]
        )


class TestExtractionProgress:
    """A long extraction must report progress while it is still running.

    ``compare_pairs`` is a single blocking call, so the runner has to hand it
    a callback. Without one the whole run is silent for its duration, and a
    post-hoc loop is worse than silence: every line prints at the end with the
    same elapsed time, which reads as "25 rows took 3 minutes".
    """

    def _stub_service(self, captured):
        """A service stub that records and exercises the progress callback."""
        import types

        class _StubService:
            def __init__(self):
                self.learned_scorer = None

            def compare_pairs(
                self, submissions=None, pairs=None, progress_callback=None
            ):
                captured["callback"] = progress_callback
                results = []
                for completed, spec in enumerate(pairs or [], start=1):
                    if progress_callback is not None:
                        progress_callback(
                            completed, len(pairs), spec["file_a"], spec["file_b"]
                        )
                    results.append(
                        types.SimpleNamespace(
                            file_a=spec["file_a"],
                            file_b=spec["file_b"],
                            features={"raw_score": 0.5},
                        )
                    )
                return results

        return _StubService

    def test_runner_hands_the_service_a_progress_callback(self, tmp_path, monkeypatch):
        """The callback reaches the service and the rows still come back."""
        captured = {}
        monkeypatch.setattr(
            "src.backend.application.services.batch_detection_service"
            ".BatchDetectionService",
            self._stub_service(captured),
        )
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        pairs = [
            LabeledPair(
                pair_id="p1", code_a="a = 1", code_b="a = 2", label=1, language="python"
            )
        ]

        rows = runner._extract_feature_rows(pairs)

        assert len(rows) == 1
        assert rows[0]["raw_score"] == pytest.approx(0.5)
        assert callable(captured["callback"])

    def test_progress_callback_logs_while_running(self, tmp_path, monkeypatch, caplog):
        """Invoking the callback emits a progress line, not silence."""
        import logging

        captured = {}
        monkeypatch.setattr(
            "src.backend.application.services.batch_detection_service"
            ".BatchDetectionService",
            self._stub_service(captured),
        )
        runner = LearnedFusionTrainingRunner(output_dir=tmp_path)
        pairs = [
            LabeledPair(
                pair_id="p1", code_a="a = 1", code_b="a = 2", label=1, language="python"
            )
        ]
        runner._extract_feature_rows(pairs)

        with caplog.at_level(logging.INFO):
            captured["callback"](1, 1, "pair_00000_a.py", "pair_00000_b.py")

        assert any(
            "Extracted 1/1 pair feature rows" in record.getMessage()
            for record in caplog.records
        )


class TestWrapperForwardsDatasetRoots:
    """The CLI wrapper must pass custom corpus roots through to the runner.

    The corpora are gitignored, so a training run may read them from a
    different checkout (or disk) than the one holding the code; a dropped
    argument here would silently fall back to the repo-relative defaults.
    """

    def test_forwards_dataset_roots(self, monkeypatch, tmp_path):
        """Explicit roots reach the runner unchanged."""
        captured = {}

        class _StubRunner:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def run(self, **kwargs):
                captured["run_kwargs"] = kwargs
                return "report"

        monkeypatch.setattr(
            "src.backend.benchmark.runners.learned_fusion_training_runner"
            ".LearnedFusionTrainingRunner",
            _StubRunner,
        )
        roots = [tmp_path / "corpora", tmp_path / "more"]
        result = run_learned_fusion_training(
            output_dir=tmp_path / "out", dataset_roots=roots
        )

        assert result == "report"
        assert captured["dataset_roots"] == roots

    def test_defaults_to_none_without_roots(self, monkeypatch, tmp_path):
        """No --dataset-roots leaves the runner on its own defaults."""
        captured = {}

        class _StubRunner:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def run(self, **kwargs):
                return "report"

        monkeypatch.setattr(
            "src.backend.benchmark.runners.learned_fusion_training_runner"
            ".LearnedFusionTrainingRunner",
            _StubRunner,
        )
        run_learned_fusion_training(output_dir=tmp_path / "out")

        assert captured["dataset_roots"] is None
