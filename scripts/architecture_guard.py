#!/usr/bin/env python3
"""Architecture guard CLI - validates layer boundaries.

This script is the entry point for CI. It performs AST-based validation.
"""
import ast
import sys
from pathlib import Path

# Layer rules matching src/backend/bootstrap/architecture_guard.py
_ALLOWED = {
    "domain": {"deny": ["api", "application", "infrastructure", "engines", "web", "workers", "ml", "evaluation"]},
    "core": {"deny": ["api", "application", "infrastructure", "web", "workers"]},
    "engines": {"deny": ["api", "web", "workers"]},
    "ml": {"deny": ["api", "web", "workers"]},
    "evaluation": {"deny": ["api", "web", "infrastructure", "workers"]},
    "application": {"deny": ["infrastructure"]},
    "api": {"deny": ["engines", "infrastructure", "core"]},
    "web": {"deny": ["domain", "core", "engines", "infrastructure"]},
    "workers": {"deny": ["domain", "core", "engines", "infrastructure"]},
    "infrastructure": {"deny": []},
    "cli": {"deny": ["runners"]},
    "bootstrap": {"deny": []},  # Bootstrap is entry layer
}


def _get_module_layer(file_path: Path) -> str:
    """Determine which architectural layer a file belongs to."""
    for layer in _ALLOWED:
        if layer in file_path.parts:
            return layer
    return "unknown"


def _detect_layer(module_name: str) -> str:
    """Detect which layer an import belongs to."""
    for layer in _ALLOWED:
        if module_name.startswith(layer):
            return layer
    return None


def validate_all() -> int:
    """Validate architecture across all Python files.

    Returns:
        0 if all imports clean, 1 if violations detected.
    """
    base_dir = Path(__file__).resolve().parent.parent
    skip_dirs = {"venv", ".venv", "__pycache__", ".git", "node_modules", ".tox", "tools"}
    violations = []
    files_checked = 0

    for py_file in base_dir.rglob("*.py"):
        if any(skip in str(py_file) for skip in skip_dirs):
            continue
        if py_file.stat().st_size < 10:
            continue

        files_checked += 1
        layer = _get_module_layer(py_file)
        if layer == "unknown":
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            import_name = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_name = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_name = node.module

            if import_name:
                imp_layer = _detect_layer(import_name)
                if imp_layer and imp_layer in _ALLOWED.get(layer, {}).get("deny", []):
                    violations.append({"file": str(py_file), "layer": layer, "import": import_name})

    print(f"🔍 Architecture guard checked {files_checked} Python files")

    if violations:
        print("❌ ARCHITECTURE VIOLATIONS DETECTED:")
        for v in violations[:10]:  # Show first 10
            print(f"  {v['file']}: {v['layer']} imports forbidden {v['import']}")
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")
        return 1

    print("✅ Architecture check passed!")
    return 0


def main() -> int:
    """Run architecture guard validation."""
    return validate_all()


if __name__ == "__main__":
    raise SystemExit(main())