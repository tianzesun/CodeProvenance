"""Regression tests for applying a workspace's saved settings at runtime.

Covers ``_workspace_setting_overrides``: saved settings take effect for the
workspace's own requests and jobs (no restart), without touching the shared
start-up configuration or the process environment, and the professor
sensitivity presets map to the same thresholds as the settings UI advertises.
"""

import asyncio
import contextvars
import os
import re
import threading
from pathlib import Path

import pytest

from src.backend.api import server
from src.backend.config.settings import DEFAULT_ENGINE_WEIGHTS
from src.backend.config.settings import settings as app_settings
from src.backend.config.settings import workspace_overrides
from src.backend.engines.scoring.professor_profiles import apply_professor_profile

SETTINGS_PAGE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "frontend"
    / "app"
    / "settings"
    / "page.tsx"
)


def _as_workspace(record: dict):
    return workspace_overrides(server._workspace_setting_overrides(record))


class TestWorkspaceSettingOverrides:
    """A workspace's saved settings apply to its own requests only."""

    def test_non_secret_settings_take_effect(self) -> None:
        with _as_workspace(
            {
                "default_threshold": 0.66,
                "webhook_url": "https://example.com/hook",
                "source_scan_enabled": True,
                "embedding_batch_size": 8,
                "engine_weights": {"token": 3.0, "ast": 1.0},
            }
        ):
            assert app_settings.DEFAULT_THRESHOLD == pytest.approx(0.66)
            assert app_settings.WEBHOOK_URL == "https://example.com/hook"
            assert app_settings.SOURCE_SCAN_ENABLED is True
            assert app_settings.EMBEDDING_BATCH_SIZE == 8
            # _normalize_engine_weights canonicalizes keys and backfills
            # defaults for unmentioned engines; it does not rescale.
            assert app_settings.ENGINE_WEIGHTS["token"] == pytest.approx(3.0)
            assert app_settings.ENGINE_WEIGHTS["ast"] == pytest.approx(1.0)
            assert (
                app_settings.ENGINE_WEIGHTS["winnowing"]
                == DEFAULT_ENGINE_WEIGHTS["winnowing"]
            )

    def test_the_start_up_configuration_is_untouched(self) -> None:
        before = app_settings.DEFAULT_THRESHOLD
        with _as_workspace({"default_threshold": 0.71}):
            assert app_settings.DEFAULT_THRESHOLD == pytest.approx(0.71)
        assert app_settings.DEFAULT_THRESHOLD == before

    def test_concurrent_workspaces_each_see_their_own(self) -> None:
        """Two workspaces' requests running at once never see each other's values."""
        seen: dict[str, list[float]] = {"a": [], "b": []}
        barrier = threading.Barrier(2)

        def run(name: str, threshold: float) -> None:
            with _as_workspace({"default_threshold": threshold}):
                for _ in range(50):
                    barrier.wait()
                    seen[name].append(app_settings.DEFAULT_THRESHOLD)

        threads = [
            threading.Thread(target=contextvars.copy_context().run, args=(run, n, t))
            for n, t in (("a", 0.6), ("b", 0.9))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert set(seen["a"]) == {0.6}
        assert set(seen["b"]) == {0.9}

    def test_methods_see_the_workspace_values(self) -> None:
        with _as_workspace({"llm_api_keys": {"groq": "gk-workspace"}}):
            assert app_settings.llm_api_key("groq") == "gk-workspace"

    def test_a_workspace_key_overrides_without_touching_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "server-key")
        with _as_workspace({"openai_api_key": "sk-runtime-test"}):
            assert app_settings.OPENAI_API_KEY == "sk-runtime-test"
        assert os.environ["OPENAI_API_KEY"] == "server-key"

    def test_empty_secret_keeps_the_server_key(self) -> None:
        before = app_settings.ANTHROPIC_API_KEY
        with _as_workspace({"anthropic_api_key": ""}):
            assert app_settings.ANTHROPIC_API_KEY == before

    def test_a_workspace_cannot_switch_on_debug_mode(self) -> None:
        before = app_settings.DEBUG_MODE
        with _as_workspace({"debug_mode": not before}):
            assert app_settings.DEBUG_MODE == before

    def test_unknown_or_meta_keys_are_ignored(self) -> None:
        # v1_* keys are stored per-tenant but have no runtime attribute;
        # unknown keys must not raise.
        assert (
            server._workspace_setting_overrides(
                {"v1_scoring": {"review_threshold": 0.9}, "not_a_setting": 1}
            )
            == {}
        )


class TestOutboundServiceSettings:
    """Email delivery settings must apply and stay masked."""

    def test_email_settings_take_effect(self) -> None:
        with _as_workspace(
            {
                "email_backend": "smtp",
                "email_host": "smtp.example.edu",
                "email_port": 2525,
                "email_user": "mailer@example.edu",
                "email_from": "integrity@example.edu",
                "email_use_tls": False,
                "email_password": "s3cret",
            }
        ):
            assert app_settings.EMAIL_BACKEND == "smtp"
            assert app_settings.EMAIL_HOST == "smtp.example.edu"
            assert app_settings.EMAIL_PORT == 2525
            assert app_settings.EMAIL_USER == "mailer@example.edu"
            assert app_settings.EMAIL_FROM == "integrity@example.edu"
            assert app_settings.EMAIL_USE_TLS is False
            assert app_settings.EMAIL_PASSWORD == "s3cret"

    def test_secret_settings_are_masked_in_payload(self) -> None:
        # No tenant_id means the database is never touched.
        payload = server._build_settings_payload(None)
        assert server.SECRET_SETTING_KEYS, "expected at least one secret setting"
        for key in server.SECRET_SETTING_KEYS:
            assert payload[key] == "", f"{key} leaked in the settings payload"
            assert f"{key}_configured" in payload

    def test_new_settings_are_wired_into_attr_map(self) -> None:
        expected = {
            "email_backend": "EMAIL_BACKEND",
            "email_host": "EMAIL_HOST",
            "email_port": "EMAIL_PORT",
            "email_user": "EMAIL_USER",
            "email_password": "EMAIL_PASSWORD",
            "email_from": "EMAIL_FROM",
            "email_use_tls": "EMAIL_USE_TLS",
            "sendgrid_api_key": "SENDGRID_API_KEY",
        }
        for key, attr in expected.items():
            assert server.SETTINGS_ATTR_MAP[key] == attr
            assert hasattr(app_settings, attr), f"AppSettings missing {attr}"

    def test_frontend_save_payload_includes_new_settings(self) -> None:
        source = SETTINGS_PAGE.read_text(encoding="utf-8")
        for key in (
            "email_backend",
            "email_host",
            "email_port",
            "email_user",
            "email_password",
            "email_from",
            "email_use_tls",
            "sendgrid_api_key",
        ):
            # Keys are declared either as an object property (``key:``) or as a
            # quoted entry in the key arrays (``'key',``); both reach buildPayload.
            assert re.search(rf"\b{key}\s*:", source) or re.search(
                rf"['\"]{key}['\"]", source
            ), f"{key} missing from {SETTINGS_PAGE.name}"


class TestEmailServiceRuntimeConfig:
    """The email service must honour settings saved at runtime."""

    def test_smtp_config_prefers_live_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.backend.infrastructure.email_service import EmailService

        for attr, value in (
            ("EMAIL_BACKEND", "smtp"),
            ("EMAIL_HOST", "smtp.example.edu"),
            ("EMAIL_PORT", 2525),
            ("EMAIL_USER", "mailer@example.edu"),
            ("EMAIL_PASSWORD", "s3cret"),
            ("EMAIL_FROM", "integrity@example.edu"),
            ("EMAIL_USE_TLS", True),
        ):
            monkeypatch.setattr(app_settings, attr, value)

        assert EmailService._get_backend() == "smtp"
        config = EmailService._get_smtp_config()
        assert config["host"] == "smtp.example.edu"
        assert config["port"] == 2525
        assert config["user"] == "mailer@example.edu"
        assert config["password"] == "s3cret"
        assert config["from_email"] == "integrity@example.edu"
        assert config["use_tls"] is True

    def test_console_backend_reports_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.backend.infrastructure.email_service import EmailService

        monkeypatch.setattr(app_settings, "EMAIL_BACKEND", "console")
        assert asyncio.run(EmailService.send_test_email("admin@example.edu")) is True


class TestSensitivityThresholdConsistency:
    """Backend presets must match what the settings page advertises."""

    def test_backend_sensitivity_thresholds(self) -> None:
        assert (
            apply_professor_profile({"sensitivity": "conservative"}).threshold == 0.84
        )
        assert apply_professor_profile({"sensitivity": "balanced"}).threshold == 0.75
        assert apply_professor_profile({"sensitivity": "strict"}).threshold == 0.64

    def test_frontend_sensitivity_thresholds_match_backend(self) -> None:
        source = SETTINGS_PAGE.read_text(encoding="utf-8")
        match = re.search(r"SENSITIVITY_THRESHOLDS[^{]*\{(.*?)\}", source, re.DOTALL)
        assert match, "SENSITIVITY_THRESHOLDS block not found in settings page"
        pairs = dict(
            (key, float(value))
            for key, value in re.findall(r"(\w+):\s*([\d.]+)", match.group(1))
        )
        expected = {
            "conservative": apply_professor_profile(
                {"sensitivity": "conservative"}
            ).threshold,
            "balanced": apply_professor_profile({"sensitivity": "balanced"}).threshold,
            "strict": apply_professor_profile({"sensitivity": "strict"}).threshold,
        }
        assert pairs == expected
