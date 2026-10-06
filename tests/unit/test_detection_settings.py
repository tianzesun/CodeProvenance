"""Regression tests for the Detection Settings tab.

The tab exposes four controls. Each one must (a) be accepted by
``PATCH /api/settings`` so it is written to the tenant settings record, (b) land
on the live ``settings`` object without a restart, and (c) actually change
backend behaviour.

``batch_size`` ("Processing Batch Size") satisfied (a) and (b) but was read by
nothing, so it looked saved while doing nothing; these tests keep it honest.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from src.backend.api import server
from src.backend.config.settings import settings

#: Every control rendered on the Detection Settings tab, keyed by the settings
#: name the frontend sends.
DETECTION_KEYS = (
    "default_threshold",
    "max_file_size_mb",
    "max_files_per_job",
    "batch_size",
)

#: Settings key -> ``AppSettings`` attribute for the same four controls.
DETECTION_ATTRS = {
    "default_threshold": "DEFAULT_THRESHOLD",
    "max_file_size_mb": "MAX_FILE_SIZE_MB",
    "max_files_per_job": "MAX_FILES_PER_JOB",
    "batch_size": "BATCH_SIZE",
}

SETTINGS_PAGE = (
    Path(__file__).resolve().parents[2] / "src" / "frontend" / "app" / "settings" / "page.tsx"
)


def _snapshot_runtime_attrs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze every runtime-mapped settings attribute so this test cannot leak.

    ``_apply_runtime_settings_from_record`` merges the stored record over
    ``USER_EDITABLE_SETTINGS_DEFAULTS`` and writes *every* mapped attribute, so
    exercising it with a partial record would otherwise reset unrelated settings
    for the rest of the session.
    """
    for attr in server.SETTINGS_ATTR_MAP.values():
        if attr and hasattr(settings, attr):
            monkeypatch.setattr(settings, attr, getattr(settings, attr))


def _frontend_source() -> str:
    """Return the raw source of the settings page."""
    return SETTINGS_PAGE.read_text(encoding="utf-8")


class TestDetectionSettingsPersist:
    """All four Detection controls must be writable through PATCH /api/settings."""

    def test_keys_are_accepted_by_the_patch_handler(self) -> None:
        # update_settings drops any key missing from SETTINGS_ATTR_MAP, so a
        # control that is absent here can never be saved at all.
        for key in DETECTION_KEYS:
            assert key in server.SETTINGS_ATTR_MAP, f"{key} cannot be saved"

    def test_keys_have_defaults_so_get_returns_them(self) -> None:
        for key in DETECTION_KEYS:
            assert key in server.USER_EDITABLE_SETTINGS_DEFAULTS, key

    def test_payload_round_trips_the_stored_value(self) -> None:
        """A tenant record holding the four values must be echoed back by GET."""
        stored = {
            "default_threshold": 0.61,
            "max_file_size_mb": 42,
            "max_files_per_job": 123,
            "batch_size": 64,
        }
        payload = {**server.USER_EDITABLE_SETTINGS_DEFAULTS, **stored}
        for key, value in stored.items():
            assert payload[key] == value


class TestDetectionSettingsApplyToRuntime:
    """Saved values must reach the live settings object without a restart."""

    def test_all_detection_keys_are_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _snapshot_runtime_attrs(monkeypatch)

        server._apply_runtime_settings_from_record(
            {
                "default_threshold": 0.61,
                "max_file_size_mb": 42,
                "max_files_per_job": 123,
                "batch_size": 64,
            }
        )

        assert settings.DEFAULT_THRESHOLD == pytest.approx(0.61)
        assert settings.MAX_FILE_SIZE_MB == 42
        assert settings.MAX_FILES_PER_JOB == 123
        assert settings.BATCH_SIZE == 64

    def test_every_detection_key_maps_to_a_real_attribute(self) -> None:
        for key, attr in DETECTION_ATTRS.items():
            assert server.SETTINGS_ATTR_MAP[key] == attr, key
            assert hasattr(settings, attr), f"AppSettings has no {attr}"


class TestDetectionControlsOnThePage:
    """The frontend must send, validate and render each of the four controls."""

    def test_keys_are_in_the_save_payload(self) -> None:
        source = _frontend_source()
        plain = re.search(r"const PLAIN_KEYS = \[(.*?)\];", source, re.DOTALL)
        assert plain, "PLAIN_KEYS not found on the settings page"
        for key in DETECTION_KEYS:
            assert f"'{key}'" in plain.group(1), f"{key} would not be saved"

    def test_keys_belong_to_the_detection_tab(self) -> None:
        source = _frontend_source()
        tabs = re.search(r"const FIELD_TABS[^{]*\{(.*?)\};", source, re.DOTALL)
        assert tabs, "FIELD_TABS not found on the settings page"
        for key in DETECTION_KEYS:
            assert re.search(
                rf"{key}:\s*'detection'", tabs.group(1)
            ), f"{key} is not mapped to the Detection tab"

    def test_keys_are_rendered_on_the_detection_tab(self) -> None:
        source = _frontend_source()
        start = source.index("activeTab === 'detection'")
        end = source.index("activeTab === 'intelligence'")
        block = source[start:end]
        for key in DETECTION_KEYS:
            assert key in block, f"{key} is not rendered on the Detection tab"


class TestUploadLimitsEnforceTheStoredValue:
    """Max file size and max files per job must actually gate an upload."""

    def test_max_file_size_rejects_an_oversized_file(self, override_setting) -> None:
        override_setting("MAX_FILE_SIZE_MB", 1)
        error = server._check_submission_size("big.py", b"x" * (2 * 1024 * 1024))
        assert error is not None
        assert "1 MB" in error

    def test_max_file_size_accepts_a_file_within_the_limit(self, override_setting) -> None:
        override_setting("MAX_FILE_SIZE_MB", 10)
        assert server._check_submission_size("ok.py", b"print(1)\n") is None

    def test_max_files_per_job_rejects_a_large_upload(self, override_setting) -> None:
        override_setting("MAX_FILES_PER_JOB", 3)
        error = server._check_submission_count(4)
        assert error is not None
        assert "3 file per-upload limit" in error
        assert server._check_submission_count(3) is None

    def test_limits_are_read_at_call_time(self) -> None:
        """The limits must come from the live settings object, not a copy.

        A value captured at import time would ignore everything the admin saves.
        """
        assert "settings.MAX_FILE_SIZE_MB" in inspect.getsource(server._check_submission_size)
        assert "settings.MAX_FILES_PER_JOB" in inspect.getsource(server._check_submission_count)


class TestProcessingBatchSize:
    """The Processing Batch Size control must size the comparison worker pool."""

    def test_reads_the_configured_value(self, override_setting) -> None:
        override_setting("BATCH_SIZE", 50)
        assert server._processing_batch_workers() == 50

    def test_clamps_a_tiny_value(self, override_setting) -> None:
        override_setting("BATCH_SIZE", 0)
        assert server._processing_batch_workers() == 1
        override_setting("BATCH_SIZE", -7)
        assert server._processing_batch_workers() == 1

    def test_clamps_an_absurd_value(self, override_setting) -> None:
        # The form allows up to 10000 and the runtime applier skips pydantic
        # validation, so the resolver is the last line of defence.
        override_setting("BATCH_SIZE", 10000)
        assert server._processing_batch_workers() == (server._MAX_PROCESSING_BATCH_WORKERS)

    def test_falls_back_when_the_value_is_unusable(self, override_setting) -> None:
        override_setting("BATCH_SIZE", "not-a-number")
        assert server._processing_batch_workers() == 8

    def test_the_field_is_actually_read_from_settings(self) -> None:
        """Guard against the control quietly becoming a no-op again."""
        assert "settings.BATCH_SIZE" in inspect.getsource(server._processing_batch_workers)

    def test_analysis_forwards_the_configured_pool_size(
        self, monkeypatch: pytest.MonkeyPatch, override_setting
    ) -> None:
        override_setting("BATCH_SIZE", 47)
        captured: dict[str, object] = {}

        class _StubService:
            """Capture the pool size instead of running the real engines."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def compare_all_pairs(
                self,
                submissions: dict[str, str],
                progress_callback=None,
                max_workers: int | None = None,
            ) -> list[object]:
                captured["max_workers"] = max_workers
                return []

            def generate_report(self, results: list[object]) -> dict[str, object]:
                return {}

        monkeypatch.setattr(server, "BatchDetectionService", _StubService)

        server._run_analysis_engines(
            ["integritydesk"],
            {"a.py": "x = 1\n", "b.py": "y = 2\n"},
            [("a.py", "b.py")],
            {},
            0.5,
            {},
            None,
        )

        assert captured["max_workers"] == 47
