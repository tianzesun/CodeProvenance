"""Tests for the per-corpus ship/no-ship gate."""

from __future__ import annotations

import json
import os

import pytest

from src.backend.benchmark.gate import (
    SHIPPED_BASELINE,
    collect_scores,
    evaluate_gate,
    load_report_scores,
)


def test_gate_passes_when_every_corpus_is_level() -> None:
    """The shipped artifact itself must pass its own bar."""
    result = evaluate_gate(dict(SHIPPED_BASELINE))
    assert result.passed
    assert result.failed == []
    assert result.missing == []


def test_gate_fails_when_one_corpus_regresses() -> None:
    """A trade of one corpus for another is not a win."""
    candidate = dict(SHIPPED_BASELINE)
    candidate["conplag"] = 0.7809
    result = evaluate_gate(candidate)
    assert not result.passed
    assert result.failed == ["conplag"]
    assert "conplag" in result.format_table()


def test_gate_fails_when_a_corpus_is_missing() -> None:
    """An unmeasured corpus cannot be declared level."""
    candidate = {name: value for name, value in SHIPPED_BASELINE.items()}
    candidate.pop("kaggle_student_code")
    result = evaluate_gate(candidate)
    assert not result.passed
    assert result.missing == ["kaggle_student_code"]


def test_gate_accepts_equal_within_reported_precision() -> None:
    """0.813377 measured for a bar of 0.8134 must not fail on float noise."""
    result = evaluate_gate({"conplag": 0.813377}, baselines={"conplag": 0.8134})
    assert result.passed


def test_gate_tolerance_is_explicit() -> None:
    """A deliberate trade-off has to be declared, not inferred."""
    candidate = {"conplag": 0.8100}
    strict = evaluate_gate(candidate, baselines={"conplag": 0.8134})
    relaxed = evaluate_gate(candidate, baselines={"conplag": 0.8134}, tolerance=0.004)
    assert not strict.passed
    assert relaxed.passed


def test_gate_json_reports_every_corpus() -> None:
    """Machine consumers get the same rows as the table."""
    payload = evaluate_gate({"conplag": 0.5}).to_dict()
    assert payload["passed"] is False
    assert payload["criteria"].startswith("per-dataset AUC only")
    rows = {row["dataset"]: row for row in payload["rows"]}
    assert rows["conplag"]["candidate"] == 0.5
    assert rows["conplag"]["missing"] is False
    assert rows["kaggle_student_code"]["missing"] is True


def test_load_training_report_reads_per_dataset_auc(tmp_path) -> None:
    """The current training report shape is the primary format."""
    report = tmp_path / "learned_fusion_results.json"
    report.write_text(
        json.dumps(
            {
                "cv_auc": 0.9,
                "per_dataset_auc": {
                    "IR-Plag-Dataset": 0.70,
                    "conplag": 0.80,
                    "kaggle_student_code": 0.89,
                },
            }
        ),
        encoding="utf-8",
    )
    assert load_report_scores(report) == {
        "IR-Plag-Dataset": 0.70,
        "conplag": 0.80,
        "kaggle_student_code": 0.89,
    }


def test_load_training_report_reads_the_legacy_key(tmp_path) -> None:
    """Reports written before the rename still parse."""
    report = tmp_path / "legacy.json"
    report.write_text(
        json.dumps({"logo_per_dataset": {"IR-Plag-Dataset": 0.7021}}), encoding="utf-8"
    )
    assert load_report_scores(report) == {"IR-Plag-Dataset": 0.7021}


def test_load_engine_eval_report_reads_one_corpus(tmp_path) -> None:
    """engine-eval writes one file per corpus; the scorer name is selectable."""
    report = tmp_path / "ENGINE_EVAL_conplag_1.json"
    report.write_text(
        json.dumps(
            {
                "dataset_name": "conplag",
                "scorers": [
                    {"name": "fused", "available": True, "auc_roc": 0.81},
                    {"name": "jplag", "available": True, "auc_roc": 0.82},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert load_report_scores(report) == {"conplag": 0.81}
    assert load_report_scores(report, scorer="jplag") == {"conplag": 0.82}


def test_load_engine_eval_report_ignores_an_unavailable_scorer(tmp_path) -> None:
    """A missing tool must not be counted as a measurement."""
    report = tmp_path / "ENGINE_EVAL_conplag_1.json"
    report.write_text(
        json.dumps(
            {
                "dataset_name": "conplag",
                "scorers": [{"name": "fused", "available": False, "auc_roc": 0.0}],
            }
        ),
        encoding="utf-8",
    )
    assert load_report_scores(report) == {}


def test_collect_scores_keeps_the_newest_run_per_corpus(tmp_path) -> None:
    """A re-run of one corpus must supersede an older file, not tie with it."""
    old = tmp_path / "ENGINE_EVAL_conplag_old.json"
    new = tmp_path / "ENGINE_EVAL_conplag_new.json"
    other = tmp_path / "ENGINE_EVAL_IR-Plag-Dataset.json"

    def write(path, dataset, auc) -> None:
        path.write_text(
            json.dumps(
                {
                    "dataset_name": dataset,
                    "scorers": [{"name": "fused", "available": True, "auc_roc": auc}],
                }
            ),
            encoding="utf-8",
        )

    write(old, "conplag", 0.10)
    write(new, "conplag", 0.90)
    write(other, "IR-Plag-Dataset", 0.70)
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    os.utime(other, (1500, 1500))

    scores, used = collect_scores([tmp_path])
    assert scores == {"conplag": 0.90, "IR-Plag-Dataset": 0.70}
    assert new in used


def test_collect_scores_breaks_mtime_ties_by_timestamp_in_the_name(tmp_path) -> None:
    """Copying a report directory rewrites mtimes; the run name still orders it."""
    old = tmp_path / "ENGINE_EVAL_conplag_20261022_093000.json"
    new = tmp_path / "ENGINE_EVAL_conplag_20261022_113000.json"
    for path, auc in ((old, 0.10), (new, 0.90)):
        path.write_text(
            json.dumps(
                {
                    "dataset_name": "conplag",
                    "scorers": [{"name": "fused", "available": True, "auc_roc": auc}],
                }
            ),
            encoding="utf-8",
        )
    # `cp` gives every file the copy time, so mtimes no longer say anything.
    os.utime(old, (2000, 2000))
    os.utime(new, (2000, 2000))

    scores, used = collect_scores([tmp_path])
    assert scores == {"conplag": 0.90}
    assert used == [new]


def test_collect_scores_ignores_files_that_are_not_reports(tmp_path) -> None:
    """A stray JSON in the report directory must not break the gate."""
    (tmp_path / "notes.json").write_text(
        json.dumps({"hello": "world"}), encoding="utf-8"
    )
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    scores, used = collect_scores([tmp_path])
    assert scores == {}
    assert used == []


def test_gate_cli_exit_codes(tmp_path, capsys) -> None:
    """The CLI mirrors the verdict in its exit status."""
    from src.backend.benchmark import __main__ as cli

    good = tmp_path / "good.json"
    good.write_text(json.dumps({"per_dataset_auc": dict(SHIPPED_BASELINE)}), "utf-8")
    assert _run_cli(cli, ["fusion-gate", "--report", str(good)]) == 0

    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"per_dataset_auc": {"IR-Plag-Dataset": 0.1}}), encoding="utf-8"
    )
    assert _run_cli(cli, ["fusion-gate", "--report", str(bad)]) == 1


def test_gate_cli_uses_a_host_measured_baseline(tmp_path, capsys) -> None:
    """A bar measured on this host replaces the constant from another machine."""
    from src.backend.benchmark import __main__ as cli

    host = tmp_path / "host"
    host.mkdir()
    for dataset, auc in (
        ("IR-Plag-Dataset", 0.6184),
        ("conplag", 0.8134),
        # The dev machine measured 0.8833 for the same artifact.
        ("kaggle_student_code", 0.8898),
    ):
        (host / f"ENGINE_EVAL_{dataset}.json").write_text(
            json.dumps(
                {
                    "dataset_name": dataset,
                    "scorers": [{"name": "fused", "available": True, "auc_roc": auc}],
                }
            ),
            encoding="utf-8",
        )

    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "per_dataset_auc": {
                    "IR-Plag-Dataset": 0.62,
                    "conplag": 0.82,
                    "kaggle_student_code": 0.885,
                }
            }
        ),
        encoding="utf-8",
    )

    # 0.885 clears the constant bar (0.8833) but not this host's measurement
    # (0.8898), so the verdict must follow the baseline it was given.
    assert _run_cli(cli, ["fusion-gate", "--report", str(candidate)]) == 0
    assert (
        _run_cli(
            cli,
            [
                "fusion-gate",
                "--report",
                str(candidate),
                "--baseline-report",
                str(host),
            ],
        )
        == 1
    )
    assert "using the host value" in capsys.readouterr().out


def test_gate_cli_host_baseline_does_not_shrink_the_gate(tmp_path, capsys) -> None:
    """A host baseline for one corpus must not hide the other two."""
    from src.backend.benchmark import __main__ as cli

    host = tmp_path / "host"
    host.mkdir()
    (host / "ENGINE_EVAL_conplag.json").write_text(
        json.dumps(
            {
                "dataset_name": "conplag",
                "scorers": [{"name": "fused", "available": True, "auc_roc": 0.8134}],
            }
        ),
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps({"per_dataset_auc": {"conplag": 0.8134}}), encoding="utf-8"
    )

    assert (
        _run_cli(
            cli,
            [
                "fusion-gate",
                "--report",
                str(candidate),
                "--baseline-report",
                str(host),
            ],
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "no measurement for kaggle_student_code" in output


def test_gate_cli_rejects_an_empty_host_baseline(tmp_path) -> None:
    """An unreadable baseline must fail loudly, not fall back silently."""
    from src.backend.benchmark import __main__ as cli

    empty = tmp_path / "empty"
    empty.mkdir()
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"per_dataset_auc": dict(SHIPPED_BASELINE)}))

    with pytest.raises(SystemExit):
        _run_cli(
            cli,
            [
                "fusion-gate",
                "--report",
                str(candidate),
                "--baseline-report",
                str(empty),
            ],
        )


def test_gate_cli_refuses_to_judge_a_run_against_itself(tmp_path) -> None:
    """A baseline file that is also the candidate always passes; that is a bug."""
    from src.backend.benchmark import __main__ as cli

    report = tmp_path / "learned_fusion_report_1.json"
    report.write_text(json.dumps({"per_dataset_auc": dict(SHIPPED_BASELINE)}))
    with pytest.raises(SystemExit):
        _run_cli(
            cli,
            [
                "fusion-gate",
                "--report",
                str(report),
                "--baseline-report",
                str(report),
            ],
        )


def _run_cli(cli, argv: list[str]) -> int:
    """Run the benchmark CLI in-process with ``argv``."""
    import sys

    previous = sys.argv
    sys.argv = ["benchmark", *argv]
    try:
        return cli.main()
    finally:
        sys.argv = previous


@pytest.mark.parametrize("dataset", sorted(SHIPPED_BASELINE))
def test_baseline_covers_every_product_corpus(dataset: str) -> None:
    """The gate must not silently drop a corpus it was built for."""
    assert SHIPPED_BASELINE[dataset] > 0.5
