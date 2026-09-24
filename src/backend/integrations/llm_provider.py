"""LLM providers for evidence summarization and rewrite analysis.

Implements chat completions over httpx (no SDK dependency) so the API keys
configured on the settings page actually connect to a model. All callers must
degrade gracefully when no key is configured or the API is unreachable: the
async helpers in this module return a heuristic summary instead of raising.

Vendor support is data-driven: :mod:`src.backend.integrations.provider_catalog`
lists every supported vendor, and because OpenAI, Google (compatibility layer),
xAI, Mistral, DeepSeek, Groq, OpenRouter and Ollama all speak the same
OpenAI-compatible ``/chat/completions`` protocol, one request path serves them
all. Anthropic keeps its native Messages API.

Models are never hardcoded to an old generation: when no explicit model is
configured the newest model the provider currently offers is resolved from the
catalog (see :func:`resolve_provider_config`).

Both providers are intentionally kept in one small module so the settings
page can authenticate a connection and jobs can enrich flagged pairs with a
neutral, evidence-based explanation for the professor.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from src.backend.config.settings import settings
from src.backend.integrations.provider_catalog import (
    ProviderSpec,
    get_provider_spec,
    latest_recommended_model,
    normalize_provider,
    supported_providers,
)

logger = logging.getLogger(__name__)

ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"

#: Every provider accepted by :class:`LLMProvider`, in catalog order.
SUPPORTED_PROVIDERS: tuple[str, ...] = supported_providers()

#: Legacy per-provider settings attributes kept in sync with the generic
#: `LLM_API_KEYS` / `LLM_MODEL_OVERRIDES` maps so existing deployments and
#: environment variables keep working unchanged.
_LEGACY_KEY_ATTRS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_LEGACY_MODEL_ATTRS: dict[str, str] = {
    "openai": "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
}
_LEGACY_BASE_URL_ATTRS: dict[str, str] = {
    "openai": "OPENAI_BASE_URL",
    "ollama": "OLLAMA_BASE_URL",
}

_MAX_CODE_CHARS = 2000

#: Substrings vendors use when they reject a request *parameter* (rather than
#: the model or the whole payload). Matching one lets the client retry with the
#: offending field dropped or renamed.
_PARAMETER_REJECTION_MARKERS: tuple[str, ...] = (
    "max_tokens",
    "max_completion_tokens",
    "temperature",
    "unsupported parameter",
    "unsupported value",
    "unknown parameter",
    "unrecognized request argument",
    "does not support",
)


def _is_parameter_rejection(detail: str) -> bool:
    """Return ``True`` when an error body blames a request parameter.

    Args:
        detail: Response body text from a rejected request.

    Returns:
        ``True`` when the error names a parameter this client can adapt.
    """
    lowered = (detail or "").lower()
    return any(marker in lowered for marker in _PARAMETER_REJECTION_MARKERS)


class LLMError(RuntimeError):
    """Raised when the LLM API cannot be reached or returns an error."""


@dataclass(frozen=True)
class LLMProviderConfig:
    """Provider identity resolved from application settings."""

    provider: str
    api_key: str
    model: str
    base_url: str
    #: ``openai`` for OpenAI-compatible chat APIs, ``anthropic`` for the
    #: native Messages API.
    api_style: str = "openai"


class LLMProvider:
    """Minimal chat-completion client for every supported vendor.

    The request path is selected from the vendor's ``api_style`` so all
    OpenAI-compatible vendors share one implementation. The transport is
    injectable so unit tests can exercise request/response handling with
    ``httpx.MockTransport`` instead of hitting a real API.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
        api_style: str | None = None,
    ) -> None:
        normalized = normalize_provider(provider)
        spec = self._resolve_spec(normalized, provider)
        if spec.requires_key and not api_key:
            raise LLMError(f"{spec.label} API key is not configured")
        if not model:
            raise LLMError(f"No model configured for {spec.label}")
        self.provider = spec.key
        self.api_key = api_key
        self.model = model
        self.api_style = api_style or spec.api_style
        self.base_url = (base_url or spec.base_url).rstrip("/")
        self.timeout = timeout
        self._transport = transport

    @staticmethod
    def _resolve_spec(normalized: str, original: str) -> ProviderSpec:
        """Look up the provider spec, translating catalog errors.

        Args:
            normalized: Canonical provider key (possibly empty).
            original: The value the caller supplied, used in the error text.

        Returns:
            The matching provider spec.

        Raises:
            ValueError: when the provider is not supported.
        """
        if not normalized:
            raise ValueError(f"Unsupported LLM provider: {original}")
        return get_provider_spec(normalized)

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> str:
        """Return the model's text completion for a single prompt."""
        try:
            if self.api_style == "anthropic":
                return await self._anthropic_messages(
                    prompt, system, max_tokens, temperature
                )
            return await self._openai_chat(prompt, system, max_tokens, temperature)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response is not None else ""
            raise LLMError(
                f"{self.provider} API returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.provider} API request failed: {exc}") from exc

    async def test_connection(self) -> dict[str, Any]:
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
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """POST an OpenAI-compatible chat completion.

        Vendors differ in the token-limit field (``max_tokens`` for most,
        ``max_completion_tokens`` for OpenAI's current models) and reasoning
        models reject a custom ``temperature``. A 400 that names one of those
        fields is retried with the field dropped or renamed, so a freshly
        released model works without a code change.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        token_field = (
            "max_completion_tokens" if self.provider == "openai" else "max_tokens"
        )
        alternate_field = (
            "max_tokens"
            if token_field == "max_completion_tokens"
            else "max_completion_tokens"
        )
        attempts: list[dict[str, Any]] = [
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                token_field: max_tokens,
            },
            {"model": self.model, "messages": messages, token_field: max_tokens},
            {"model": self.model, "messages": messages, alternate_field: max_tokens},
        ]

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: LLMError | None = None
        for index, payload in enumerate(attempts):
            async with self._client(headers) as client:
                response = await client.post(url, json=payload)
            if response.status_code == 400 and index < len(attempts) - 1:
                detail = response.text[:300]
                if _is_parameter_rejection(detail):
                    last_error = LLMError(
                        f"{self.provider} rejected request parameters: {detail}"
                    )
                    continue
            response.raise_for_status()
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                raise LLMError(
                    f"Unexpected {self.provider} response: {str(data)[:200]}"
                )
            return str(content or "").strip()

        if last_error is not None:
            raise last_error
        raise LLMError(f"{self.provider} API request failed")

    async def _anthropic_messages(
        self,
        prompt: str,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload: dict[str, Any] = {
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

    def _client(self, headers: dict[str, str]) -> httpx.AsyncClient:
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


def configured_api_key(provider: str) -> str:
    """Return the stored API key for a provider.

    Args:
        provider: Canonical provider key or alias.

    Returns:
        The per-provider key from ``LLM_API_KEYS``, falling back to the legacy
        per-vendor setting so existing deployments keep working.
    """
    try:
        provider = get_provider_spec(provider).key
    except ValueError:
        return ""
    keys = settings.LLM_API_KEYS or {}
    value = str(keys.get(provider) or "").strip()
    if value:
        return value
    legacy_attr = _LEGACY_KEY_ATTRS.get(provider)
    if legacy_attr:
        return str(getattr(settings, legacy_attr, "") or "").strip()
    return ""


def _configured_model(provider: str) -> str:
    """Resolve the model to use for a provider.

    A stored override always wins. When nothing is pinned the newest model the
    vendor currently offers is used, which is what keeps this integration from
    drifting onto an obsolete generation.

    Args:
        provider: Canonical provider key.

    Returns:
        A model ID, or ``""`` when the vendor has no known models.
    """
    overrides = settings.LLM_MODEL_OVERRIDES or {}
    pinned = str(overrides.get(provider) or "").strip()
    if pinned:
        return pinned
    legacy_attr = _LEGACY_MODEL_ATTRS.get(provider)
    if legacy_attr:
        legacy_value = str(getattr(settings, legacy_attr, "") or "").strip()
        if legacy_value:
            return legacy_value
    return latest_recommended_model(provider)


def _configured_base_url(provider: str, spec: ProviderSpec) -> str:
    """Resolve the base URL for a provider.

    Args:
        provider: Canonical provider key.
        spec: The provider's catalog entry (its default base URL).

    Returns:
        The stored override, the legacy per-vendor setting, or the vendor
        default, in that order of precedence.
    """
    base_urls = settings.LLM_BASE_URLS or {}
    override = str(base_urls.get(provider) or "").strip()
    if override:
        return override.rstrip("/")
    legacy_attr = _LEGACY_BASE_URL_ATTRS.get(provider)
    if legacy_attr:
        legacy_value = str(getattr(settings, legacy_attr, "") or "").strip()
        if legacy_value:
            return legacy_value.rstrip("/")
    return spec.base_url.rstrip("/")


def resolve_provider_config(
    provider: str = "",
    api_key_override: str | None = None,
) -> LLMProviderConfig:
    """Resolve a provider config from settings.

    Both the provider and the model are resolved dynamically: an empty
    ``provider`` means "use the configured default", and an unpinned model
    means "use the newest model this vendor currently offers". That is what
    prevents the integration from being stuck on an outdated model.

    Args:
        provider: Provider key or alias; falls back to ``LLM_PROVIDER`` and
            then to OpenAI.
        api_key_override: Optional key supplied by the user on the settings
            page before saving; falls back to the configured key.

    Returns:
        LLMProviderConfig with resolved provider, key, model, base URL and the
        API style used to select the request path.

    Raises:
        ValueError: for unsupported providers.
    """
    candidate = (
        normalize_provider(provider)
        or normalize_provider(settings.LLM_PROVIDER)
        or "openai"
    )
    spec = get_provider_spec(candidate)
    return LLMProviderConfig(
        provider=spec.key,
        api_key=(api_key_override or "").strip() or configured_api_key(spec.key),
        model=_configured_model(spec.key),
        base_url=_configured_base_url(spec.key, spec),
        api_style=spec.api_style,
    )


async def test_provider_connection(
    provider: str = "",
    api_key_override: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Test a configured provider and return a professor-facing result.

    Args:
        provider: Provider key or alias; empty means "use the configured one".
        api_key_override: Optional key typed on the settings page.
        transport: Optional mock transport for tests.

    Returns:
        A dict with ``ok``, a human-readable ``message``, the resolved
        ``provider``, ``model`` and ``latency_ms``.
    """
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
            api_style=config.api_style,
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
    result["base_url"] = config.base_url
    return result


async def summarize_pair_evidence(
    code_a: str,
    code_b: str,
    features: Mapping[str, float],
    provider: str = "",
    api_key_override: str | None = None,
    file_a: str = "file_a",
    file_b: str = "file_b",
    task: str = "evidence",
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Summarize a pair with the LLM, or fall back to a heuristic summary.

    Args:
        code_a: First submission source code.
        code_b: Second submission source code.
        features: Engine scores to interpret.
        provider: Provider key or alias; empty means "use the configured one".
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
            api_style=config.api_style,
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
