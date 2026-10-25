"""The Python-only code LM must not score other languages."""

import pytest

from src.backend.engines.ai.perplexity import PerplexityScorer

CODE = "\n".join(f"value_{i} = compute({i}) + offset" for i in range(40))


@pytest.fixture
def scorer() -> PerplexityScorer:
    """A scorer whose 'code LM' is a stub, so no model download is needed."""
    instance = PerplexityScorer(transformer=False)
    instance._transformer_available = True
    instance._transformer_perplexity = lambda code: (50.0, -3.9)
    return instance


@pytest.mark.parametrize("language", ["python", "Python", "py"])
def test_python_uses_the_code_lm(scorer: PerplexityScorer, language: str) -> None:
    assert scorer.score(CODE, language=language)["model"] == "huggingface"


@pytest.mark.parametrize("language", ["java", "c", "cpp", "javascript", "unknown"])
def test_other_languages_use_the_statistical_model(
    scorer: PerplexityScorer, language: str
) -> None:
    assert scorer.score(CODE, language=language)["model"] == "statistical"


def test_language_defaults_to_python(scorer: PerplexityScorer) -> None:
    assert scorer.score(CODE)["model"] == "huggingface"
