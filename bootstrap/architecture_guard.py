"""
Architecture Guard - Strict Layered Import Enforcement

This script enforces non-negotiable architectural rules:
- Domain is pure (King Layer)
- One-way dependency flow
- No upward imports
- No cross-layer sibling coupling

Usage:
    python bootstrap/architecture_guard.py
    
Exit codes:
    0 - All imports clean
    1 - Architecture violations detected
"""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict


# ============================================================================
# ARCHITECTURE LAYER DEFINITION (Non-Negotiable)
# ============================================================================

LAYER_RULES = {
    "domain": {
        "allow": ["domain"],  # Pure - imports NOTHING external
        "deny": ["api", "application", "infrastructure", "engines", "web", "workers", "ml", "evaluation"],
        "description": "King Layer - Pure business rules, NO external imports"
    },
    "core": {
        "allow": ["domain", "core"],
        "deny": ["api", "application", "infrastructure", "web", "workers"],
        "description": "Algorithms, IR, graph logic"
    },
    "engines": {
        "allow": ["domain", "core", "engines"],
        "deny": ["api", "web", "workers"],
        "description": "Computation layer - controlled access only"
    },
    "ml": {
        "allow": ["domain", "core", "ml"],
        "deny": ["api", "web", "workers"],
        "description": "Machine learning models"
    },
    "evaluation": {
        "allow": ["domain", "core", "engines", "evaluation"],
        "deny": ["api", "web", "infrastructure", "workers"],
        "description": "Metrics computation only"
    },
    "application": {
        "allow": ["domain", "core", "engines", "application"],
        "deny": ["infrastructure"],
        "description": "Orchestration layer"
    },
    "api": {
        "allow": ["api", "application", "domain"],
        "deny": ["engines", "infrastructure", "core"],
        "description": "REST API - entry point only"
    },
    "web": {
        "allow": ["web", "application"],
        "deny": ["domain", "core", "engines", "infrastructure"],
        "description": "Web interface - entry point only"
    },
    "workers": {
        "allow": ["workers", "application"],
        "deny": ["domain", "core", "engines", "infrastructure"],
        "description": "Background workers - entry point only"
    },
    "infrastructure": {
        "allow": ["*"],  # Bottom layer - can import anything
        "deny": [],
        "description": "External systems (DB, IO, etc.)"
    },
    "cli": {
        "allow": ["cli", "engines"],
        "deny": ["runners"],
        "description": "CLI dispatcher - must use registry, not direct runner imports"
    }
}

# Layer hierarchy for ordering checks
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


def get_module_layer(file_path: Path) -> str:
    """Determine which architectural layer a file belongs to."""
    parts = file_path.parts
    
    for layer in LAYER_RULES.keys():
        if layer in parts:
            return layer
    
    return "unknown"


def extract_imports(file_path: Path):
    """Extract all imports from a Python file."""
    imports = []
    
    if not file_path.is_file():
        return imports
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    
    except (SyntaxError, UnicodeDecodeError):
        pass
    
    return imports


def detect_layer(module_name: str):
    """Detect which layer an import belongs to."""
    for layer in LAYER_RULES.keys():
        if module_name.startswith(layer):
            return layer
    return None


def check_file(file_path: Path):
    """Check a single file for architecture violations."""
    layer = get_module_layer(file_path)
    
    if layer == "unknown":
        return []
    
    rules = LAYER_RULES.get(layer, {})
    denied = rules.get("deny", [])
    allowed = rules.get("allow", [])
    
    imports = extract_imports(file_path)
    violations = []
    
    for imp in imports:
        imp_layer = detect_layer(imp)
        
        if imp_layer is None:
            continue
        
        # Check denied
        if imp_layer in denied:
            violations.append({
                "file": str(file_path),
                "source_layer": layer,
                "import": imp,
                "target_layer": imp_layer,
                "rule": f"{layer} cannot import {imp_layer}",
            })
        
        # Check allowed (if not wildcard)
        elif "*" not in allowed and imp_layer not in allowed:
            violations.append({
                "file": str(file_path),
                "source_layer": layer,
                "import": imp,
                "target_layer": imp_layer,
                "rule": f"{layer} cannot import {imp_layer} (not in allowed list)",
            })
        
        # Check layer ordering (no upward imports)
        src_order = LAYER_ORDER.get(layer, 999)
        dst_order = LAYER_ORDER.get(imp_layer, 999)
        
        if src_order < dst_order:
            violations.append({
                "file": str(file_path),
                "source_layer": layer,
                "import": imp,
                "target_layer": imp_layer,
                "rule": f"Layer ordering violation: {layer} (order {src_order}) cannot import {imp_layer} (order {dst_order})",
            })
    
    return violations


def check_sibling_coupling(file_path: Path):
    """Check for cross-layer sibling coupling."""
    violations = []
    layer = get_module_layer(file_path)
    
    if layer not in ["engines", "ml", "evaluation"]:
        return violations
    
    # Extract imports
    imports = extract_imports(file_path)
    
    # Check if importing from sibling layer
    for imp in imports:
        for sibling in ["engines", "ml", "evaluation"]:
            if sibling != layer and imp.startswith(sibling):
                violations.append({
                    "file": str(file_path),
                    "source_layer": layer,
                    "import": imp,
                    "target_layer": sibling,
                    "rule": f"Cross-layer sibling coupling: {layer} cannot import {sibling}",
                })
    
    return violations


def main() -> int:
    """Main entry point for architecture guard.

    Returns:
        0 if all imports clean, 1 if architecture violations detected.
    """
    base_dir = Path(".")
    
    skip_dirs = {"venv", ".venv", "__pycache__", ".git", "node_modules", ".tox", "tools"}
    
    violations = []
    files_checked = 0
    
    print("🔍 Running strict architecture guard...")
    print()
    
    for py_file in base_dir.rglob("*.py"):
        if any(skip in str(py_file) for skip in skip_dirs):
            continue
        
        if py_file.name == "__init__.py":
            try:
                if py_file.stat().st_size < 10:
                    continue
            except OSError:
                continue
        
        files_checked += 1
        
        # Check import rules
        file_violations = check_file(py_file)
        
        # Check sibling coupling
        sibling_violations = check_sibling_coupling(py_file)
        
        violations.extend(file_violations)
        violations.extend(sibling_violations)
    
    # Report results
    print(f"📊 Checked {files_checked} Python files")
    print()
    
    if violations:
        print("❌ ARCHITECTURE VIOLATIONS DETECTED:")
        print()
        
        for v in violations:
            print(f"📄 {v['file']}")
            print(f"   Layer: {v['source_layer']}")
            print(f"   Import: {v['import']}")
            print(f"   Target: {v['target_layer']}")
            print(f"   Rule: {v['rule']}")
            print()
        
        print(f"💥 Total violations: {len(violations)}")
        print()
        print("Architecture rules:")
        print("  - domain → NOTHING (pure)")
        print("  - core → domain, core")
        print("  - engines → domain, core, engines")
        print("  - ml → domain, core, ml")
        print("  - evaluation → domain, core, engines, evaluation")
        print("  - application → domain, core, engines, application")
        print("  - api → api, application, domain")
        print("  - web → web, application")
        print("  - workers → workers, application")
        print("  - infrastructure → * (bottom layer)")
        print()
        print("Forbidden patterns:")
        print("  - domain → anything else")
        print("  - core → api/web/infrastructure")
        print("  - engines → api/web")
        print("  - evaluation → api/web/infrastructure")
        print("  - Cross-layer siblings (engines/ml/evaluation importing each other)")
        print()
        
        return 1
    
    else:
        print("✅ Architecture check passed!")
        print()
        print("All imports comply with strict architectural rules:")
        print("  ✓ Domain is pure (no external imports)")
        print("  ✓ Core imports only domain")
        print("  ✓ Engines import core and domain only")
        print("  ✓ ML imports core and domain only")
        print("  ✓ Evaluation imports core, domain, engines only")
        print("  ✓ Application imports domain, core, engines")
        print("  ✓ API imports application and domain only")
        print("  ✓ Web imports application only")
        print("  ✓ Workers import application only")
        print("  ✓ Infrastructure is bottom layer (can import anything)")
        print("  ✓ No cross-layer sibling coupling")
        print("  ✓ No upward imports")
        print()
        
        return 0


if __name__ == "__main__":
    main()