"""Catalog of supported LLM vendors plus live model discovery.

Vendors ship new flagship models every few weeks, so a hardcoded model list is
stale almost immediately. This module therefore treats each vendor's own
``/models`` endpoint as the source of truth and ranks the returned IDs by
"most useful for this application" (newest version, strongest tier, auto-
updating aliases first).

Almost every important vendor now exposes an OpenAI-compatible
``/chat/completions`` API -- OpenAI, xAI, Mistral, DeepSeek, Groq, OpenRouter,
Ollama and Google's Gemini compatibility layer -- so adding a vendor is a data
change in :data:`PROVIDER_SPECS`, not new request code. Anthropic keeps its
native Messages API.

When a live listing is impossible (no API key, offline host, or an endpoint
error) the per-vendor ``recommended`` tuple is used instead. Those entries are
deliberately built from vendor aliases (``-latest``, ``deepseek-chat``, ...) and
the current flagship IDs, and are labelled ``source="recommended"`` so the UI
can be explicit that they were not verified against the vendor.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Cache lifetime for a live model listing, in seconds.
DEFAULT_MODEL_CACHE_TTL_SECONDS = 900

#: How many models the settings page receives by default.
DEFAULT_MODEL_LIMIT = 25


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of one LLM vendor.

    Attributes:
        key: Stable provider identifier stored in the database.
        label: Human-readable vendor name for the settings page.
        api_style: ``openai`` for OpenAI-compatible chat APIs, ``anthropic``
            for the native Messages API.
        base_url: Default base URL used for chat completions.
        docs_url: Link to the vendor's model documentation.
        key_url: Link to the page where a user creates an API key.
        requires_key: ``False`` for local runtimes such as Ollama.
        list_style: Response shape of the vendor's model-listing endpoint
            (``openai``, ``anthropic`` or ``google``).
        list_base_url: Base URL for the model listing when it differs from
            ``base_url`` (Gemini's native API vs. its OpenAI-compat layer).
        recommended: Newest known-good model IDs, used only when a live
            listing is unavailable. Ordered best-first.
        note: Optional hint shown next to the provider in the UI.
    """

    key: str
    label: str
    api_style: str
    base_url: str
    docs_url: str
    key_url: str
    requires_key: bool = True
    list_style: str = "openai"
    list_base_url: str | None = None
    recommended: tuple[str, ...] = ()
    note: str = ""


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        api_style="openai",
        base_url="https://api.openai.com/v1",
        docs_url="https://platform.openai.com/docs/models",
        key_url="https://platform.openai.com/api-keys",
        recommended=("gpt-6-astra", "gpt-5.6-terra", "gpt-5.6-luna"),
    ),
    "anthropic": ProviderSpec(
        key="anthropic",
        label="Anthropic",
        api_style="anthropic",
        base_url="https://api.anthropic.com/v1",
        docs_url="https://platform.claude.com/docs/en/about-claude/models/overview",
        key_url="https://console.anthropic.com/settings/keys",
        list_style="anthropic",
        recommended=(
            "claude-opus-5-5",
            "claude-sonnet-5",
            "claude-fable-5-1",
            "claude-haiku-4-5-20251001",
        ),
    ),
    "google": ProviderSpec(
        key="google",
        label="Google Gemini",
        api_style="openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        docs_url="https://ai.google.dev/gemini-api/docs/models",
        key_url="https://aistudio.google.com/app/apikey",
        list_style="google",
        list_base_url="https://generativelanguage.googleapis.com/v1beta",
        recommended=("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"),
    ),
    "xai": ProviderSpec(
        key="xai",
        label="xAI Grok",
        api_style="openai",
        base_url="https://api.x.ai/v1",
        docs_url="https://docs.x.ai/docs/models",
        key_url="https://console.x.ai",
        recommended=("grok-4.7",),
    ),
    "mistral": ProviderSpec(
        key="mistral",
        label="Mistral AI",
        api_style="openai",
        base_url="https://api.mistral.ai/v1",
        docs_url="https://docs.mistral.ai/getting-started/models/models_overview/",
        key_url="https://console.mistral.ai/api-keys",
        recommended=(
            "mistral-medium-latest",
            "mistral-large-latest",
            "mistral-small-latest",
        ),
    ),
    "deepseek": ProviderSpec(
        key="deepseek",
        label="DeepSeek",
        api_style="openai",
        base_url="https://api.deepseek.com/v1",
        docs_url="https://api-docs.deepseek.com/quick_start/pricing",
        key_url="https://platform.deepseek.com/api_keys",
        recommended=("deepseek-chat", "deepseek-reasoner"),
    ),
    "groq": ProviderSpec(
        key="groq",
        label="Groq",
        api_style="openai",
        base_url="https://api.groq.com/openai/v1",
        docs_url="https://console.groq.com/docs/models",
        key_url="https://console.groq.com/keys",
        recommended=("openai/gpt-oss-120b", "moonshotai/kimi-k2-instruct"),
    ),
    "openrouter": ProviderSpec(
        key="openrouter",
        label="OpenRouter",
        api_style="openai",
        base_url="https://openrouter.ai/api/v1",
        docs_url="https://openrouter.ai/models",
        key_url="https://openrouter.ai/keys",
        recommended=("openrouter/auto",),
        note="One key for many vendors; model IDs are namespaced (vendor/model).",
    ),
    "ollama": ProviderSpec(
        key="ollama",
        label="Ollama (local)",
        api_style="openai",
        base_url="http://localhost:11434/v1",
        docs_url="https://ollama.com/library",
        key_url="https://ollama.com/download",
        requires_key=False,
        recommended=(),
        note="Runs on your own hardware; pull a model first, then refresh.",
    ),
}

#: Alternative spellings accepted from the UI or environment variables.
PROVIDER_ALIASES: dict[str, str] = {
    "gemini": "google",
    "google-gemini": "google",
    "googleai": "google",
    "grok": "xai",
    "x-ai": "xai",
    "claude": "anthropic",
    "open-ai": "openai",
    "open_ai": "openai",
    "mistralai": "mistral",
    "deep-seek": "deepseek",
}

#: Legacy environment variables older integrations read directly, keyed by
#: provider. Mirrored alongside ``LLM_API_KEYS`` so existing deployments and
#: third-party clients keep working without configuration changes.
LEGACY_KEY_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


# ─── Normalization and lookup ────────────────────────────────────────


def normalize_provider(provider: str | None) -> str:
    """Return the canonical provider key for a user-supplied name.

    Args:
        provider: Provider name or alias (for example ``gemini`` or ``grok``).

    Returns:
        The canonical key from :data:`PROVIDER_SPECS`, or ``""`` when empty.
    """
    normalized = str(provider or "").strip().lower()
    if not normalized:
        return ""
    return PROVIDER_ALIASES.get(normalized, normalized)


def supported_providers() -> tuple[str, ...]:
    """Return every canonical provider key in catalog order."""
    return tuple(PROVIDER_SPECS)


def get_provider_spec(provider: str) -> ProviderSpec:
    """Look up a provider spec, accepting aliases.

    Args:
        provider: Provider name or alias.

    Returns:
        The matching :class:`ProviderSpec`.

    Raises:
        ValueError: when the provider is not in the catalog.
    """
    key = normalize_provider(provider)
    spec = PROVIDER_SPECS.get(key)
    if spec is None:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: {', '.join(supported_providers())}"
        )
    return spec


def provider_catalog_payload() -> list[dict[str, Any]]:
    """Describe every provider for the settings page (never includes secrets)."""
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "base_url": spec.base_url,
            "docs_url": spec.docs_url,
            "key_url": spec.key_url,
            "requires_key": spec.requires_key,
            "api_style": spec.api_style,
            "recommended": list(spec.recommended),
            "note": spec.note,
        }
        for spec in PROVIDER_SPECS.values()
    ]


# ─── Model filtering / ranking ───────────────────────────────────────

#: Model families that cannot answer a text prompt, or that exist for a
#: different product surface (audio, images, safety, retrieval, agents).
_EXCLUDE_PATTERNS: tuple[str, ...] = (
    r"embed",
    r"moderation",
    r"whisper",
    r"transcrib",
    r"(^|[-_/])tts",
    r"audio",
    r"(^|[-_/])live",
    r"realtime",
    r"image",
    r"dall-e",
    r"sora",
    r"video",
    r"veo\b",
    r"imagen",
    r"lyria",
    r"computer-use",
    r"robotics",
    r"rerank",
    r"guard",
    r"(^|[-_/])ocr",
    r"codex",
    r"codestral",
    r"voxtral",
    r"voice",
    r"davinci",
    r"babbage",
    r"curie",
    r"ada-0",
    r"chatgpt",
    r"chat-latest",
    r"deep-research",
    r"search-preview",
    r"stable-diffusion",
    r"nano-banana",
)

_EXCLUDE_RE = re.compile("|".join(_EXCLUDE_PATTERNS), re.IGNORECASE)

#: Capability tiers mapped to the weakest matching keyword. Vendors name a
#: variant by adding a modifier (``gemini-3.5-flash-lite``, ``gpt-4o-mini``), so
#: the most specific keyword describes the model best.
_TIER_KEYWORDS: tuple[tuple[str, int, str], ...] = (
    ("ultra", 100, "flagship"),
    ("opus", 98, "flagship"),
    ("fable", 96, "flagship"),
    ("astra", 95, "flagship"),
    ("max", 90, "flagship"),
    ("pro", 86, "advanced"),
    ("sonnet", 80, "balanced"),
    ("medium", 78, "balanced"),
    ("terra", 76, "balanced"),
    ("large", 70, "balanced"),
    ("plus", 66, "balanced"),
    ("turbo", 62, "balanced"),
    ("reasoner", 60, "reasoning"),
    ("flash", 58, "fast"),
    ("small", 46, "efficient"),
    ("mini", 42, "efficient"),
    ("haiku", 40, "efficient"),
    ("luna", 38, "efficient"),
    ("lite", 34, "efficient"),
    ("nano", 30, "efficient"),
    ("micro", 28, "efficient"),
    ("instant", 26, "efficient"),
)

#: Token splitter used for tier matching; keeps ``gemini`` from matching
#: ``mini`` while still splitting ``gpt-5.6-luna`` into usable tokens.
_TIER_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: Preview/experimental markers. Kept but ranked below GA models.
_PREVIEW_RE = re.compile(
    r"preview|experimental|-exp\b|-beta\b|-rc\b|alpha|nightly", re.IGNORECASE
)

#: Version tokens such as ``5.6`` in ``gpt-5.6-terra`` or ``3-8`` in
#: ``gemini-3-8-flash``. Date stamps (``20251001``) are rejected later.
_VERSION_RE = re.compile(r"(?<![\d.])(\d{1,2})(?:[.\-_](\d{1,2}))?(?![\d])")


def _version_score(model_id: str) -> float:
    """Extract a comparable version number from a model ID.

    Args:
        model_id: Vendor model identifier.

    Returns:
        ``major + minor / 10`` for the first plausible version token, or
        ``0.0`` when the ID carries no usable version.
    """
    for match in _VERSION_RE.finditer(model_id):
        major = int(match.group(1))
        if not 1 <= major <= 30:
            continue
        minor_raw = match.group(2)
        if minor_raw is None:
            return float(major)
        minor = int(minor_raw)
        if minor > 9:
            # Vendors such as xAI count ``4.20`` after ``4.7``; keep the token
            # comparable without letting it dwarf a higher major version.
            return major + minor / 100.0
        return major + minor / 10.0
    return 0.0


def _tier_score(model_id: str) -> tuple[int, str]:
    """Rate a model's capability tier from its name.

    Keywords are matched as whole tokens and the *weakest* match wins. That
    keeps ``gemini-3.8-pro`` at ``advanced`` (``gemini`` must not be read as
    ``mini``) while correctly reading ``gemini-3.5-flash-lite`` as the
    ``efficient`` variant of Flash.

    Args:
        model_id: Vendor model identifier.

    Returns:
        A ``(score, tier_label)`` tuple; ``(45, "standard")`` when unknown.
    """
    tokens = set(_TIER_TOKEN_RE.findall(model_id.lower()))
    best: tuple[int, str] | None = None
    for keyword, score, label in _TIER_KEYWORDS:
        if keyword in tokens and (best is None or score < best[0]):
            best = (score, label)
    return best if best is not None else (45, "standard")


def _is_chat_model(model_id: str) -> bool:
    """Return ``True`` when a model ID can serve a text chat completion."""
    return bool(model_id) and not _EXCLUDE_RE.search(model_id)


def rank_models(
    model_ids: list[str],
    *,
    created: dict[str, int] | None = None,
    recommended: tuple[str, ...] = (),
    limit: int = DEFAULT_MODEL_LIMIT,
) -> list[dict[str, Any]]:
    """Filter and rank vendor models by usefulness for evidence summarization.

    Ranking is deliberately vendor-agnostic: it combines the model family
    version, the capability tier encoded in the name, recency reported by the
    vendor, and a bonus for auto-updating aliases (``-latest``, ``vendor/auto``)
    so the top of the list is always the most capable current option.

    Args:
        model_ids: Raw model IDs returned by the vendor.
        created: Optional creation timestamps (unix seconds) keyed by model ID.
        recommended: The provider's recommended fallback IDs, boosted when
            they appear in the live listing.
        limit: Maximum number of models to return.

    Returns:
        A list of ``{"id", "label", "tier", "version", "created"}`` dicts,
        best-first.
    """
    created = created or {}
    unique = list(
        dict.fromkeys(mid.strip() for mid in model_ids if mid and mid.strip())
    )
    chat_models = [mid for mid in unique if _is_chat_model(mid)]
    if not chat_models:
        return []

    # Recency percentile (0-8 points) among the models actually offered.
    timestamps = sorted(
        (created[mid] for mid in chat_models if created.get(mid)), reverse=True
    )
    recency_points: dict[str, float] = {}
    if timestamps:
        newest, oldest = timestamps[0], timestamps[-1]
        span = max(newest - oldest, 1)
        recency_points = {
            mid: 8.0 * ((created[mid] - oldest) / span)
            for mid in chat_models
            if created.get(mid)
        }

    recommended_rank = {
        mid: len(recommended) - idx for idx, mid in enumerate(recommended)
    }
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for mid in chat_models:
        version = _version_score(mid)
        tier_score, tier_label = _tier_score(mid)
        points = version * 3.0 + tier_score * 0.25
        points += recency_points.get(mid, 0.0)
        if recommended_rank.get(mid):
            points += 12.0 + recommended_rank[mid]
        if mid.endswith("-latest") or mid.endswith("/auto"):
            points += 10.0
        if _PREVIEW_RE.search(mid):
            points -= 14.0
        scored.append(
            (
                points,
                mid,
                {
                    "id": mid,
                    "label": mid,
                    "tier": tier_label,
                    "version": version or None,
                    "created": created.get(mid),
                },
            )
        )

    scored.sort(key=lambda item: (-item[0], -int(item[2]["created"] or 0), item[1]))
    return [entry for _, _, entry in scored[: max(limit, 0)]]


# ─── Live discovery ──────────────────────────────────────────────────

#: ``{provider: (expires_at, payload)}`` -- vendors publish models rarely
#: enough that a short cache avoids hammering their API on every page load.
_MODEL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def clear_model_cache(provider: str | None = None) -> None:
    """Drop cached model listings.

    Args:
        provider: Specific provider to clear, or ``None`` for all providers.
    """
    with _CACHE_LOCK:
        if provider is None:
            _MODEL_CACHE.clear()
            return
        _MODEL_CACHE.pop(normalize_provider(provider), None)


def _build_list_request(
    spec: ProviderSpec,
    api_key: str,
    base_url: str | None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Build the model-listing request for a provider.

    Args:
        spec: Provider being queried.
        api_key: Credential for the provider (may be empty for local hosts).
        base_url: Optional base URL override from settings.

    Returns:
        A ``(url, headers, params)`` tuple.
    """
    if spec.list_style == "anthropic":
        root = (base_url or spec.base_url).rstrip("/")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        return f"{root}/models", headers, {"limit": 100}
    if spec.list_style == "google":
        root = (spec.list_base_url or spec.base_url).rstrip("/")
        headers = {"Content-Type": "application/json"}
        return f"{root}/models", headers, {"key": api_key, "pageSize": 200}
    root = (base_url or spec.base_url).rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return f"{root}/models", headers, {}


def _parse_model_list(list_style: str, data: Any) -> tuple[list[str], dict[str, int]]:
    """Extract model IDs and creation timestamps from a vendor response.

    Args:
        list_style: Response shape to parse (``openai``, ``anthropic`` or
            ``google``).
        data: Decoded JSON response body.

    Returns:
        A ``(model_ids, created)`` tuple where ``created`` maps model ID to a
        unix timestamp when the vendor reports one.
    """
    ids: list[str] = []
    created: dict[str, int] = {}
    if not isinstance(data, dict):
        return ids, created

    if list_style == "google":
        for entry in data.get("models") or []:
            if not isinstance(entry, dict):
                continue
            methods = entry.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            name = str(entry.get("name") or "")
            if name.startswith("models/"):
                name = name[len("models/") :]
            if name:
                ids.append(name)
        return ids, created

    for entry in data.get("data") or []:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("id") or entry.get("name") or "").strip()
        if not model_id:
            continue
        ids.append(model_id)
        raw_created = entry.get("created_at") or entry.get("created")
        if isinstance(raw_created, (int, float)) and raw_created > 0:
            created[model_id] = int(raw_created)
        elif isinstance(raw_created, str):
            try:
                parsed = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
                created[model_id] = int(parsed.timestamp())
            except ValueError:
                pass
    return ids, created


# ─── Public discovery API ────────────────────────────


def _recommended_payload(spec: ProviderSpec, limit: int, reason: str) -> dict[str, Any]:
    """Build the fallback payload used when live discovery is impossible."""
    models = rank_models(list(spec.recommended), limit=limit)
    return {
        "provider": spec.key,
        "label": spec.label,
        "source": "recommended",
        "models": models,
        "count": len(models),
        "available_count": len(spec.recommended),
        "excluded_count": 0,
        "message": reason,
        "docs_url": spec.docs_url,
        "key_url": spec.key_url,
        "base_url": spec.base_url,
        "requires_key": spec.requires_key,
        "note": spec.note,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }


async def list_provider_models(
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
    *,
    refresh: bool = False,
    limit: int = DEFAULT_MODEL_LIMIT,
    cache_ttl_seconds: int = DEFAULT_MODEL_CACHE_TTL_SECONDS,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Return the most useful currently-available models for a provider.

    Live vendor discovery is attempted first. When that is not possible the
    provider's recommended list is returned with ``source="recommended"`` and a
    ``message`` explaining why, so the UI never implies a verified listing.

    Args:
        provider: Provider key or alias.
        api_key: Credential for the provider, when one is configured.
        base_url: Optional base URL override from settings.
        refresh: Bypass the in-memory cache and re-query the vendor.
        limit: Maximum number of models to return.
        cache_ttl_seconds: How long a successful listing stays cached.
        transport: Injected transport for tests.
        timeout: Per-request timeout in seconds.

    Returns:
        A payload describing the listing, including ``source``, ``models`` and
        a human-readable ``message``.

    Raises:
        ValueError: when the provider is not in the catalog.
    """
    spec = get_provider_spec(provider)
    cache_key = f"{spec.key}:{limit}"

    if not refresh:
        with _CACHE_LOCK:
            cached = _MODEL_CACHE.get(cache_key)
        if cached and cached[0] > time.monotonic():
            payload = dict(cached[1])
            payload["cached"] = True
            return payload

    if spec.requires_key and not api_key:
        return _recommended_payload(
            spec, limit, f"No {spec.label} API key configured yet."
        )

    url, headers, params = _build_list_request(spec, api_key or "", base_url)
    try:
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, transport=transport
        ) as client:
            response = await client.get(url, params=params or None)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("Model discovery failed for %s: %s", spec.key, exc)
        return _recommended_payload(
            spec, limit, f"Could not list models from {spec.label}: {exc}"
        )

    model_ids, created = _parse_model_list(spec.list_style, data)
    models = rank_models(
        model_ids, created=created, recommended=spec.recommended, limit=limit
    )
    if not models:
        return _recommended_payload(
            spec, limit, f"{spec.label} returned no text chat models for this key."
        )

    payload: dict[str, Any] = {
        "provider": spec.key,
        "label": spec.label,
        "source": "live",
        "models": models,
        "count": len(models),
        "available_count": len(model_ids),
        "excluded_count": len(model_ids) - len(models),
        "message": "",
        "docs_url": spec.docs_url,
        "key_url": spec.key_url,
        "base_url": spec.base_url,
        "requires_key": spec.requires_key,
        "note": spec.note,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
    }
    with _CACHE_LOCK:
        _MODEL_CACHE[cache_key] = (
            time.monotonic() + max(cache_ttl_seconds, 0),
            dict(payload),
        )
    return payload


def latest_recommended_model(provider: str) -> str:
    """Return the best-known current model for a provider.

    Used as a last-resort default when neither the tenant nor the environment
    pinned a model, so the application never falls back to an obsolete ID.

    Args:
        provider: Provider key or alias.

    Returns:
        The first recommended model ID, or ``""`` when the provider has none.
    """
    try:
        spec = get_provider_spec(provider)
    except ValueError:
        return ""
    return spec.recommended[0] if spec.recommended else ""
