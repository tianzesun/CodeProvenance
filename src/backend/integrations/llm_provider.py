"""LLM providers for evidence summarization and rewrite analysis.

Implements OpenAI and Anthropic chat completions over httpx (no SDK
dependency) so the API keys configured on the settings page actually
connect to a model. All callers must degrade gracefully when no key is
configured or the API is unreachable: the async helpers in this module
return a heuristic summary instead of raising.

Both providers are intentionally kept in one small module so the settings
page can authenticate a connection and jobs can enrich flagged pairs with a
neutral, evidence-based explanation for the professor.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import httpx

from src.backend.config.settings import settings

logger = logging.getLogger(__name__)

ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"

SUPPORTED_PROVIDERS = ("openai", "anthropic")

_MAX_CODE_CHARS = 2000


class LLMError(RuntimeError):
    """Raised when the LLM API cannot be reached or returns an error."""


@dataclass(frozen=True)
class LLMProviderConfig:
    """Provider identity resolved from application settings."""

    provider: str
    api_key: str
    model: str
    base_url: str


class LLMProvider:
    """Minimal chat-completion client for OpenAI and Anthropic.

    The transport is injectable so unit tests can exercise request/response
    handling with ``httpx.MockTransport`` instead of hitting a real API.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: float = 60.0,
    ) -> None:
        normalized = str(provider or "").strip().lower()
        if normalized not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        if not api_key:
            raise LLMError(f"{normalized} API key is not configured")
        if not model:
            raise LLMError(f"No model configured for {normalized}")
        self.provider = normalized
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "").rstrip("/")
        if not self.base_url:
            self.base_url = (
                settings.OPENAI_BASE_URL
                if self.provider == "openai"
                else ANTHROPIC_DEFAULT_BASE_URL
            )
        self.timeout = timeout
        self._transport = transport

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> str:
        """Return the model's text completion for a single prompt."""
        try:
            if self.provider == "openai":
                return await self._openai_chat(prompt, system, max_tokens, temperature)
            return await self._anthropic_messages(
                prompt, system, max_tokens, temperature
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response is not None else ""
            raise LLMError(
                f"{self.provider} API returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.provider} API request failed: {exc}") from exc

    async def test_connection(self) -> Dict[str, Any]:
        """Verify the configured key/model actually work with a trivial prompt."""
        started = time.monotonic()
        try:
            await self.complete("Reply with exactly: OK", max_tokens=4, temperature=0.0)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "ok": False,
                "message": str(exc),
                "latency_ms": elapsed_ms,
                "model": self.model,
            }
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "message": "Connected",
            "latency_ms": elapsed_ms,
            "model": self.model,
        }

    # -- provider request/response handling -----------------------------

    async def _openai_chat(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        messages: list[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with self._client(headers) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"Unexpected OpenAI response: {str(data)[:200]}")
        return str(content or "").strip()

    async def _anthropic_messages(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        async with self._client(headers) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            blocks = data.get("content", [])
            text = "".join(
                block.get("text", "") for block in blocks if block.get("type") == "text"
            )
        except (KeyError, TypeError):
            raise LLMError(f"Unexpected Anthropic response: {str(data)[:200]}")
        return text.strip()

    def _client(self, headers: Dict[str, str]) -> httpx.AsyncClient:
        """Build an async client; transport is only used to mock in tests."""
        return httpx.AsyncClient(
            headers=headers,
            timeout=self.timeout,
            transport=self._transport,
        )


# ─── Prompt construction ─────────────────────────────────────────────


def build_evidence_prompt(
    code_a: str,
    code_b: str,
    features: Mapping[str, float],
    file_a: str = "file_a",
    file_b: str = "file_b",
    task: str = "evidence",
) -> str:
    """Build an LLM prompt summarizing evidence for a submission pair.

    Args:
        code_a: First submission source code.
        code_b: Second submission source code.
        features: Engine scores (engine name -> similarity score).
        file_a: Display name for the first file.
        file_b: Display name for the second file.
        task: ``evidence`` for neutral similarity review, ``rewrite`` to also
            weigh in on whether differences look like AI-assisted rewriting.

    Returns:
        A single prompt string suitable for an LLM chat completion.
    """
    feature_lines = ", ".join(
        f"{name}={float(score):.3f}"
        for name, score in sorted(features.items())
        if score is not None
    )
    task_note = (
        "Assess whether remaining differences are consistent with AI-assisted "
        "rewriting (e.g. paraphrasing, renaming, restructuring) versus "
        "independent work."
        if task == "rewrite"
        else "Focus on what is similar, what differs, and what a human reviewer "
        "should verify."
    )
    return (
        f"Compare the two student code submissions below and interpret the "
        f"automated similarity features.\n\n"
        f"## {file_a}\n```\n{code_a[: _MAX_CODE_CHARS]}\n```\n\n"
        f"## {file_b}\n```\n{code_b[: _MAX_CODE_CHARS]}\n```\n\n"
        f"## Automated similarity features\n{feature_lines}\n\n"
        f"{task_note}\n\n"
        "Summarize in 4-6 neutral sentences. Describe concrete patterns and "
        "what a professor should verify. Do not allege misconduct."
    )


def _heuristic_summary(features: Mapping[str, float]) -> str:
    """Rule-based fallback when no LLM provider is available or callable."""
    if not features:
        return "No automated similarity features were available for review."
    ranked = sorted(
        ((name, float(score)) for name, score in features.items() if score is not None),
        key=lambda item: item[1],
        reverse=True,
    )
    top = ", ".join(f"{name}={score:.2f}" for name, score in ranked[:4])
    return (
        "No LLM provider is configured, so automated evidence is shown instead: "
        f"strongest signals are {top}. Review the pair directly."
    )


# ─── High-level helpers ──────────────────────────────────────────────


def resolve_provider_config(
    provider: str = "openai",
    api_key_override: Optional[str] = None,
) -> LLMProviderConfig:
    """Resolve a provider config from settings (optionally overriding the key).

    Args:
        provider: ``openai`` or ``anthropic``.
        api_key_override: Optional key supplied by the user on the settings
            page before saving; falls back to the configured key.

    Returns:
        LLMProviderConfig with resolved key, model, and base URL.

    Raises:
        ValueError: for unsupported providers.
    """
    normalized = str(provider or "").strip().lower()
    if normalized == "openai":
        return LLMProviderConfig(
            provider="openai",
            api_key=api_key_override or settings.OPENAI_API_KEY or "",
            model=settings.OPENAI_MODEL,
            base_url=settings.OPENAI_BASE_URL,
        )
    if normalized == "anthropic":
        return LLMProviderConfig(
            provider="anthropic",
            api_key=api_key_override or settings.ANTHROPIC_API_KEY or "",
            model=settings.ANTHROPIC_MODEL,
            base_url=ANTHROPIC_DEFAULT_BASE_URL,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


async def test_provider_connection(
    provider: str = "openai",
    api_key_override: Optional[str] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    """Test a configured provider and return a professor-facing result."""
    try:
        config = resolve_provider_config(provider, api_key_override)
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "provider": provider}
    try:
        llm = LLMProvider(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            transport=transport,
        )
    except LLMError as exc:
        return {
            "ok": False,
            "message": str(exc),
            "provider": config.provider,
            "model": config.model,
        }
    result = await llm.test_connection()
    result["provider"] = config.provider
    return result


async def summarize_pair_evidence(
    code_a: str,
    code_b: str,
    features: Mapping[str, float],
    provider: str = "openai",
    api_key_override: Optional[str] = None,
    file_a: str = "file_a",
    file_b: str = "file_b",
    task: str = "evidence",
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    """Summarize a pair with the LLM, or fall back to a heuristic summary.

    Args:
        code_a: First submission source code.
        code_b: Second submission source code.
        features: Engine scores to interpret.
        provider: ``openai`` or ``anthropic``.
        api_key_override: Optional key to use instead of the stored one.
        file_a, file_b: Display names for the submissions.
        task: ``evidence`` or ``rewrite``.
        transport: Optional mock transport for tests.

    Returns:
        A dict with ``summary``, ``provider``, ``source`` (``llm`` or
        ``heuristic``), and optional ``fallback_reason``.
    """
    try:
        config = resolve_provider_config(provider, api_key_override)
        llm = LLMProvider(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            transport=transport,
        )
    except (LLMError, ValueError) as exc:
        logger.info("LLM summary unavailable (%s); using heuristic", exc)
        return {
            "summary": _heuristic_summary(features),
            "provider": "heuristic",
            "source": "heuristic",
            "fallback_reason": str(exc),
        }

    prompt = build_evidence_prompt(
        code_a,
        code_b,
        features,
        file_a=file_a,
        file_b=file_b,
        task=task,
    )
    try:
        text = await llm.complete(
            prompt,
            system=(
                "You are an academic-integrity reviewer for a programming "
                "course. Write concise, neutral, evidence-based summaries for "
                "a professor. Do not allege misconduct; describe patterns and "
                "what a human should verify."
            ),
            max_tokens=400,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("LLM summary call failed (%s); using heuristic", exc)
        return {
            "summary": _heuristic_summary(features),
            "provider": "heuristic",
            "source": "heuristic",
            "fallback_reason": str(exc),
        }

    return {
        "summary": text,
        "provider": config.provider,
        "source": "llm",
    }
