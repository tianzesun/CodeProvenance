"""Release security policy regression tests.

Covers the three hardening changes that gate what an unauthenticated caller
can reach:

1. Compute-heavy endpoints (upload / AI review / benchmark) require a session
   or API key unless ``ALLOW_ANONYMOUS_ANALYSIS`` is explicitly enabled.
2. The seeded development API keys require ``ALLOW_DEV_API_KEYS`` in addition to
   ``DEBUG_MODE``.
3. The interactive API docs are not served unless ``EXPOSE_API_DOCS`` is set.
"""

from src.backend.api import server
from src.backend.api.middleware import auth as auth_middleware


class TestAnalysisEndpointsRequireAuth:
    """Analysis endpoints must not be anonymously reachable by default."""

    def test_analysis_paths_are_not_exempt_by_default(self) -> None:
        for path in server.ANALYSIS_PATHS:
            assert (
                path not in server.AUTH_EXEMPT_PATHS
            ), f"{path} must not be in AUTH_EXEMPT_PATHS"
            assert (
                server._should_require_auth(path) is True
            ), f"{path} must require authentication"

    def test_auth_exempt_paths_stay_small_and_public(self) -> None:
        """The anonymous surface should only contain login/health endpoints."""
        assert server.AUTH_EXEMPT_PATHS == set(server.PUBLIC_PATHS)
        assert "/api/auth/login" in server.AUTH_EXEMPT_PATHS
        assert "/api/upload" not in server.AUTH_EXEMPT_PATHS

    def test_authentication_endpoints_remain_public(self) -> None:
        for path in ("/", "/health", "/api/auth/status", "/api/auth/login"):
            assert server._should_require_auth(path) is False

    def test_anonymous_analysis_can_be_re_enabled_explicitly(self) -> None:
        """The escape hatch works when a deployment asks for it."""
        original = server.AUTH_EXEMPT_PATHS
        try:
            server.AUTH_EXEMPT_PATHS = original | set(server.ANALYSIS_PATHS)
            assert server._should_require_auth("/api/upload") is False
            assert server._should_require_auth("/api/ai-detect") is False
        finally:
            server.AUTH_EXEMPT_PATHS = original


class TestDevApiKeysRequireExplicitOptIn:
    """Seeded dev keys need both flags, so DEBUG_MODE alone is not enough."""

    def test_keys_are_skipped_when_opt_in_is_off(self, monkeypatch) -> None:
        monkeypatch.setattr(auth_middleware.settings, "ALLOW_DEV_API_KEYS", False)
        monkeypatch.setattr(auth_middleware.settings, "DEBUG_MODE", True)
        created: list[str] = []
        monkeypatch.setattr(
            auth_middleware.api_key_manager,
            "create_key",
            lambda *args, **kwargs: created.append(kwargs.get("name", args[0])),
        )

        auth_middleware.setup_default_keys()

        assert created == []

    def test_keys_are_created_when_both_flags_are_on(self, monkeypatch) -> None:
        monkeypatch.setattr(auth_middleware.settings, "ALLOW_DEV_API_KEYS", True)
        monkeypatch.setattr(auth_middleware.settings, "DEBUG_MODE", True)
        created: list[str] = []
        monkeypatch.setattr(
            auth_middleware.api_key_manager,
            "create_key",
            lambda *args, **kwargs: created.append(kwargs["name"]),
        )

        auth_middleware.setup_default_keys()

        assert created == ["Development Key", "Demo Key"]


class TestApiDocsAreGated:
    """The OpenAPI schema documents every endpoint, so it is opt-in."""

    def test_docs_are_not_served_by_default(self) -> None:
        from fastapi.testclient import TestClient

        client = TestClient(server.app)
        assert client.get("/openapi.json").status_code in {401, 404}
        assert client.get("/docs").status_code in {401, 404}
