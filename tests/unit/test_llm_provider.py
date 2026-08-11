"""Unit tests for the LLM provider integration (OpenAI/Anthropic over httpx).

Uses httpx.MockTransport so no real API calls are made.
"""

import json
from typing import Dict

import httpx
import pytest

from src.backend.config.settings import settings as app_settings
from src.backend.integrations.llm_provider import (
    LLMError,
    LLMProvider,
    build_evidence_prompt,
    resolve_provider_config,
    summarize_pair_evidence,
)
from src.backend.integrations.llm_provider import (
    test_provider_connection as _test_provider_connection,
)


def _openai_ok_handler(request: httpx.Request) -> httpx.Response:
    """Return a minimal OpenAI chat-completions response."""
    payload = json.loads(request.content or b"{}")
    assert request.url.path.endswith("/chat/completions")
    assert request.headers["Authorization"] == "Bearer test-openai-key"
    assert payload["model"]
    assert payload["messages"][-1]["role"] == "user"
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": "Evidence summary text"}}]},
    )


def _anthropic_ok_handler(request: httpx.Request) -> httpx.Response:
    """Return a minimal Anthropic messages response."""
    assert request.url.path.endswith("/messages")
    assert request.headers["x-api-key"] == "test-anthropic-key"
    assert request.headers["anthropic-version"] == "2023-06-01"
    return httpx.Response(
        200,
        json={"content": [{"type": "text", "text": "Evidence summary text"}]},
    )


def _error_handler(request: httpx.Request) -> httpx.Response:
    """Return a 401 so connection-testing failure paths can be exercised."""
    return httpx.Response(401, text="invalid api key")


class TestLLMProviderOpenAI:
    """OpenAI chat-completions request/response handling."""

    def test_complete_parses_content(self) -> None:
        transport = httpx.MockTransport(_openai_ok_handler)
        provider = LLMProvider(
            provider="openai",
            api_key="test-openai-key",
            model="gpt-test",
            base_url="https://example.com/v1",
            transport=transport,
        )
        assert await_provider(provider) == "Evidence summary text"


class TestLLMProviderAnthropic:
    """Anthropic messages request/response handling."""

    def test_complete_sends_expected_headers_and_parses_text_blocks(self) -> None:
        transport = httpx.MockTransport(_anthropic_ok_handler)
        provider = LLMProvider(
            provider="anthropic",
            api_key="test-anthropic-key",
            model="claude-test",
            base_url="https://api.anthropic.com/v1",
            transport=transport,
        )
        assert await_provider(provider) == "Evidence summary text"


class TestLLMProviderValidation:
    """Provider construction and config resolution."""

    def test_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError):
            LLMProvider(
                provider="gemini",
                api_key="x",
                model="m",
                base_url="https://example.com",
            )

    def test_missing_api_key_raises_llm_error(self) -> None:
        with pytest.raises(LLMError):
            LLMProvider(
                provider="openai",
                api_key="",
                model="gpt-test",
                base_url="https://example.com/v1",
            )

    def test_resolve_provider_config_rejects_unknown_provider(self) -> None:
        with pytest.raises(ValueError):
            resolve_provider_config("gemini")

    def test_resolve_provider_config_uses_override_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_settings, "OPENAI_API_KEY", "stored-key")
        config = resolve_provider_config("openai", api_key_override="override-key")
        assert config.api_key == "override-key"
        assert config.provider == "openai"

        monkeypatch.setattr(app_settings, "ANTHROPIC_API_KEY", "stored-anthropic")
        config = resolve_provider_config("anthropic")
        assert config.api_key == "stored-anthropic"
        assert config.provider == "anthropic"


class TestConnectionTesting:
    """test_provider_connection ok/failure paths."""

    def test_connection_ok(self) -> None:
        result = pytest_unwrap(
            _test_provider_connection(
                "openai",
                api_key_override="test-openai-key",
                transport=httpx.MockTransport(_openai_ok_handler),
            )
        )
        assert result["ok"] is True
        assert result["message"] == "Connected"
        assert "latency_ms" in result

    def test_connection_http_error_reports_failure(self) -> None:
        result = pytest_unwrap(
            _test_provider_connection(
                "openai",
                api_key_override="test-openai-key",
                transport=httpx.MockTransport(_error_handler),
            )
        )
        assert result["ok"] is False
        assert "Connection failed" in result["message"] or "401" in result["message"]

    def test_connection_missing_key_reports_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_settings, "OPENAI_API_KEY", None)
        result = pytest_unwrap(_test_provider_connection("openai"))
        assert result["ok"] is False
        assert "key" in result["message"].lower()


class TestEvidenceSummarization:
    """summarize_pair_evidence LLM and fallback behavior."""

    def test_uses_llm_when_key_and_transport_available(self) -> None:
        result = pytest_unwrap(
            summarize_pair_evidence(
                "def f():\n    return 1\n",
                "def g():\n    return 1\n",
                {"ast": 0.9, "fingerprint": 0.8},
                provider="openai",
                api_key_override="test-openai-key",
                transport=httpx.MockTransport(_openai_ok_handler),
            )
        )
        assert result["source"] == "llm"
        assert result["summary"] == "Evidence summary text"

    def test_uses_anthropic_provider(self) -> None:
        result = pytest_unwrap(
            summarize_pair_evidence(
                "a",
                "b",
                {"ast": 0.5},
                provider="anthropic",
                api_key_override="test-anthropic-key",
                transport=httpx.MockTransport(_anthropic_ok_handler),
            )
        )
        assert result["source"] == "llm"
        assert result["provider"] == "anthropic"

    def test_falls_back_to_heuristic_when_no_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_settings, "OPENAI_API_KEY", None)
        result = pytest_unwrap(
            summarize_pair_evidence(
                "def f():\n    return 1\n",
                "def g():\n    return 1\n",
                {"ast": 0.9},
                provider="openai",
            )
        )
        assert result["source"] == "heuristic"
        assert "ast=0.90" in result["summary"]

    def test_falls_back_to_heuristic_on_api_error(self) -> None:
        result = pytest_unwrap(
            summarize_pair_evidence(
                "a",
                "b",
                {"fingerprint": 0.4},
                provider="openai",
                api_key_override="test-openai-key",
                transport=httpx.MockTransport(_error_handler),
            )
        )
        assert result["source"] == "heuristic"
        assert "fallback_reason" in result


class TestPromptBuilder:
    """build_evidence_prompt includes features and task instructions."""

    def test_includes_feature_scores_and_files(self) -> None:
        prompt = build_evidence_prompt(
            "def f():\n    return 1\n",
            "def g():\n    return 1\n",
            {"ast": 0.91, "winnowing": 0.5},
            file_a="sub_a.py",
            file_b="sub_b.py",
        )
        assert "sub_a.py" in prompt
        assert "sub_b.py" in prompt
        assert "ast=0.910" in prompt
        assert "winnowing=0.500" in prompt

    def test_rewrite_task_adds_instruction(self) -> None:
        prompt = build_evidence_prompt("a", "b", {}, task="rewrite")
        assert "AI-assisted rewriting" in prompt


class TestSettingsEndpoints:
    """Server endpoints for provider testing and evidence summarization."""

    @staticmethod
    def _cookie_jar() -> Dict[str, str]:
        """Return a valid session cookie accepted by the auth middleware."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from src.backend.api.server import AUTH_COOKIE_NAME

        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
            app_settings.AUTH_JWT_SECRET or "unit-test-secret",
            algorithm="HS256",
        )
        return {AUTH_COOKIE_NAME: token}

    @staticmethod
    def _fake_admin(*args, **kwargs):
        return {"id": "admin-1", "role": "admin"}

    def test_ai_provider_test_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.testclient import TestClient

        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", self._fake_admin)

        async def fake_test(provider, api_key_override=None):
            return {"ok": True, "message": "Connected", "provider": provider}

        monkeypatch.setattr(
            "src.backend.integrations.llm_provider.test_provider_connection",
            fake_test,
        )
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/ai-provider/test",
            json={"provider": "openai", "api_key": "sk-test"},
            cookies=self._cookie_jar(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["provider"] == "openai"

    def test_ai_provider_test_endpoint_calls_supported_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi.testclient import TestClient

        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", self._fake_admin)
        called_with: list = []

        async def fake_test(provider, api_key_override=None):
            called_with.append((provider, api_key_override))
            return {"ok": True, "message": "Connected", "provider": provider}

        monkeypatch.setattr(
            "src.backend.integrations.llm_provider.test_provider_connection",
            fake_test,
        )
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/ai-provider/test",
            json={"provider": "anthropic", "api_key": "sk-ant-test"},
            cookies=self._cookie_jar(),
        )
        assert response.status_code == 200
        assert called_with == [("anthropic", "sk-ant-test")]

    def test_evidence_summary_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.testclient import TestClient

        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", self._fake_admin)

        async def fake_summarize(code_a, code_b, features, **kwargs):
            return {
                "summary": "The two files share structural patterns.",
                "provider": "openai",
                "source": "llm",
            }

        monkeypatch.setattr(
            "src.backend.integrations.llm_provider.summarize_pair_evidence",
            fake_summarize,
        )
        client = TestClient(server.app)
        response = client.post(
            "/api/analyze/evidence-summary",
            json={
                "code_a": "def f():\n    return 1\n",
                "code_b": "def f():\n    return 2\n",
                "features": {"ast": 0.9},
                "provider": "openai",
            },
            cookies=self._cookie_jar(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "llm"
        assert body["provider"] == "openai"

    def test_evidence_summary_endpoint_requires_both_codes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi.testclient import TestClient

        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", self._fake_admin)

        client = TestClient(server.app)
        response = client.post(
            "/api/analyze/evidence-summary",
            json={"code_a": "", "features": {}},
            cookies=self._cookie_jar(),
        )
        assert response.status_code == 400
        assert "code_a and code_b are required" in response.json()["detail"]


# ─── asyncio helpers ─────────────────────────────────────────────────


def pytest_unwrap(coro):
    """Run an async helper synchronously for tests."""
    import asyncio

    return asyncio.run(coro)


def await_provider(provider: LLMProvider) -> str:
    """Run provider.complete synchronously."""
    return pytest_unwrap(
        provider.complete("analyze this pair", system="be neutral", max_tokens=50)
    )
