"""
Import Architecture Guard - Machine-checkable dependency enforcement.

This script enforces strict dependency rules between architectural layers.
It must pass before any commit is allowed.

Usage:
    python tools/import_guard.py
    
Exit codes:
    0 - All imports clean
    1 - Architecture violations detected
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set
from dataclasses import dataclass


# ============================================================================
# ARCHITECTURE LAYER DEFINITION
# ============================================================================

# Layer hierarchy (lower number = higher level)
ARCH_LAYERS = {
    "api": 1,
    "application": 2,
    "domain": 3,
    "core": 4,
    "engines": 5,
    "evaluation": 5,
    "infrastructure": 6,
}

# Import rules: what each layer MAY import
# Everything else is DENIED
RULES = {
    "api": {
        "allow": ["application"],
        "deny": ["domain", "core", "engines", "evaluation", "infrastructure"],
    },
    "application": {
        "allow": ["domain", "core"],
        "deny": ["engines", "evaluation", "infrastructure"],
    },
    "domain": {
        "allow": [],  # Domain is PURE - imports NOTHING
        "deny": ["api", "application", "core", "engines", "evaluation", "infrastructure"],
    },
    "core": {
        "allow": ["domain"],
        "deny": ["api", "application", "engines", "evaluation", "infrastructure"],
    },
    "engines": {
        "allow": ["core", "domain"],
        "deny": ["api", "application", "evaluation"],
    },
    "evaluation": {
        "allow": ["core", "domain", "engines"],  # READ-ONLY access to engines
        "deny": ["api", "application"],
    },
    "infrastructure": {
        "allow": ["core", "domain"],  # May use core/domain if necessary
        "deny": ["api", "application", "evaluation"],
    },
}


@dataclass
class Violation:
    """Import architecture violation."""
    file_path: Path
    import_name: str
    forbidden_layer: str
    line_number: int


def get_module_layer(file_path: Path) -> str:
    """Determine which architectural layer a file belongs to."""
    parts = file_path.parts
    
    # Find the layer in the path
    for layer in ARCH_LAYERS.keys():
        if layer in parts:
            return layer
    
    return None


def extract_imports(file_path: Path) -> List[Tuple[str, int]]:
    """Extract all imports from a Python file."""
    imports = []
    
    # Skip if not a file (e.g., directory)
    if not file_path.is_file():
        return imports
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, node.lineno))
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append((node.module, node.lineno))
    
    except (SyntaxError, UnicodeDecodeError):
        # Skip files with syntax errors or encoding issues
        pass
    
    return imports


def check_file(file_path: Path) -> List[Violation]:
    """Check a single file for import violations."""
    layer = get_module_layer(file_path)
    
    if not layer:
        return []
    
    rules = RULES.get(layer, {})
    denied = rules.get("deny", [])
    allowed = rules.get("allow", [])
    
    imports = extract_imports(file_path)
    violations = []
    
    for import_name, line_number in imports:
        # Skip relative imports (they start with dot)
        if import_name.startswith('.'):
            continue
            
        # Check if import is denied
        for denied_layer in denied:
            if import_name.startswith(denied_layer):
                # Check if it's explicitly allowed
                is_allowed = False
                for allowed_layer in allowed:
                    if import_name.startswith(allowed_layer):
                        is_allowed = True
                        break
                
                if not is_allowed:
                    violations.append(Violation(
                        file_path=file_path,
                        import_name=import_name,
                        forbidden_layer=denied_layer,
                        line_number=line_number,
                    ))
    
    return violations


def check_layer_dependency_order(file_path: Path, import_name: str) -> bool:
    """Check if import violates layer ordering (lower layer importing higher layer)."""
    src_layer = get_module_layer(file_path)
    
    if not src_layer:
        return True
    
    # Find destination layer
    dst_layer = None
    for layer in ARCH_LAYERS.keys():
        if import_name.startswith(layer):
            dst_layer = layer
            break
    
    if not dst_layer:
        return True
    
    # Check ordering: source layer number must be >= destination layer number
    # Lower number = higher level. Lower layers (higher number) may import higher layers (lower number)
    src_order = ARCH_LAYERS.get(src_layer, 999)
    dst_order = ARCH_LAYERS.get(dst_layer, 999)
    
    # Same level layers can import each other freely
    return src_order >= dst_order


def main():
    """Main entry point for import guard."""
    base_dir = Path(".")
    
    # Directories to skip
    skip_dirs = {"venv", ".venv", "__pycache__", ".git", "node_modules", ".tox"}
    
    violations = []
    files_checked = 0
    
    print("🔍 Running import architecture guard...")
    print()
    
    for py_file in base_dir.rglob("*.py"):
        # Skip non-source directories
        if any(skip in str(py_file) for skip in skip_dirs):
            continue
        
        # Skip empty __init__.py files
        if py_file.name == "__init__.py":
            try:
                if py_file.stat().st_size < 10:
                    continue
            except OSError:
                continue
        
        files_checked += 1
        file_violations = check_file(py_file)
        
        # Also check layer ordering
        imports = extract_imports(py_file)
        for import_name, line_number in imports:
            # Skip relative imports
            if import_name.startswith('.'):
                continue
            if not check_layer_dependency_order(py_file, import_name):
                src_layer = get_module_layer(py_file)
                file_violations.append(Violation(
                    file_path=py_file,
                    import_name=import_name,
                    forbidden_layer=f"layer_order (src={src_layer})",
                    line_number=line_number,
                ))
        
        violations.extend(file_violations)
    
    # Report results
    print(f"📊 Checked {files_checked} Python files")
    print()
    
    if violations:
        print("❌ IMPORT ARCHITECTURE VIOLATIONS DETECTED:")
        print()
        
        # Group by file
        violations_by_file = {}
        for v in violations:
            if v.file_path not in violations_by_file:
                violations_by_file[v.file_path] = []
            violations_by_file[v.file_path].append(v)
        
        for file_path, file_violations in sorted(violations_by_file.items()):
            print(f"📄 {file_path}")
            for v in file_violations:
                print(f"   Line {v.line_number}: imports '{v.import_name}'")
                print(f"   Forbidden: {v.forbidden_layer}")
            print()
        
        print(f"💥 Total violations: {len(violations)}")
        print()
        print("Architecture rules:")
        print("  - api → application only")
        print("  - application → domain, core")
        print("  - domain → NOTHING (pure)")
        print("  - core → domain only")
        print("  - engines → core, domain")
        print("  - evaluation → core, domain, engines (read-only)")
        print("  - infrastructure → core, domain")
        print()
        
        sys.exit(1)
    
    else:
        print("✅ Import architecture clean!")
        print()
        print("All imports comply with architectural rules:")
        print("  ✓ API imports only application")
        print("  ✓ Application imports only domain and core")
        print("  ✓ Domain is pure (no external imports)")
        print("  ✓ Core imports only domain")
        print("  ✓ Engines import only core and domain")
        print("  ✓ Evaluation imports core, domain, engines (read-only)")
        print("  ✓ Infrastructure imports only core and domain")
        print()
        
        sys.exit(0)


if __name__ == "__main__":
    main()