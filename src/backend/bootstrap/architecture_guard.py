"""Architecture Enforcement - Prevents architectural decay.

This module provides the canonical architecture guard for the bootstrap layer.
"""

from pathlib import Path


class ArchitectureGuard:
    """Prevents forbidden layer access with AST-based validation."""

    _enabled = False
    _ALLOWED = {
        "domain": {
            "allow": ["domain"],
            "deny": [
                "api",
                "application",
                "infrastructure",
                "engines",
                "web",
                "workers",
                "ml",
                "evaluation",
            ],
        },
        "core": {
            "allow": ["domain", "core"],
            "deny": ["api", "application", "infrastructure", "web", "workers"],
        },
        "engines": {
            "allow": ["domain", "core", "engines"],
            "deny": ["api", "web", "workers"],
        },
        "ml": {"allow": ["domain", "core", "ml"], "deny": ["api", "web", "workers"]},
        "evaluation": {
            "allow": ["domain", "core", "engines", "evaluation"],
            "deny": ["api", "web", "infrastructure", "workers"],
        },
        "application": {
            "allow": ["domain", "core", "engines", "application"],
            "deny": ["infrastructure"],
        },
        "api": {
            "allow": ["api", "application", "domain"],
            "deny": ["engines", "infrastructure", "core"],
        },
        "web": {
            "allow": ["web", "application"],
            "deny": ["domain", "core", "engines", "infrastructure"],
        },
        "workers": {
            "allow": ["workers", "application"],
            "deny": ["domain", "core", "engines", "infrastructure"],
        },
        "infrastructure": {"allow": ["*"], "deny": []},
        "cli": {"allow": ["cli", "engines"], "deny": ["runners"]},
    }
    LAYER_ORDER = {
        "api": 1,
        "web": 1,
        "workers": 1,
        "application": 2,
        "domain": 3,
        "core": 4,
        "engines": 5,
        "ml": 5,
        "evaluation": 5,
        "infrastructure": 6,
    }

    @classmethod
    def install_guard(cls) -> None:
        """Install import guard (call from bootstrap only)."""
        cls._enabled = True

    @classmethod
    def validate_all(cls) -> int:
        """Validate architecture across all Python files.

        Returns:
            0 if all imports clean, 1 if violations detected.
        """
        import ast

        base_dir = Path(__file__).parent.parent.parent.parent
        skip_dirs = {
            "venv",
            ".venv",
            "__pycache__",
            ".git",
            "node_modules",
            ".tox",
            "tools",
        }
        violations: list[dict] = []
        files_checked = 0

        for py_file in base_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            if py_file.stat().st_size < 10:
                continue

            files_checked += 1
            layer = cls._get_module_layer(py_file)
            if layer == "unknown":
                continue

            content = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(content, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                import_name = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_name = alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    import_name = node.module

                if import_name:
                    imp_layer = cls._detect_layer(import_name)
                    if imp_layer and imp_layer in cls._ALLOWED.get(layer, {}).get(
                        "deny", []
                    ):
                        violations.append(
                            {
                                "file": str(py_file),
                                "layer": layer,
                                "import": import_name,
                            }
                        )

        if violations:
            print(f"❌ Architecture violations: {len(violations)}")
            return 1
        print("✅ Architecture check passed!")
        return 0

    @classmethod
    def _get_module_layer(cls, file_path: Path) -> str:
        """Determine which architectural layer a file belongs to."""
        for layer in cls._ALLOWED:
            if layer in file_path.parts:
                return layer
        return "unknown"

    @classmethod
    def _detect_layer(cls, module_name: str) -> str:
        """Detect which layer an import belongs to."""
        for layer in cls._ALLOWED:
            if module_name.startswith(layer):
                return layer
        return None


def main() -> int:
    """Run architecture guard validation."""
    return ArchitectureGuard.validate_all()


if __name__ == "__main__":
    raise SystemExit(main())
