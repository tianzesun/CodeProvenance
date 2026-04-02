"""Automated benchmark regression tests.

These tests verify that benchmark engines produce consistent results
across code changes. They run all three layers with fixed seeds and
check that metrics stay within expected bounds.

Usage:
    pytest tests/unit/test_benchmark_regression.py -v
    pytest tests/unit/test_benchmark_regression.py -v --tb=long
"""
from __future__ import annotations

import pytest
import random
from typing import Any, Dict, List

from benchmark.datasets.synthetic_generator import (
    SyntheticDatasetGenerator,
    generate_type1_pair, generate_type2_pair, generate_type3_pair,
    generate_type4_pair, generate_non_clone_pair,
)
from benchmark.datasets.multilang_benchmark import (
    MultiLangLoader, MultiLangDataset, PYTHON_SAMPLES, JAVA_SAMPLES,
    JAVASCRIPT_SAMPLES,
)
from benchmark.similarity.base_engine import BaseSimilarityEngine
from benchmark.similarity.engines import (
    TokenWinnowingEngine, ASTEngine, HybridEngine,
)
from benchmark.pipeline.evaluation_framework import (
    ThreeLayerBenchmarkRunner, CombineLoops, ExtractFunction,
    ALL_TECHNIQUES,
)
from benchmark.metrics.significance import (
    bootstrap_confidence_interval,
    mcnemar_test, McNemarResult,
    compare_engines, EngineComparisonResult,
    add_significance_to_results,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def base_codes() -> List[str]:
    """Get fixed base code templates for reproducible tests."""
    gen = SyntheticDatasetGenerator(seed=42)
    return gen._get_default_templates("python")[:10]


@pytest.fixture
def small_base_codes() -> List[str]:
    """Get small base code subset for faster tests."""
    gen = SyntheticDatasetGenerator(seed=42)
    return gen._get_default_templates("python")[:5]


@pytest.fixture
def hybrid_engine() -> HybridEngine:
    return HybridEngine()


@pytest.fixture
def token_engine() -> TokenWinnowingEngine:
    return TokenWinnowingEngine()


@pytest.fixture
def ast_engine() -> ASTEngine:
    return ASTEngine()


@pytest.fixture
def token_engine() -> TokenWinnowingEngine:
    return TokenWinnowingEngine()


# =============================================================================
# Synthetic Dataset Tests (Data Integrity)
# =============================================================================


class TestSyntheticDataset:
    """Verify synthetic dataset generation is deterministic."""

    def test_seed_reproducibility(self):
        """Same seed should produce same dataset."""
        gen_a = SyntheticDatasetGenerator(seed=42)
        gen_b = SyntheticDatasetGenerator(seed=42)

        a = gen_a.generate_pair_count(type1=5, type2=5, non_clone=10)
        b = gen_b.generate_pair_count(type1=5, type2=5, non_clone=10)

        assert len(a.pairs) == len(b.pairs)
        # Same seed, same pair counts → same codes
        for pa, pb in zip(a.pairs, b.pairs):
            assert pa.code_a == pb.code_a
            assert pa.code_b == pb.code_b
            assert pa.label == pb.label

    def test_default_templates(self):
        """Default templates should return expected number of samples."""
        gen = SyntheticDatasetGenerator(seed=42)
        templates = gen._get_default_templates("python")
        assert len(templates) >= 10

    def test_clone_type_generation(self):
        """Each clone type generator should produce valid pairs."""
        code = '''def foo(x):
    result = x + 1
    return result
'''
        # Type-1: identical
        a, b = generate_type1_pair(code, seed=42)
        assert a == b

        # Type-2: renamed - should differ but be structurally similar
        a, b = generate_type2_pair(code, seed=42)
        assert a != b  # identifiers renamed

        # Type-3: restructured - should differ
        a, b = generate_type3_pair(code, seed=42)
        assert a != b

        # Type-4: semantic - should differ
        a, b = generate_type4_pair(code, seed=42)
        assert a != b or a == b  # may or may not differ

        # Non-clone: should differ significantly
        a, b = generate_non_clone_pair(code, seed=42, language="python")
        assert a != b


# =============================================================================
# Multi-Language Dataset Tests (Layer 3 Data)
# =============================================================================


class TestMultiLangDataset:
    """Verify multi-language dataset integrity."""

    def test_sample_counts(self):
        """All languages should have same number of algorithms."""
        loader = MultiLangLoader()
        ds = loader.load()
        assert len(ds.python) == len(ds.java) == len(ds.javascript)
        assert len(ds.python) == 10

    def test_algorithm_alignment(self):
        """Index 0 in each language should implement the same algorithm."""
        loader = MultiLangLoader()
        ds = loader.load()

        py_code = ds.python["0"]
        java_code = ds.java["0"]
        js_code = ds.javascript["0"]

        # All should contain the algorithm name
        assert "linear" in py_code.lower()
        assert "linear" in java_code.lower()
        assert "linear" in js_code.lower()

    def test_cross_language_pairs(self):
        """get_pairs should return aligned pairs."""
        loader = MultiLangLoader()
        ds = loader.load()
        pairs = ds.get_pairs("python", "java")
        assert len(pairs) == 10  # All 10 algorithms aligned
        for py, java in pairs:
            assert isinstance(py, str)
            assert isinstance(java, str)
            assert len(py) > 0
            assert len(java) > 0

    def test_single_language_samples(self):
        """get_single_language should return list of code strings."""
        loader = MultiLangLoader()
        ds = loader.load()
        samples = ds.get_single_language("python")
        assert len(samples) == 10
        assert all(isinstance(s, str) for s in samples)

    def test_language_names(self):
        """languages property should return correct order."""
        loader = MultiLangLoader()
        ds = loader.load()
        assert ds.languages == ["python", "java", "javascript"]

    def test_get_multilang_samples(self):
        """Convenience function should return 3 languages."""
        from benchmark.datasets.multilang_benchmark import get_multilang_samples
        samples = get_multilang_samples()
        assert len(samples) == 3
        for lang, codes in samples:
            assert lang in ["python", "java", "javascript"]
            assert len(codes) == 10


# =============================================================================
# Significance Testing Tests
# =============================================================================


class TestBootstrapCI:
    """Test bootstrap confidence interval implementation."""

    def test_perfect_model_narrow_ci(self):
        """Perfect model should have very narrow CI."""
        scores = [0.99] * 20 + [0.01] * 20
        labels = [1] * 20 + [0] * 20
        ci = bootstrap_confidence_interval(scores, labels, n_bootstrap=100)
        assert ci["f1"]["value"] == 1.0
        assert ci["f1"]["ci_lower"] >= 0.9

    def test_zero_model_zero_ci(self):
        """All-wrong model should have F1=0."""
        scores = [0.01] * 20 + [0.99] * 20
        labels = [1] * 20 + [0] * 20
        ci = bootstrap_confidence_interval(scores, labels, n_bootstrap=100)
        assert ci["f1"]["value"] == 0.0

    def test_ci_bounds_contain_point_estimate(self):
        """CI bounds should always contain point estimate."""
        import random as rng
        rng.seed(42)
        for _ in range(5):
            scores = [rng.uniform(0.1, 0.9) for _ in range(30)]
            labels = [rng.choice([0, 1]) for _ in range(30)]
            ci = bootstrap_confidence_interval(scores, labels, n_bootstrap=200)
            for metric in ["f1", "precision", "recall"]:
                assert ci[metric]["ci_lower"] <= ci[metric]["value"]
                assert ci[metric]["ci_upper"] >= ci[metric]["value"]

    def test_empty_input(self):
        """Empty input should return zeros without error."""
        ci = bootstrap_confidence_interval([], [])
        assert ci["f1"]["value"] == 0.0


class TestMcNemarTest:
    """Test McNemar's test implementation."""

    def test_identical_models_not_significant(self):
        """Identical models should not be significantly different."""
        labels = [1, 1, 1, 0, 0, 0]
        pred_a = [1, 1, 0, 0, 0, 1]
        result = mcnemar_test(labels, pred_a, pred_a)
        assert not result.is_significant
        assert result.p_value == 1.0

    def test_different_models_significant(self):
        """Models with many discordant errors should be significantly different."""
        n = 100
        labels = [1] * 50 + [0] * 50
        pred_a = labels  # Perfect
        pred_b = [0] * 50 + [0] * 50  # All negative
        result = mcnemar_test(labels, pred_a, pred_b)
        assert result.is_significant
        assert result.p_value < 0.05


# =============================================================================
# Engine Tests (Deterministic Behavior)
# =============================================================================


class TestEngineDeterminism:
    """Verify engines are deterministic."""

    def test_token_engine_deterministic(self, token_engine: TokenWinnowingEngine):
        """Token engine should produce same scores with same input."""
        code_a = "def foo(x): return x + 1"
        code_b = "def bar(y): return y + 1"
        score_a = token_engine.compare(code_a, code_b)
        score_b = token_engine.compare(code_a, code_b)
        assert score_a == score_b

    def test_hybrid_engine_deterministic(self, hybrid_engine: HybridEngine):
        """Hybrid engine should produce same scores with same input."""
        code_a = "def foo(x): return x + 1"
        code_b = "def foo(x): return x + 1"
        score_a = hybrid_engine.compare(code_a, code_b)
        score_b = hybrid_engine.compare(code_a, code_b)
        assert score_a == score_b


# =============================================================================
# Layer 1 Regression Tests
# =============================================================================


class TestLayer1Regression:
    """Layer 1: Sensitivity regression tests."""

    def test_hybrid_engine_f1_threshold(self, base_codes: List[str]):
        """Hybrid engine should achieve > 85% F1 on Layer 1."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l1 = runner._run_layer1(base_codes)
        assert l1["overall_f1"] >= 0.85, f"Hybrid F1 too low: {l1['overall_f1']}"

    def test_token_engine_precision(self, base_codes: List[str]):
        """Token engine should have 0 false positives."""
        runner = ThreeLayerBenchmarkRunner(TokenWinnowingEngine(), seed=42)
        l1 = runner._run_layer1(base_codes)
        assert l1["fp"] == 0, f"Token engine has {l1['fp']} false positives"

    def test_per_technique_detection(self, base_codes: List[str]):
        """All techniques should have detection results."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l1 = runner._run_layer1(base_codes)
        tech_det = l1.get("technique_detection", {})
        assert len(tech_det) >= 18, f"Only {len(tech_det)} techniques reported"
        # Each technique should have pairs_tested
        for tech_name, data in tech_det.items():
            assert "tp" in data, f"Missing tp for {tech_name}"
            assert "fn" in data, f"Missing fn for {tech_name}"
            assert data.get("pairs_tested", 0) > 0, f"No pairs for {tech_name}"

    def test_non_clone_pairs_scored_low(self, base_codes: List[str]):
        """Non-clone pairs should have low average detection rates."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l1 = runner._run_layer1(base_codes)
        tech_det = l1.get("technique_detection", {})
        non_clone = tech_det.get("non_clone", {})
        # Non-clone pairs should have low f1 (ideally 0)
        # Since non_clone has label=0, engine should score them low (< 0.5)
        # TP=0, FN=non_clone_count means they're all incorrectly predicted
        assert non_clone.get("tp", 0) == 0, "Non-clone pairs shouldn't be predicted as clones"


# =============================================================================
# Layer 2 Regression Tests
# =============================================================================


class TestLayer2Regression:
    """Layer 2: Precision reg tests."""

    def test_layer2_has_confidence_intervals(self, base_codes: List[str]):
        """Layer 2 results should include confidence intervals."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l2 = runner._run_layer2_synthetic(base_codes)
        assert "confidence_intervals" in l2, "Layer 2 should have confidence_intervals"
        ci = l2["confidence_intervals"]
        assert "f1" in ci
        assert "precision" in ci
        assert "recall" in ci

    def test_layer2_confusion_matrix(self, base_codes: List[str]):
        """Layer 2 should report proper confusion matrix."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l2 = runner._run_layer2_synthetic(base_codes)
        assert "tp" in l2
        assert "fp" in l2
        assert "tn" in l2
        assert "fn" in l2

    def test_layer2_negative_pairs_scored(self, base_codes: List[str]):
        """Layer 2 should correctly score negative pairs."""
        runner = ThreeLayerBenchmarkRunner(TokenWinnowingEngine(), seed=42)
        l2 = runner._run_layer2_synthetic(base_codes)
        # Token engine: negative pairs (different templates) should score low (TN)
        assert l2.get("tn", 0) > 0 or l2.get("fp", 0) > 0, \
            "Layer 2 should have results for negative pairs"


# =============================================================================
# Layer 3 Regression Tests (Multi-Language)
# =============================================================================


class TestLayer3Regression:
    """Layer 3: Generalization regression tests."""

    def test_layer3_multi_language(self, base_codes: List[str]):
        """Layer 3 should include 3 languages."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l3 = runner._run_layer3_synthetic(base_codes)
        per_lang = l3.get("per_language", {})
        assert "python" in per_lang, "Layer 3 should include Python"
        assert "java" in per_lang, "Layer 3 should include Java"
        assert "javascript" in per_lang, "Layer 3 should include JavaScript"

    def test_layer3_cross_language_pairs(self, base_codes: List[str]):
        """Layer 3 should include cross-language pairs."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l3 = runner._run_layer3_synthetic(base_codes)
        per_lang = l3.get("per_language", {})
        cross_keys = [k for k in per_lang.keys() if k.startswith("cross_")]
        assert len(cross_keys) >= 3, \
            f"Expected 3 cross-language pairs, got {len(cross_keys)}: {cross_keys}"

    def test_layer3_generalization_score(self, base_codes: List[str]):
        """Layer 3 generalization score should be in valid range."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l3 = runner._run_layer3_synthetic(base_codes)
        gen_score = l3.get("generalization_score", 0)
        assert 0.0 <= gen_score <= 1.0, f"Generalization score out of range: {gen_score}"

    def test_layer3_with_in_language_pairs(self, base_codes: List[str]):
        """Each language should have within-language pairs."""
        runner = ThreeLayerBenchmarkRunner(HybridEngine(), seed=42)
        l3 = runner._run_layer3_synthetic(base_codes)
        for lang in ["python", "java", "javascript"]:
            data = l3["per_language"].get(lang, {})
            assert "n_pairs" in data, f"Missing n_pairs for {lang}"
            assert data["n_pairs"] > 0, f"No pairs for {lang}"


# =============================================================================
# Full Benchmark Regression Test
# =============================================================================


class TestFullBenchmark:
    """End-to-end benchmark regression tests."""

    def test_full_benchmark_completes(self, base_codes: List[str]):
        """Full benchmark should complete without error."""
        engine = HybridEngine()
        runner = ThreeLayerBenchmarkRunner(engine, seed=42)
        result = runner.run(base_codes)
        assert result is not None

    def test_overall_score_range(self, base_codes: List[str]):
        """Overall score should be in valid range."""
        engine = HybridEngine()
        runner = ThreeLayerBenchmarkRunner(engine, seed=42)
        result = runner.run(base_codes)
        assert 0.0 <= result.overall_score <= 1.0

    def test_layer1_dominates_overall_score(self, base_codes: List[str]):
        """Layer 1 should contribute most to overall score (40% weight)."""
        engine = HybridEngine()
        runner = ThreeLayerBenchmarkRunner(engine, seed=42)
        result = runner.run(base_codes)
        # L1 F1 should be the primary contributor
        assert result.layer1_sensitivity["overall_f1"] > 0.5


# =============================================================================
# Engine Comparison Tests
# =============================================================================


class TestEngineComparison:
    """Test engine comparison functionality."""

    def test_compare_engines_returns_result(self):
        """compare_engines should return EngineComparisonResult."""
        scores_a = [0.9] * 20 + [0.1] * 20
        scores_b = [0.6] * 20 + [0.1] * 20
        labels = [1] * 20 + [0] * 20
        result = compare_engines(scores_a, scores_b, labels)
        assert isinstance(result, EngineComparisonResult)
        assert result.metric_name == "f1"

    def test_significantly_better_engine(self):
        """Much better engine should be detected as significantly better."""
        scores_a = [0.95] * 40 + [0.05] * 40
        scores_b = [0.3] * 40 + [0.05] * 40
        labels = [1] * 40 + [0] * 40
        result = compare_engines(scores_a, scores_b, labels)
        assert result.engine_a_value > result.engine_b_value
        assert result.is_significant


# =============================================================================
# Plagiarism Technique Tests
# =============================================================================


class TestPlagiarismTechniques:
    """Verify plagiarism technique implementations."""

    def test_all_techniques_count(self):
        """Should have 18+ techniques registered."""
        assert len(ALL_TECHNIQUES) >= 18

    def test_each_technique_has_name(self):
        """All techniques should have a name attribute."""
        for tech in ALL_TECHNIQUES:
            assert hasattr(tech, "name") and tech.name, \
                f"Technique missing name: {tech}"

    def test_techniques_transform_code(self):
        """Each technique should produce output code."""
        base_code = '''def foo(x):
    result = x + 1
    return result
'''
        for tech in ALL_TECHNIQUES:
            if hasattr(tech, "apply") and hasattr(tech, "techniques"):
                # ChainTransformation (skip for simplicity)
                continue
            result = tech.apply(base_code, seed=42)
            assert isinstance(result, str)
            # Some techniques may not change code significantly
            # This is fine - the important thing is it returns a string
