"""Class-level evaluation runner: loading, metrics and reporting."""

from src.backend.benchmark.runners import class_evaluation_runner as runner


def _class():
    return runner.ClassSet(
        name="toy",
        files={"a.py": "x", "b.py": "y", "c.py": "z", "d.py": "w"},
        labels={("a.py", "b.py"): 1, ("a.py", "c.py"): 0},
    )


def test_flag_rate_counts_every_pair_but_recall_only_labelled_ones() -> None:
    scores = {
        ("a.py", "b.py"): 0.96,  # labelled copy
        ("a.py", "c.py"): 0.80,  # labelled innocent look-alike
        ("a.py", "d.py"): 0.10,
        ("b.py", "c.py"): 0.20,
        ("b.py", "d.py"): 0.30,
        ("c.py", "d.py"): 0.40,
    }

    result = runner.evaluate_class(_class(), scores, common_code_lines=2)

    mid = result.at_threshold["0.75"]
    assert mid["flagged"] == 2 and mid["flag_rate"] == round(2 / 6, 4)
    assert mid["recall"] == 1.0 and mid["hard_negative_rate"] == 1.0
    assert result.at_threshold["0.95"]["hard_negative_rate"] == 0.0
    assert result.auc == 1.0
    assert result.common_code_lines == 2


def test_auc_needs_both_labels() -> None:
    assert runner._auc([(1, 0.9)]) is None
    assert runner._auc([(1, 0.5), (0, 0.5)]) == 0.5


def test_loaders_read_the_bundled_datasets(tmp_path) -> None:
    kaggle = tmp_path / "kaggle_student_code"
    kaggle.mkdir()
    for name in ("submission1.py", "submission2.py", "submission3.py"):
        (kaggle / name).write_text("print(1)\n")
    (kaggle / "cheating_dataset.csv").write_text(
        "File_1,File_2,Label\nsubmission2.py,submission1.py,1\nsubmission1.py,missing.py,0\n"
    )
    case = tmp_path / "IR-Plag-Dataset" / "case-01"
    for folder in ("original", "plagiarized/L1/01", "non-plagiarized/01"):
        (case / folder).mkdir(parents=True)
        (case / folder / "A.java").write_text("class A {}\n")

    (kaggle_set,) = list(runner.load_kaggle(tmp_path))
    (ir_set,) = list(runner.load_irplag(tmp_path))

    assert kaggle_set.labels == {("submission1.py", "submission2.py"): 1}
    assert len(kaggle_set.files) == 3
    assert sorted(ir_set.labels.values()) == [0, 1]


def test_the_report_renders_a_row_per_class() -> None:
    result = runner.evaluate_class(
        _class(), {("a.py", "b.py"): 0.9, ("a.py", "c.py"): 0.1}
    )
    from dataclasses import asdict

    text = runner.render_markdown(
        {"run_id": "CLASS_EVAL_x", "runtime_seconds": 1, "classes": [asdict(result)]}
    )

    assert "| toy | 4 | 2 |" in text
    assert f"Recall @{runner.REVIEW_MIN:.2f}" in text
    assert f"Recall @{runner.HIGH_MIN:.2f}" in text


def test_reports_at_the_review_policy_bands_and_earlier_cut_offs() -> None:
    from src.backend.engines.scoring.review_policy import BAND_THRESHOLDS

    default = BAND_THRESHOLDS["default"]
    result = runner.evaluate_class(_class(), {("a.py", "b.py"): 0.9})

    for cut_off in (default["review_min"], default["high_min"], 0.75, 0.95):
        assert f"{cut_off:.2f}" in result.at_threshold


def test_labelled_pair_rows_keep_the_engine_breakdown() -> None:
    scores = {("a.py", "b.py"): 0.9, ("b.py", "c.py"): 0.2}
    details = {
        ("a.py", "b.py"): {
            "features": {"ast": 0.8},
            "contributions": {"ast": 0.4},
            "review_hold": None,
        }
    }

    rows = runner.labelled_pair_rows(_class(), scores, details)

    # ("a.py", "c.py") is labelled but unscored; ("b.py", "c.py") is unlabelled.
    assert rows == [
        {
            "class": "toy",
            "file_a": "a.py",
            "file_b": "b.py",
            "label": 1,
            "score": 0.9,
            "features": {"ast": 0.8},
            "contributions": {"ast": 0.4},
            "review_hold": None,
        }
    ]


def test_conplag_groups_submissions_by_problem(tmp_path) -> None:
    versions = tmp_path / "conplag" / "versions"
    for sub1, sub2 in (("aaa", "bbb"), ("aaa", "ccc"), ("ddd", "eee"), ("fff", "ggg")):
        pair_dir = versions / "version_1" / f"{sub1}_{sub2}"
        pair_dir.mkdir(parents=True)
        (pair_dir / f"{sub1}.java").write_text(f"class {sub1.upper()} {{}}\n")
        if sub2 != "ggg":  # one pair is missing a file and is skipped
            (pair_dir / f"{sub2}.java").write_text(f"class {sub2.upper()} {{}}\n")
    (versions / "labels.csv").write_text(
        "sub1,sub2,problem,verdict\n"
        "aaa,bbb,p1,1\n"
        "aaa,ccc,p1,0\n"
        "ddd,eee,p2,0\n"
        "fff,ggg,p2,1\n"
    )

    p1, p2 = list(runner.load_conplag(tmp_path))

    assert p1.name == "conplag/p1"
    assert sorted(p1.files) == ["aaa.java", "bbb.java", "ccc.java"]
    assert p1.labels == {("aaa.java", "bbb.java"): 1, ("aaa.java", "ccc.java"): 0}
    assert p1.files["aaa.java"] == "class AAA {}\n"
    assert sorted(p2.files) == ["ddd.java", "eee.java"]
    assert p2.labels == {("ddd.java", "eee.java"): 0}
