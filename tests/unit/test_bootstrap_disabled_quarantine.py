"""Repository policy tests for the quarantined legacy bootstrap package."""

from pathlib import Path

from scripts.backend_structure_audit import (
    BACKEND_ROOT,
    find_bootstrap_disabled_importers,
)


def test_production_code_does_not_import_bootstrap_disabled() -> None:
    """Production package roots must not depend on the legacy bootstrap area."""
    assert find_bootstrap_disabled_importers(BACKEND_ROOT) == []


def test_bootstrap_disabled_has_legacy_notice() -> None:
    """The legacy package should carry an explicit quarantine notice."""
    legacy_note = BACKEND_ROOT / "bootstrap_disabled" / "LEGACY.md"

    assert legacy_note.exists()
    normalized = " ".join(legacy_note.read_text(encoding="utf-8").split())

    assert "must not be used by active production code" in normalized
