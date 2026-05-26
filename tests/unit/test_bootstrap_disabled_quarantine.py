"""Repository policy tests for the bootstrap package."""

from pathlib import Path

from scripts.backend_structure_audit import (
    BACKEND_ROOT,
    find_bootstrap_disabled_importers,
)


def test_production_code_does_not_import_bootstrap_disabled() -> None:
    """Production package roots must not depend on the bootstrap module."""
    assert find_bootstrap_disabled_importers(BACKEND_ROOT) == []


def test_bootstrap_has_policy_document() -> None:
    """The bootstrap module should carry an explicit policy document."""
    policy_note = BACKEND_ROOT / "bootstrap" / "LEGACY.md"

    assert policy_note.exists()
    normalized = " ".join(policy_note.read_text(encoding="utf-8").split())

    assert "bootstrap module" in normalized.lower()
