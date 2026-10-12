"""Unit tests for the system-status overview (no real services touched)."""

import asyncio
import sys
from types import SimpleNamespace

import httpx
import pytest

from src.backend.config.settings import settings as app_settings
from src.backend.integrations import system_status
from src.backend.integrations.system_status import (
    _describe_database_url,
    check_database,
    check_embedding,
    check_gpu,
    check_llm_provider,
    check_storage,
    collect_system_status,
)


def run(coro):
    """Run an async helper synchronously for tests."""
    return asyncio.run(coro)


class _FakeDB:
    """Minimal stand-in for a SQLAlchemy session."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def execute(self, *args, **kwargs):
        """Mirror ``Session.execute`` for the ``SELECT 1`` probe."""
        if self.fail:
            raise RuntimeError("connection refused")


class _FakeSession:
    """Context-manager stand-in for ``SessionLocal()``."""

    def __init__(self, fail: bool = False) -> None:
        self.db = _FakeDB(fail)

    def __enter__(self):
        return self.db

    def __exit__(self, *args):
        return False


def _embedding_ok_handler(request: httpx.Request) -> httpx.Response:
    """Mimic the embedding server's ``GET /health``."""
    assert request.url.path == "/health"
    return httpx.Response(
        200,
        json={"status": "healthy", "model": "unixcoder", "model_loaded": True},
    )


def _refused_handler(request: httpx.Request) -> httpx.Response:
    """Simulate an unreachable service."""
    raise httpx.ConnectError("connection refused")


class TestDescribeDatabaseUrl:
    """Database descriptions never leak credentials."""

    def test_masks_password(self) -> None:
        """Test that passwords are stripped from the description."""
        described = _describe_database_url("postgresql://user:s3cret@dbhost/appdb")
        assert "s3cret" not in described
        assert "dbhost" in described

    def test_handles_sqlite(self) -> None:
        """Test that file-based URLs still describe the target."""
        described = _describe_database_url("sqlite:////tmp/test.db")
        assert "test.db" in described


class TestCheckDatabase:
    """Database probe ok/failure paths."""

    def test_up_on_select_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a working database reports up with latency."""
        monkeypatch.setattr(system_status, "SessionLocal", lambda: _FakeSession())
        result = run(check_database())
        assert result["status"] == "up"
        assert result["verified"] is True
        assert result["latency_ms"] >= 0

    def test_down_on_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a refused connection reports down, not an exception."""
        monkeypatch.setattr(
            system_status, "SessionLocal", lambda: _FakeSession(fail=True)
        )
        result = run(check_database())
        assert result["status"] == "down"
        assert "refused" in result["detail"]


class TestCheckEmbedding:
    """Embedding probe server/local/disabled paths."""

    def test_server_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a healthy embedding server reports up with its model."""
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_URL", "http://emb:8001/v1")
        result = run(
            check_embedding(transport=httpx.MockTransport(_embedding_ok_handler))
        )
        assert result["status"] == "up"
        assert result["verified"] is True
        assert "unixcoder" in result["detail"]

    def test_server_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an unreachable server reports down."""
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_URL", "http://emb:8001/v1")
        result = run(check_embedding(transport=httpx.MockTransport(_refused_handler)))
        assert result["status"] == "down"

    def test_local_runtime_reports_config_unverified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a local runtime reports config without a live probe."""
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_URL", None)
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_HOST", None)
        monkeypatch.setattr(app_settings, "EMBEDDING_RUNTIME", "local_unixcoder")
        monkeypatch.setattr(app_settings, "EMBEDDING_MODEL", "microsoft/unixcoder-base")
        result = run(check_embedding())
        assert result["status"] == "up"
        assert result["verified"] is False
        assert "unixcoder" in result["detail"]

    def test_disabled_runtime_is_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a disabled runtime reports unconfigured."""
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_URL", None)
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_HOST", None)
        monkeypatch.setattr(app_settings, "EMBEDDING_RUNTIME", "none")
        result = run(check_embedding())
        assert result["status"] == "unconfigured"


class TestCheckLlmProvider:
    """LLM probe live/unconfigured/down mapping."""

    def test_live_listing_is_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a live model listing reports up without exposing keys."""

        async def fake_list(*args, **kwargs):
            return {
                "source": "live",
                "models": [{"id": "qwen3:8b"}],
                "available_count": 4,
                "message": "",
            }

        monkeypatch.setattr(system_status, "list_provider_models", fake_list)
        monkeypatch.setattr(app_settings, "LLM_MODEL_OVERRIDES", {"ollama": "qwen3:8b"})
        monkeypatch.setattr(app_settings, "LLM_API_KEYS", {})
        result = run(check_llm_provider("ollama"))
        assert result["status"] == "up"
        assert result["verified"] is True
        assert result["models_available"] == 4
        assert "api_key" not in result

    def test_missing_key_is_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a keyed provider without a key reports unconfigured."""

        async def fake_list(*args, **kwargs):
            return {
                "source": "recommended",
                "models": [],
                "available_count": 0,
                "message": "No OpenAI API key configured yet.",
            }

        monkeypatch.setattr(system_status, "list_provider_models", fake_list)
        monkeypatch.setattr(app_settings, "LLM_API_KEYS", {})
        result = run(check_llm_provider("openai"))
        assert result["status"] == "unconfigured"
        assert "key" in result["detail"].lower()

    def test_unreachable_vendor_is_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a listing failure reports down with the vendor message."""

        async def fake_list(*args, **kwargs):
            return {
                "source": "recommended",
                "models": [],
                "available_count": 0,
                "message": "Could not list models from Ollama (local): refused",
            }

        monkeypatch.setattr(system_status, "list_provider_models", fake_list)
        monkeypatch.setattr(app_settings, "LLM_MODEL_OVERRIDES", {"ollama": "qwen3:8b"})
        result = run(check_llm_provider("ollama"))
        assert result["status"] == "down"
        assert "refused" in result["detail"]


class TestCheckGpu:
    """GPU probe paths with and without CUDA."""

    def test_reports_cuda_when_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a CUDA device reports up with its name and memory."""
        cuda = SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 2,
            get_device_name=lambda index: "NVIDIA A100",
            mem_get_info=lambda index: (40_000_000_000, 80_000_000_000),
        )
        fake_torch = SimpleNamespace(
            __version__="2.2.1",
            version=SimpleNamespace(cuda="12.1"),
            cuda=cuda,
        )
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        result = check_gpu()
        assert result["status"] == "up"
        assert "A100" in result["detail"]
        assert "free" in result["detail"]

    def test_reports_down_without_cuda(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a CUDA build with no visible device names the cause."""
        cuda = SimpleNamespace(is_available=lambda: False)
        fake_torch = SimpleNamespace(
            __version__="2.2.1+cu121",
            version=SimpleNamespace(cuda="12.1"),
            cuda=cuda,
        )
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setattr(
            system_status,
            "_nvidia_smi_summary",
            lambda: "OS sees 1 GPU (NVIDIA A100) · driver 550.54",
        )
        result = check_gpu()
        assert result["status"] == "down"
        assert "no device visible" in result["detail"]
        assert "A100" in result["detail"]

    def test_cpu_only_build_says_reinstall(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a CPU-only torch build points at the wheel."""
        cuda = SimpleNamespace(is_available=lambda: False)
        fake_torch = SimpleNamespace(
            __version__="2.2.1+cpu",
            version=SimpleNamespace(cuda=None),
            cuda=cuda,
        )
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setattr(
            system_status, "_nvidia_smi_summary", lambda: "nvidia-smi not found"
        )
        result = check_gpu()
        assert result["status"] == "down"
        assert "CPU-only torch build" in result["detail"]


class TestCheckStorage:
    """Disk-space probe paths."""

    def test_reports_free_space(self, tmp_path) -> None:
        """Test that an existing directory reports free space."""
        result = check_storage(str(tmp_path))
        assert result["status"] == "up"
        assert "GB free" in result["detail"]

    def test_missing_directory_is_down(self) -> None:
        """Test that an unreadable directory reports down."""
        result = check_storage("/nonexistent-codeprovenance-dir-xyz")
        assert result["status"] == "down"


class TestCollectSystemStatus:
    """Aggregate overview shape and worst-of status."""

    def test_collects_all_services(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Test that the overview contains every service with a timestamp."""
        monkeypatch.setattr(system_status, "SessionLocal", lambda: _FakeSession())
        monkeypatch.setattr(app_settings, "EMBEDDING_SERVER_URL", "http://emb:8001/v1")
        monkeypatch.setattr(app_settings, "LLM_PROVIDER", "ollama")
        monkeypatch.setattr(app_settings, "LLM_FALLBACK_PROVIDER", "")
        monkeypatch.setattr(app_settings, "LLM_API_KEYS", {})
        monkeypatch.setattr(app_settings, "LLM_MODEL_OVERRIDES", {"ollama": "qwen3:8b"})
        # Deterministic GPU result regardless of the machine running the test.
        cuda = SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 1,
            get_device_name=lambda index: "NVIDIA Test GPU",
            mem_get_info=lambda index: (10_000_000_000, 20_000_000_000),
        )
        monkeypatch.setitem(
            sys.modules, "torch", SimpleNamespace(__version__="2.2.1", cuda=cuda)
        )

        async def fake_list(*args, **kwargs):
            return {
                "source": "live",
                "models": [{"id": "qwen3:8b"}],
                "available_count": 4,
                "message": "",
            }

        monkeypatch.setattr(system_status, "list_provider_models", fake_list)

        def fake_health(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return _embedding_ok_handler(request)
            raise httpx.ConnectError("refused")

        result = run(
            collect_system_status(
                reports_dir=str(tmp_path),
                transport=httpx.MockTransport(fake_health),
            )
        )
        assert result["status"] == "up"
        assert set(result["services"]) == {
            "database",
            "embedding",
            "llm",
            "gpu",
            "storage",
        }
        assert result["services"]["llm"]["providers"][0]["provider"] == "ollama"
        assert "checked_at" in result


class TestSystemStatusEndpoint:
    """The admin-only status endpoint serves the overview payload."""

    @staticmethod
    def _cookie_jar() -> dict[str, str]:
        """Return a valid session cookie accepted by the auth middleware."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from src.backend.api.server import AUTH_COOKIE_NAME

        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
            app_settings.auth_jwt_secret or "unit-test-secret",
            algorithm="HS256",
        )
        return {AUTH_COOKIE_NAME: token}

    @staticmethod
    def _fake_admin(*args, **kwargs):
        return {"id": "admin-1", "role": "admin"}

    def test_status_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that GET /api/system/status returns every service."""
        from fastapi.testclient import TestClient

        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", self._fake_admin)

        async def fake_collect(**kwargs):
            return {
                "checked_at": "2026-01-01T00:00:00+00:00",
                "status": "up",
                "services": {
                    "database": {"status": "up", "label": "Database"},
                    "embedding": {"status": "up", "label": "Embeddings"},
                    "llm": {"status": "up", "label": "LLM", "providers": []},
                    "gpu": {"status": "up", "label": "GPU"},
                    "storage": {"status": "up", "label": "Storage"},
                },
            }

        monkeypatch.setattr(
            "src.backend.integrations.system_status.collect_system_status",
            fake_collect,
        )
        client = TestClient(server.app)
        response = client.get("/api/system/status", cookies=self._cookie_jar())
        assert response.status_code == 200
        body = response.json()
        assert set(body["services"]) == {
            "database",
            "embedding",
            "llm",
            "gpu",
            "storage",
        }
