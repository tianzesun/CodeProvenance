"""Tests for the benchmark tribunal pipeline: execution engine, adapters, comparison, reports."""

import json
import tempfile
from pathlib import Path

import pytest

from src.backend.evaluation.dataset.ground_truth import (
    GroundTruthPair,
    EvaluationProtocol,
    DEFAULT_PROTOCOL,
    SyntheticDatasetGenerator,
    build_score_label_arrays,
)
from src.backend.evaluation.comparison_engine import (
    ToolMetrics,
    PairwiseSignificance,
    SignificanceMatrix,
    ToolRanking,
    build_significance_matrix,
    rank_tools,
    _cohens_d,
)
from src.backend.evaluation.ieee_report_generator import (
    BenchmarkReport,
    IEEEStyleReportGenerator,
    generate_benchmark_report,
)
from src.backend.evaluation.benchmark_tribunal import BenchmarkTribunal, TribunalResult
from src.backend.engines.execution.execution_engine import (
    ExecutionResult,
    DeterministicEnv,
)
from src.backend.engines.execution.adapter_layer import (
    ToolFinding,
    MossAdapter,
    JPlagAdapter,
    AdapterRegistry,
    adapt_tool_output,
)


class TestDeterministicEnv:
    def test_build_env_deterministic(self):
        env = DeterministicEnv(seed=42)
        built = env.build_env()
        assert built["PYTHONHASHSEED"] == "42"
        assert built["LANG"] == "C.UTF-8"

    def test_build_env_custom_seed(self):
        env = DeterministicEnv(seed=123)
        built = env.build_env()
        assert built["PYTHONHASHSEED"] == "123"

    def test_fingerprint_consistency(self, tmp_path):
        env = DeterministicEnv(seed=42)
        f1 = tmp_path / "a.py"
        f1.write_text("def foo(): pass")
        fp1 = env.compute_fingerprint(tmp_path)
        fp2 = env.compute_fingerprint(tmp_path)
        assert fp1 == fp2


class TestExecutionResult:
    def test_to_dict(self):
        result = ExecutionResult(
            tool_name="jplag",
            success=True,
            exit_code=0,
            stdout="done",
            stderr="",
            execution_time=1.5,
            parsed_pairs=[{"file1": "a.py", "file2": "b.py", "similarity": 0.8}],
        )
        d = result.to_dict()
        assert d["tool_name"] == "jplag"
        assert d["success"] is True
        assert d["num_pairs"] == 1
        assert d["execution_time"] == 1.5


class TestSyntheticDatasetGenerator:
    def test_generate_default(self):
        gen = SyntheticDatasetGenerator(seed=42)
        pairs = gen.generate()
        assert len(pairs) > 0
        assert any(p.label == 1 for p in pairs)
        assert any(p.label == 0 for p in pairs)

    def test_generate_custom_counts(self):
        gen = SyntheticDatasetGenerator(seed=42)
        pairs = gen.generate(
            num_type1=10, num_type2=10, num_type3=10,
            num_type4=5, num_non_clone=20,
        )
        assert len(pairs) == 55

    def test_clone_types_present(self):
        gen = SyntheticDatasetGenerator(seed=42)
        pairs = gen.generate(num_type1=5, num_type2=5, num_type3=5, num_type4=3, num_non_clone=10)
        clone_types = {p.clone_type for p in pairs if p.clone_type}
        assert 1 in clone_types
        assert 2 in clone_types
        assert 3 in clone_types
        assert 4 in clone_types

    def test_type1_identical_code(self):
        gen = SyntheticDatasetGenerator(seed=99)
        all_pairs = gen.generate(num_type1=3, num_type2=0, num_type3=0, num_type4=0, num_non_clone=0)
        for p in all_pairs:
            assert p.code_a == p.code_b
            assert p.clone_type == 1

    def test_type2_renamed_variables(self):
        gen = SyntheticDatasetGenerator(seed=99)
        all_pairs = gen.generate(num_type1=20, num_type2=3, num_type3=0, num_type4=0, num_non_clone=0)
        type2_pairs = [p for p in all_pairs if p.clone_type == 2]
        assert len(type2_pairs) == 3
        for p in type2_pairs:
            assert p.clone_type == 2
            tokens_a = set(p.code_a.split())
            tokens_b = set(p.code_b.split())
            assert len(tokens_a) > 0
            assert len(tokens_b) > 0


class TestBuildScoreLabelArrays:
    def test_basic_alignment(self):
        tool_findings = {
            "tool_a": [
                {"file1": "a.py", "file2": "b.py", "similarity": 0.9},
                {"file1": "c.py", "file2": "d.py", "similarity": 0.2},
            ],
            "tool_b": [
                {"file1": "a.py", "file2": "b.py", "similarity": 0.8},
                {"file1": "c.py", "file2": "d.py", "similarity": 0.3},
            ],
        }
        ground_truth = {
            ("a.py", "b.py"): 1,
            ("c.py", "d.py"): 0,
        }
        scores, labels = build_score_label_arrays(tool_findings, ground_truth)
        assert len(labels) == 2
        assert labels == [1, 0]
        assert scores["tool_a"] == [0.9, 0.2]
        assert scores["tool_b"] == [0.8, 0.3]

    def test_missing_pairs_default_to_zero(self):
        tool_findings = {
            "tool_a": [{"file1": "a.py", "file2": "b.py", "similarity": 0.9}],
        }
        ground_truth = {
            ("a.py", "b.py"): 1,
            ("c.py", "d.py"): 0,
        }
        scores, labels = build_score_label_arrays(tool_findings, ground_truth)
        assert len(labels) == 2
        assert scores["tool_a"] == [0.9, 0.0]


class TestComparisonEngine:
    @pytest.fixture
    def tool_scores(self):
        return {
            "good_tool": [0.9, 0.85, 0.92, 0.88, 0.91, 0.1, 0.05, 0.15, 0.08, 0.12],
            "bad_tool": [0.6, 0.55, 0.65, 0.58, 0.62, 0.4, 0.35, 0.45, 0.38, 0.42],
        }

    @pytest.fixture
    def labels(self):
        return [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]

    def test_rank_tools_returns_ranking(self, tool_scores, labels):
        ranking = rank_tools(tool_scores, labels)
        assert isinstance(ranking, ToolRanking)
        assert len(ranking.rankings) == 2
        assert ranking.rankings[0].rank_by_f1 == 1

    def test_best_tool_is_correct(self, tool_scores, labels):
        ranking = rank_tools(tool_scores, labels)
        assert ranking.best_tool == "good_tool"

    def test_significance_matrix_built(self, tool_scores, labels):
        ranking = rank_tools(tool_scores, labels)
        sig = ranking.significance_matrix
        assert len(sig.tools) == 2
        comp = sig.get("good_tool", "bad_tool")
        assert comp is not None
        assert comp.tool_a in ("good_tool", "bad_tool")

    def test_cohens_d_basic(self):
        d = _cohens_d([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])
        assert abs(d) > 2.0

    def test_cohens_d_identical(self):
        d = _cohens_d([1, 2, 3], [1, 2, 3])
        assert d == 0.0

    def test_tool_metrics_to_dict(self):
        m = ToolMetrics(
            tool_name="test",
            precision=0.8,
            recall=0.75,
            f1=0.77,
            accuracy=0.85,
            tp=8, fp=2, tn=7, fn=3,
            rank_by_f1=1,
        )
        d = m.to_dict()
        assert d["tool"] == "test"
        assert d["precision"] == 0.8
        assert d["rank"] == 1


class TestIEEEStyleReportGenerator:
    @pytest.fixture
    def sample_report(self, tmp_path):
        from src.backend.evaluation.comparison_engine import rank_tools

        tool_scores = {
            "moss": [0.9, 0.85, 0.1, 0.05, 0.92, 0.08],
            "jplag": [0.88, 0.82, 0.15, 0.1, 0.90, 0.12],
            "ours": [0.95, 0.93, 0.05, 0.03, 0.96, 0.04],
        }
        labels = [1, 1, 0, 0, 1, 0]

        ranking = rank_tools(tool_scores, labels)

        return BenchmarkReport(
            report_id="test_001",
            timestamp="2026-04-02T12:00:00",
            dataset_name="synthetic",
            dataset_size=6,
            num_tools=3,
            threshold=0.5,
            ranking=ranking,
            tool_scores=tool_scores,
            labels=labels,
        )

    def test_generate_html(self, sample_report):
        gen = IEEEStyleReportGenerator()
        html = gen.generate_html(sample_report)
        assert "<!DOCTYPE html>" in html
        assert "moss" in html
        assert "jplag" in html
        assert "ours" in html
        assert sample_report.reproducibility_hash in html

    def test_generate_json(self, sample_report):
        gen = IEEEStyleReportGenerator()
        json_str = gen.generate_json(sample_report)
        data = json.loads(json_str)
        assert data["report_id"] == "test_001"
        assert data["dataset"]["name"] == "synthetic"
        assert len(data["ranking"]["rankings"]) == 3

    def test_save_html(self, sample_report, tmp_path):
        gen = IEEEStyleReportGenerator()
        output = tmp_path / "report.html"
        gen.save_html(sample_report, output)
        assert output.exists()
        assert output.read_text().startswith("<!DOCTYPE html>")

    def test_save_json(self, sample_report, tmp_path):
        gen = IEEEStyleReportGenerator()
        output = tmp_path / "report.json"
        gen.save_json(sample_report, output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["report_id"] == "test_001"


class TestBenchmarkTribunal:
    def test_run_with_synthetic_data(self, tmp_path):
        output_dir = tmp_path / "reports"
        tribunal = BenchmarkTribunal(
            language="python",
            tools=["ours"],
            output_dir=output_dir,
            generate_synthetic=True,
            synthetic_config={
                "type1": 10,
                "type2": 10,
                "type3": 10,
                "type4": 5,
                "non_clone": 20,
            },
            seed=42,
        )
        result = tribunal.run()
        assert isinstance(result, TribunalResult)
        assert result.report.num_tools >= 1
        assert result.report.dataset_size == 55
        assert output_dir.exists()
        assert (output_dir / "report.html").exists()
        assert (output_dir / "report.json").exists()

    def test_run_with_precomputed_scores(self, tmp_path):
        output_dir = tmp_path / "reports"
        tribunal = BenchmarkTribunal(
            output_dir=output_dir,
            protocol=EvaluationProtocol(
                name="test",
                description="Test protocol",
                threshold=0.5,
                n_bootstrap=100,
            ),
        )

        tool_scores = {
            "moss": [0.55, 0.52, 0.58, 0.45, 0.48, 0.42, 0.51, 0.47, 0.53, 0.44],
            "jplag": [0.62, 0.58, 0.65, 0.38, 0.42, 0.35, 0.60, 0.40, 0.55, 0.37],
            "ours": [0.95, 0.93, 0.96, 0.94, 0.92, 0.05, 0.03, 0.04, 0.02, 0.06],
        }
        labels = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]

        result = tribunal.run_with_precomputed_scores(tool_scores, labels, "test_dataset")
        assert isinstance(result, TribunalResult)
        assert result.report.ranking.best_tool == "ours"
        assert result.report.dataset_size == 10
        assert result.report.num_tools == 3
        assert (output_dir / "report.html").exists()

    def test_summary_output(self, tmp_path):
        tribunal = BenchmarkTribunal(
            output_dir=tmp_path,
            generate_synthetic=True,
            synthetic_config={"type1": 5, "type2": 5, "non_clone": 10},
            seed=42,
        )
        result = tribunal.run()
        summary = result.summary()
        assert "BENCHMARK TRIBUNAL RESULT" in summary
        assert "Tool Rankings" in summary or "RANKING" in summary


class TestAdapterRegistry:
    def test_available_tools(self):
        tools = AdapterRegistry.available_tools()
        assert "moss" in tools
        assert "jplag" in tools
        assert "dolos" in tools
        assert "nicad" in tools

    def test_get_adapter_moss(self):
        adapter = AdapterRegistry.get_adapter("moss")
        assert isinstance(adapter, MossAdapter)

    def test_get_adapter_jplag(self):
        adapter = AdapterRegistry.get_adapter("jplag")
        assert isinstance(adapter, JPlagAdapter)

    def test_get_adapter_unknown_raises(self):
        with pytest.raises(ValueError):
            AdapterRegistry.get_adapter("unknown_tool")


class TestEvaluationProtocol:
    def test_default_protocol(self):
        assert DEFAULT_PROTOCOL.threshold == 0.5
        assert DEFAULT_PROTOCOL.ci_level == 0.95
        assert DEFAULT_PROTOCOL.n_bootstrap == 1000
        assert DEFAULT_PROTOCOL.clone_types == [1, 2, 3, 4]

    def test_custom_protocol(self):
        proto = EvaluationProtocol(
            name="strict",
            description="Strict evaluation",
            threshold=0.7,
            ci_level=0.99,
            n_bootstrap=5000,
        )
        assert proto.threshold == 0.7
        assert proto.ci_level == 0.99
        d = proto.to_dict()
        assert d["name"] == "strict"


class TestEndToEnd:
    """Full end-to-end test mimicking real tribunal output."""

    def test_full_tribunal_produces_expected_table(self, tmp_path):
        tribunal = BenchmarkTribunal(
            output_dir=tmp_path,
            tools=["ours"],
            generate_synthetic=True,
            synthetic_config={
                "type1": 15,
                "type2": 15,
                "type3": 15,
                "type4": 8,
                "non_clone": 30,
            },
            seed=42,
        )
        result = tribunal.run()

        assert result.report.dataset_size == 83
        assert len(result.report.ranking.rankings) >= 1

        best = result.report.ranking.rankings[0]
        assert best.f1 > 0
        assert best.f1_ci is not None
        assert best.f1_ci["ci_lower"] <= best.f1 <= best.f1_ci["ci_upper"]

        html = (tmp_path / "report.html").read_text()
        assert "Benchmark Evaluation Report" in html
        assert "Tool Rankings" in html
        assert "Reproducibility" in html

        json_data = json.loads((tmp_path / "report.json").read_text())
        assert "ranking" in json_data
        assert "reproducibility_hash" in json_data
        assert len(json_data["ranking"]["rankings"]) >= 1
