"""Regression tests for runtime application of persisted professor settings.

Covers ``_apply_runtime_settings_from_record``: saved settings must actually
take effect on the running backend (no restart), secrets must be mirrored into
the process environment, and the professor sensitivity presets must map to the
same thresholds on the backend as the settings UI advertises.
"""

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
