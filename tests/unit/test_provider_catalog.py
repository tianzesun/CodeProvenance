"""Unit tests for the multi-vendor provider catalog and model discovery.

Uses httpx.MockTransport so no real vendor API calls are made.
"""

import asyncio

import httpx
import pytest

from src.backend.integrations.provider_catalog import (
    PROVIDER_SPECS,
    clear_model_cache,
    get_provider_spec,
    latest_recommended_model,
    list_provider_models,
    normalize_provider,
    provider_catalog_payload,
    rank_models,
)


def _run(coro):
    """Run an async helper synchronously (project test convention)."""
    return asyncio.run(coro)


# ─── Catalog structure ───────────────────────────────────────────────


class TestProviderCatalog:
    """Catalog integrity, aliases, and payload safety."""

    def test_catalog_contains_multiple_vendors(self) -> None:
        """The catalog covers OpenAI, Anthropic, Google, xAI, Mistral, DeepSeek."""
        keys = set(PROVIDER_SPECS)
        assert {"openai", "anthropic", "google", "xai", "mistral", "deepseek"} <= keys

    def test_every_spec_is_coherent(self) -> None:
        """Each spec has labels, base URLs, styles, and a recommended model."""
        for key, spec in PROVIDER_SPECS.items():
            assert spec.key == key
            assert spec.label
            if spec.requires_key:
                assert spec.base_url.startswith("https://")
            else:
                # Keyless local hosts may use plain http on loopback.
                assert spec.base_url.startswith(("http://", "https://"))
            assert spec.api_style in {"openai", "anthropic", "google"}
            assert spec.list_style in {"openai", "anthropic", "google"}
            if spec.requires_key:
                # Keyed cloud vendors must ship a working fallback; local
                # hosts (Ollama) legitimately ship none.
                assert spec.recommended, f"{key} must ship a recommended model"
            for model in spec.recommended:
                assert model, f"{key} recommended list must not contain blanks"

    def test_normalize_provider_aliases(self) -> None:
        """Aliases resolve to canonical keys; unknown input passes through."""
        assert normalize_provider("gemini") == "google"
        assert normalize_provider("Google") == "google"
        assert normalize_provider("claude") == "anthropic"
        assert normalize_provider("grok") == "xai"
        assert normalize_provider("  ") == ""
        assert normalize_provider("not-a-vendor") == "not-a-vendor"

    def test_get_provider_spec_rejects_unknown(self) -> None:
        """Unknown providers raise ValueError listing the valid options."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_provider_spec("cloudflare-ai")

    def test_catalog_payload_contains_no_secrets(self) -> None:
        """The UI-facing payload only exposes the documented safe fields."""
        allowed = {
            "key",
            "label",
            "base_url",
            "docs_url",
            "key_url",
            "requires_key",
            "api_style",
            "recommended",
            "note",
        }
        payload = provider_catalog_payload()
        assert payload
        for entry in payload:
            # Exact field allow-list: any future secret field must be denied.
            assert set(entry) <= allowed
            assert "key" in entry and "label" in entry

    def test_latest_recommended_model_is_not_obsolete(self) -> None:
        """Defaults are current-generation, never gpt-3.5 / claude-3-sonnet."""
        assert latest_recommended_model("openai") != "gpt-3.5-turbo"
        assert not latest_recommended_model("anthropic").startswith("claude-3-")
        assert latest_recommended_model("nope") == ""


# ─── Model ranking ───────────────────────────────────────────────────


class TestRankModels:
    """Filtering and vendor-agnostic ranking."""

    def test_excludes_non_chat_models(self) -> None:
        """Embeddings, moderation, audio, image and video models are dropped."""
        ranked = rank_models(
            [
                "text-embedding-3-large",
                "omni-moderation-latest",
                "whisper-1",
                "gpt-image-1",
                "sora-2",
                "gpt-5.6-terra",
            ]
        )
        ids = [entry["id"] for entry in ranked]
        assert ids == ["gpt-5.6-terra"]

    def test_flagship_ranks_above_efficient(self) -> None:
        """Capability tiers order the list flagship-first."""
        ranked = rank_models(
            ["gpt-5.6-luna", "gpt-5.6-terra", "claude-haiku-4-5", "claude-opus-5-5"]
        )
        ids = [entry["id"] for entry in ranked]
        assert ids.index("claude-opus-5-5") < ids.index("claude-haiku-4-5")
        assert ids.index("gpt-5.6-terra") < ids.index("gpt-5.6-luna")

    def test_newer_version_ranks_higher(self) -> None:
        """Within one family, higher version wins regardless of listing order."""
        ranked = rank_models(["gemini-3-6-flash", "gemini-3-8-flash"])
        assert [entry["id"] for entry in ranked] == [
            "gemini-3-8-flash",
            "gemini-3-6-flash",
        ]

    def test_latest_alias_gets_bonus_and_preview_penalized(self) -> None:
        """Auto-updating aliases beat pinned previews of the same family."""
        ranked = rank_models(["grok-4-7-preview", "grok-4-7-latest"])
        assert [entry["id"] for entry in ranked] == [
            "grok-4-7-latest",
            "grok-4-7-preview",
        ]

    def test_date_stamps_do_not_pollute_version(self) -> None:
        """Snapshot suffixes like -20251001 are not read as version numbers."""
        ranked = rank_models(["claude-haiku-4-5-20251001"])
        assert ranked[0]["version"] == 4.5

    def test_entries_carry_tier_and_limit_respected(self) -> None:
        """Output entries expose tier metadata and honor the limit."""
        ranked = rank_models(["a-flash", "b-opus", "c-mini"], limit=2)
        assert len(ranked) == 2
        assert all("tier" in entry for entry in ranked)
        assert ranked[0]["tier"] in {"flagship", "balanced", "fast", "efficient"}


# ─── Live discovery ──────────────────────────────────────────────────


def _openai_models_handler(request: httpx.Request) -> httpx.Response:
    """Serve an OpenAI-shaped model listing."""
    assert request.url.path.endswith("/models")
    return httpx.Response(
        200,
        json={
            "data": [
                {"id": "text-embedding-3-large", "created": 1700000000},
                {"id": "gpt-6-astra", "created": 1780000000},
                {"id": "gpt-5.6-terra", "created": 1775000000},
                {"id": "gpt-5.6-luna", "created": 1776000000},
                {"id": "whisper-1", "created": 1690000000},
            ]
        },
    )


def _anthropic_models_handler(request: httpx.Request) -> httpx.Response:
    """Serve an Anthropic-shaped model listing."""
    assert request.url.path.endswith("/models")
    assert request.headers["x-api-key"] == "test-key"
    return httpx.Response(
        200,
        json={
            "data": [
                {"id": "claude-fable-5-1", "created_at": "2026-06-01T00:00:00Z"},
                {"id": "claude-opus-5-5", "created_at": "2026-06-01T00:00:00Z"},
                {"id": "claude-sonnet-5", "created_at": "2026-01-01T00:00:00Z"},
            ],
            "has_more": False,
        },
    )


def _google_models_handler(request: httpx.Request) -> httpx.Response:
    """Serve a Google-shaped model listing, mixing chat and non-chat models."""
    return httpx.Response(
        200,
        json={
            "models": [
                {
                    "name": "models/gemini-3-8-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        },
    )


class TestListProviderModels:
    """Live discovery, fallbacks, and caching."""

    def setup_method(self) -> None:
        """Start each test with a cold cache."""
        clear_model_cache()

    def test_live_openai_listing_filters_and_ranks(self) -> None:
        """Non-chat models are excluded; results come from the live source."""
        transport = httpx.MockTransport(_openai_models_handler)
        payload = _run(
            list_provider_models(
                "openai", api_key="sk-test", transport=transport, refresh=True
            )
        )
        assert payload["source"] == "live"
        ids = [entry["id"] for entry in payload["models"]]
        assert "text-embedding-3-large" not in ids
        assert "whisper-1" not in ids
        assert ids[0] == "gpt-6-astra"
        assert payload["excluded_count"] >= 2

    def test_live_anthropic_listing_parses_created_at(self) -> None:
        """Anthropic ISO timestamps are converted and used for ranking."""
        transport = httpx.MockTransport(_anthropic_models_handler)
        payload = _run(
            list_provider_models(
                "anthropic", api_key="test-key", transport=transport, refresh=True
            )
        )
        assert payload["source"] == "live"
        ids = [entry["id"] for entry in payload["models"]]
        # Both flagships outrank the mid-tier Sonnet, and timestamps parsed.
        assert ids[-1] == "claude-sonnet-5"
        assert set(ids[:2]) == {"claude-fable-5-1", "claude-opus-5-5"}
        assert payload["models"][0]["created"]

    def test_live_google_listing_uses_generation_methods(self) -> None:
        """Gemini listing keeps only generateContent-capable models."""
        transport = httpx.MockTransport(_google_models_handler)
        payload = _run(
            list_provider_models(
                "gemini", api_key="AIza-test", transport=transport, refresh=True
            )
        )
        assert payload["source"] == "live"
        ids = [entry["id"] for entry in payload["models"]]
        assert ids == ["gemini-3-8-flash"]

    def test_missing_key_returns_recommended_with_message(self) -> None:
        """No configured key falls back to the vendor's recommended list."""
        payload = _run(list_provider_models("xai", api_key="", refresh=True))
        assert payload["source"] == "recommended"
        assert payload["models"]
        assert payload["message"]

    def test_http_error_returns_recommended_with_message(self) -> None:
        """Vendor failures degrade to the recommended list, never raise."""

        def _boom(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="bad key")

        transport = httpx.MockTransport(_boom)
        payload = _run(
            list_provider_models(
                "mistral", api_key="bad", transport=transport, refresh=True
            )
        )
        assert payload["source"] == "recommended"
        assert "Could not list models" in payload["message"]

    def test_cache_serves_without_refetch(self) -> None:
        """A second call within the TTL is served from cache."""
        calls = {"count": 0}

        def _counting(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            return _openai_models_handler(request)

        transport = httpx.MockTransport(_counting)
        first = _run(
            list_provider_models(
                "openai", api_key="sk-test", transport=transport, refresh=True
            )
        )
        second = _run(
            list_provider_models(
                "openai", api_key="sk-test", transport=transport, refresh=False
            )
        )
        assert first["cached"] is False
        assert second["cached"] is True
        assert calls["count"] == 1

    def test_empty_input_returns_empty(self) -> None:
        """No models means an empty result, not an error."""
        assert rank_models([]) == []
