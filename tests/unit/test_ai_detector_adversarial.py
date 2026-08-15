"""Adversarial-resistance tests for the AI detector heuristic engine.

These tests document how the **live heuristic path** (``AIDetectionEngine``,
the default engine) responds to realistic evasion attempts by a credulous
humanizer:

- **Comment / docstring stripping** — the pattern library leans on templated
  LLM comments and Google/Sphinx docstrings, so removing them should collapse
  the docstring-density signal and shrink the fingerprint signal.
- **Whitespace regularization** — the rhythm signal measures blank-line
  regularity, so collapsing blank lines should zero it.
- **Identifier paraphrase** — renaming generic AI names (`process_data`,
  `input_data`) should drop the naming-fingerprint signal and indicators.
- **Combined evasion** — the sum of the above is the realistic `"humanizer"`
  attack: all tests assert the *detector's actual response*, not a fantasy
  about robustness. Where a signal is defeated, we assert that defeat honestly
  so the reader sees exactly what a paraphrase attack buys.

Every attack must still produce **valid, parseable Python** — an attacker
would not submit broken code.

The point is not "the detector resists everything" — it does not. The point is
to make the resistance profile explicit and regression-frozen: if signal
weights or patterns change, these tests force the reader to reconsider whether
the heuristic still holds up under a comment-strip or paraphrase attack.
"""

import ast
import re

from src.backend.engines.similarity.ai_detection import AIDetectionEngine
from tests.fixtures.ai_detector.fixtures import get_ai_samples

# ---------------------------------------------------------------------------
# Adversarial attack transforms
# ---------------------------------------------------------------------------


def strip_comments(code: str) -> str:
    """Remove line comments and docstrings, keeping code valid."""
    text = re.sub(r"#.*$", "", code, flags=re.M)
    text = re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', "", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text)


def regularize_whitespace(code: str) -> str:
    """Collapse all blank lines and trailing spaces (uniform rhythm)."""
    return "\n".join(line.rstrip() for line in code.splitlines() if line.strip())


def paraphrase_identifiers(code: str) -> str:
    """Rename generic AI-style identifiers to terse human-style names."""
    text = code
    text = text.replace("process_data", "compute_rows")
    text = text.replace("validate_input", "check_input")
    text = text.replace("input_data", "rows")
    text = text.replace("processed_item", "row")
    text = text.replace("status", "kind")
    return text


def rename_identifiers(code: str) -> str:
    """Rename class/method identifiers (structural paraphrase)."""
    text = code
    text = text.replace("DataProcessor", "Calc")
    text = text.replace("_transform", "_build")
    text = text.replace("_aggregate", "_group")
    text = text.replace("_validate", "_ok")
    return text


ATTACKS = {
    "strip_comments": strip_comments,
    "regularize_whitespace": regularize_whitespace,
    "paraphrase_identifiers": paraphrase_identifiers,
    "rename_identifiers": rename_identifiers,
}


def combined_evasion(code: str) -> str:
    """Realistic humanizer: strip comments, collapse spacing, then rename."""
    return paraphrase_identifiers(regularize_whitespace(strip_comments(code)))


# ---------------------------------------------------------------------------
# Shared assertions
# ---------------------------------------------------------------------------


class TestAttackSanity:
    """Every attack must be a genuine, valid-code transform."""

    def test_all_attacks_modify_the_code(self) -> None:
        """Each attack must actually change its target sample."""
        samples = get_ai_samples()
        for name, attack in ATTACKS.items():
            assert any(
                attack(code) != code for code in samples.values()
            ), f"{name} did not modify any AI sample"

    def test_attacks_produce_valid_python(self) -> None:
        """Transformed output must still parse (attackers submit working code)."""
        for sample_name, code in get_ai_samples().items():
            if not sample_name.startswith("ai_python"):
                continue
            for name, attack in ATTACKS.items():
                transformed = attack(code)
                try:
                    ast.parse(transformed)
                except SyntaxError as exc:  # pragma: no cover - diagnostic
                    raise AssertionError(
                        f"{name} made {sample_name} unparseable: {exc}"
                    ) from exc

    def test_combined_evasion_produces_valid_python(self) -> None:
        """The combined humanizer attack must also stay valid."""
        for sample_name, code in get_ai_samples().items():
            if sample_name.startswith("ai_python"):
                ast.parse(combined_evasion(code))

    def test_engine_returns_bounded_scores(self) -> None:
        """Scores must stay in [0, 1] for both original and attacked code."""
        engine = AIDetectionEngine()
        for sample_name, code in get_ai_samples().items():
            variants = [code] + [attack(code) for attack in ATTACKS.values()]
            variants.append(combined_evasion(code))
            for variant in variants:
                result = engine.analyze(variant, "python")
                assert 0.0 <= result["ai_probability"] <= 1.0, (
                    f"{sample_name} produced out-of-range score "
                    f"{result['ai_probability']}"
                )


class TestCommentStripAttack:
    """Docstring/comment stripping is the cheapest, highest-yield evasion."""

    def test_docstring_density_collapses_to_zero(self) -> None:
        """Removing docstrings must zero the docstring-density signal."""
        engine = AIDetectionEngine()
        for code in get_ai_samples().values():
            original = engine.analyze(code, "python")
            assert original["signals"].get("docstring_density", 0.0) > 0.5
            stripped = engine.analyze(strip_comments(code), "python")
            assert stripped["signals"].get("docstring_density", 1.0) == 0.0

    def test_fingerprint_pattern_signal_shrinks(self) -> None:
        """The templated-comment fingerprints should weaken after stripping."""
        engine = AIDetectionEngine()
        code = get_ai_samples()["ai_python_simple"]
        original = engine.analyze(code, "python")
        stripped = engine.analyze(strip_comments(code), "python")
        assert original["signals"]["pattern_library"] >= 0.5
        assert (
            stripped["signals"]["pattern_library"]
            < original["signals"]["pattern_library"]
        )

    def test_fused_score_drops(self) -> None:
        """Comment stripping should measurably lower the fused score."""
        engine = AIDetectionEngine()
        code = get_ai_samples()["ai_python_simple"]
        original = engine.analyze(code, "python")["ai_probability"]
        stripped = engine.analyze(strip_comments(code), "python")["ai_probability"]
        assert stripped < original

    def test_structural_statistical_signals_persist(self) -> None:
        """Signals not tied to comments should survive stripping.

        This is the honest counter-side of the attack: perplexity, burstiness
        and structural entropy are comment-independent, so a comment strip
        alone must not collapse the entire profile.
        """
        engine = AIDetectionEngine()
        for code in get_ai_samples().values():
            original = engine.analyze(code, "python")
            stripped = engine.analyze(strip_comments(code), "python")
            persist = ["perplexity", "burstiness", "structural_entropy"]
            for signal in persist:
                before = original["signals"].get(signal, 0.0)
                after = stripped["signals"].get(signal, 0.0)
                assert (
                    abs(after - before) < 0.15
                ), f"{signal} moved {before} -> {after} on comment strip"


class TestWhitespaceRegularizationAttack:
    """Collapsing blank lines should defeat the whitespace-rhythm signal."""

    def test_whitespace_rhythm_signal_zeros(self) -> None:
        """Uniform spacing should collapse the rhythm signal to zero."""
        engine = AIDetectionEngine()
        for code in get_ai_samples().values():
            original = engine.analyze(code, "python")
            assert original["signals"].get("whitespace_rhythm", 0.0) >= 0.9
            reformed = engine.analyze(regularize_whitespace(code), "python")
            assert reformed["signals"].get("whitespace_rhythm", 1.0) == 0.0

    def test_regularization_does_not_touch_comment_independent_signals(self) -> None:
        """Whitespace changes must not distort statistical signals."""
        engine = AIDetectionEngine()
        for code in get_ai_samples().values():
            original = engine.analyze(code, "python")
            reformed = engine.analyze(regularize_whitespace(code), "python")
            for signal in ("perplexity", "burstiness", "vocabulary_richness"):
                before = original["signals"].get(signal, 0.0)
                after = reformed["signals"].get(signal, 0.0)
                assert (
                    abs(after - before) < 0.15
                ), f"{signal} moved {before} -> {after} on whitespace change"


class TestParaphraseAttack:
    """Renaming generic AI identifiers is the 'rewrite' humanizer weapon."""

    def test_generic_naming_indicator_removed(self) -> None:
        """After paraphrase, the 'generic AI naming' indicator should vanish."""
        engine = AIDetectionEngine()
        code = get_ai_samples()["ai_python_generic"]
        original = engine.analyze(code, "python")
        paraphrased = engine.analyze(paraphrase_identifiers(code), "python")
        assert any("Generic AI naming" in ind for ind in original["indicators"])
        assert not any("Generic AI naming" in ind for ind in paraphrased["indicators"])

    def test_paraphrase_reduces_pattern_library(self) -> None:
        """Naming fingerprints should weaken after paraphrase."""
        engine = AIDetectionEngine()
        code = get_ai_samples()["ai_python_generic"]
        original = engine.analyze(code, "python")
        paraphrased = engine.analyze(paraphrase_identifiers(code), "python")
        assert (
            paraphrased["signals"]["pattern_library"]
            < original["signals"]["pattern_library"]
        )


class TestCombinedEvasion:
    """The realistic humanizer combines all single attacks."""

    def test_combined_attack_lowers_score(self) -> None:
        """Full evasion must reduce the fused score below baseline."""
        engine = AIDetectionEngine()
        for name, code in get_ai_samples().items():
            original = engine.analyze(code, "python")["ai_probability"]
            evaded = engine.analyze(combined_evasion(code), "python")["ai_probability"]
            assert evaded < original, (
                f"{name}: combined evasion did not reduce score "
                f"({original} -> {evaded})"
            )

    def test_combined_attack_is_stronger_than_any_single_attack(self) -> None:
        """A full humanizer should beat each individual attack alone.

        Uses the most fingerprint-heavy sample where single attacks matter.
        """
        engine = AIDetectionEngine()
        code = get_ai_samples()["ai_python_simple"]
        baseline = engine.analyze(code, "python")["ai_probability"]
        single_best = min(
            engine.analyze(attack(code), "python")["ai_probability"]
            for attack in ATTACKS.values()
        )
        combined = engine.analyze(combined_evasion(code), "python")["ai_probability"]
        assert (
            combined < single_best < baseline
        ), f"combined={combined} single_best={single_best} baseline={baseline}"

    def test_combined_attack_survives_as_bounded_false_negative(self) -> None:
        """Document the honest outcome on the strongest case (no overclaim).

        A full humanizer on the most fingerprint-heavy sample pushes the fused
        score well below the medium-risk threshold (0.40). This is a real,
        known false-negative vector — the matrix doc warns that a credulous
        humanizer defeats the heuristic path. We assert the *measured* outcome,
        so an improvement to the heuristic must explicitly change this test.
        """
        engine = AIDetectionEngine()
        code = get_ai_samples()["ai_python_simple"]
        baseline = engine.analyze(code, "python")["ai_probability"]
        evaded = engine.analyze(combined_evasion(code), "python")["ai_probability"]
        assert baseline >= 0.30, "fixture moved: AI sample no longer scores high"
        assert evaded < 0.30, (
            f"combined evasion expected < 0.30, got {evaded} — heuristic may "
            f"have improved, review this test before updating the doc claim"
        )
