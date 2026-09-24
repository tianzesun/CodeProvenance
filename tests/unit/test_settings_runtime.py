"""Regression tests for runtime application of persisted professor settings.

Covers ``_apply_runtime_settings_from_record``: saved settings must actually
take effect on the running backend (no restart), secrets must be mirrored into
the process environment, and the professor sensitivity presets must map to the
same thresholds on the backend as the settings UI advertises.
"""

import asyncio
import os
import re
from pathlib import Path

import pytest

from src.backend.api import server
from src.backend.config.settings import DEFAULT_ENGINE_WEIGHTS
from src.backend.config.settings import settings as app_settings
from src.backend.engines.scoring.professor_profiles import apply_professor_profile

SETTINGS_PAGE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "frontend"
    / "app"
    / "settings"
    / "page.tsx"
)


class TestApplyRuntimeSettingsFromRecord:
    """Persisted tenant settings must mutate the live settings object."""

    def test_non_secret_settings_are_applied_to_runtime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # monkeypatch snapshots these attributes and restores them afterwards,
        # so the runtime object is not polluted for other tests.
        for attr in (
            "DEFAULT_THRESHOLD",
            "WEBHOOK_URL",
            "SOURCE_SCAN_ENABLED",
            "DEBUG_MODE",
            "AUDIT_LOG_LEVEL",
            "EMBEDDING_BATCH_SIZE",
            "ENGINE_WEIGHTS",
        ):
            monkeypatch.setattr(app_settings, attr, getattr(app_settings, attr))

        server._apply_runtime_settings_from_record(
            {
                "default_threshold": 0.66,
                "webhook_url": "https://example.com/hook",
                "source_scan_enabled": True,
                "debug_mode": True,
                "audit_log_level": "DEBUG",
                "embedding_batch_size": 8,
                "engine_weights": {"token": 3.0, "ast": 1.0},
            }
        )

        assert app_settings.DEFAULT_THRESHOLD == pytest.approx(0.66)
        assert app_settings.WEBHOOK_URL == "https://example.com/hook"
        assert app_settings.SOURCE_SCAN_ENABLED is True
        assert app_settings.DEBUG_MODE is True
        assert app_settings.AUDIT_LOG_LEVEL == "DEBUG"
        assert app_settings.EMBEDDING_BATCH_SIZE == 8
        # _normalize_engine_weights canonicalizes keys and backfills defaults
        # for unmentioned engines; it does not rescale provided values.
        assert app_settings.ENGINE_WEIGHTS["token"] == pytest.approx(3.0)
        assert app_settings.ENGINE_WEIGHTS["ast"] == pytest.approx(1.0)
        assert (
            app_settings.ENGINE_WEIGHTS["winnowing"]
            == DEFAULT_ENGINE_WEIGHTS["winnowing"]
        )

    def test_secret_settings_mirror_to_process_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "")
        server._apply_runtime_settings_from_record(
            {"openai_api_key": "sk-runtime-test"}
        )
        assert os.environ.get("OPENAI_API_KEY") == "sk-runtime-test"
        assert app_settings.OPENAI_API_KEY == "sk-runtime-test"

    def test_empty_secret_does_not_wipe_existing_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "keep-me")
        server._apply_runtime_settings_from_record({"anthropic_api_key": ""})
        assert os.environ.get("ANTHROPIC_API_KEY") == "keep-me"

    def test_unknown_or_meta_keys_are_ignored(self) -> None:
        # v1_* keys are stored per-tenant but have no runtime attribute;
        # unknown keys must not raise.
        server._apply_runtime_settings_from_record(
            {"v1_scoring": {"review_threshold": 0.9}, "not_a_setting": 1}
        )


class TestOutboundServiceSettings:
    """Email delivery and AI-detector settings must apply and stay masked."""

    def test_email_settings_apply_to_runtime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for attr in (
            "EMAIL_BACKEND",
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_USER",
            "EMAIL_FROM",
            "EMAIL_USE_TLS",
            "EMAIL_PASSWORD",
        ):
            monkeypatch.setattr(app_settings, attr, getattr(app_settings, attr))
        monkeypatch.setenv("EMAIL_PASSWORD", "")

        server._apply_runtime_settings_from_record(
            {
                "email_backend": "smtp",
                "email_host": "smtp.example.edu",
                "email_port": 2525,
                "email_user": "mailer@example.edu",
                "email_from": "integrity@example.edu",
                "email_use_tls": False,
                "email_password": "s3cret",
            }
        )

        assert app_settings.EMAIL_BACKEND == "smtp"
        assert app_settings.EMAIL_HOST == "smtp.example.edu"
        assert app_settings.EMAIL_PORT == 2525
        assert app_settings.EMAIL_USER == "mailer@example.edu"
        assert app_settings.EMAIL_FROM == "integrity@example.edu"
        assert app_settings.EMAIL_USE_TLS is False
        # Email password is secret-like: applied to settings and mirrored to env.
        assert app_settings.EMAIL_PASSWORD == "s3cret"
        assert os.environ.get("EMAIL_PASSWORD") == "s3cret"

    def test_ai_detector_keys_mirror_to_process_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GPTZERO_API_KEY", "")
        monkeypatch.setenv("GRAMMARLY_API_KEY", "")
        monkeypatch.setattr(
            app_settings, "GPTZERO_API_KEY", app_settings.GPTZERO_API_KEY
        )
        monkeypatch.setattr(
            app_settings, "GRAMMARLY_API_KEY", app_settings.GRAMMARLY_API_KEY
        )

        server._apply_runtime_settings_from_record(
            {"gptzero_api_key": "gz-live", "grammarly_api_key": "gm-live"}
        )

        assert app_settings.GPTZERO_API_KEY == "gz-live"
        assert app_settings.GRAMMARLY_API_KEY == "gm-live"
        assert os.environ.get("GPTZERO_API_KEY") == "gz-live"
        assert os.environ.get("GRAMMARLY_API_KEY") == "gm-live"

    def test_secret_settings_are_masked_in_payload(self) -> None:
        # No tenant_id means the database is never touched.
        payload = server._build_settings_payload(None)
        assert server.SECRET_SETTING_KEYS, "expected at least one secret setting"
        for key in server.SECRET_SETTING_KEYS:
            assert payload[key] == "", f"{key} leaked in the settings payload"
            assert f"{key}_configured" in payload

    def test_new_settings_are_wired_into_attr_map(self) -> None:
        expected = {
            "gptzero_api_key": "GPTZERO_API_KEY",
            "grammarly_api_key": "GRAMMARLY_API_KEY",
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
            "gptzero_api_key",
            "grammarly_api_key",
            "email_backend",
            "email_host",
            "email_port",
            "email_user",
            "email_password",
            "email_from",
            "email_use_tls",
            "sendgrid_api_key",
        ):
            assert re.search(
                rf"\b{key}:", source
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
