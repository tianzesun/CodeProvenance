#!/usr/bin/env python3
"""Update imports in Python files from src.* to src.backend.*"""

import re
from pathlib import Path

def update_imports_in_file(filepath):
    """Update imports in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  ✗ Error reading {filepath}: {e}")
        return False
    
    original = content
    
    # Update from imports
    content = re.sub(
        r'from src\.(\w+)',
        r'from src.backend.\1',
        content
    )
    
    # Update import statements
    content = re.sub(
        r'import src\.(\w+)',
        r'import src.backend.\1',
        content
    )
    
    # Skip if no changes
    if content == original:
        return False
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"  ✗ Error writing {filepath}: {e}")
        return False

def main():
    """Update all Python files."""
    updated = 0
    skipped = 0
    errors = 0
    
    print("Updating imports in Python files...")
    print()
    
    for py_file in sorted(Path('.').rglob('*.py')):
        # Skip venv and node_modules
        if 'venv' in py_file.parts or 'node_modules' in py_file.parts or '__pycache__' in py_file.parts:
            continue
        
        # Skip if not in src/backend or tests
        if 'src/backend' not in str(py_file) and 'tests' not in str(py_file):
            continue
        
        if update_imports_in_file(py_file):
            print(f"✓ {py_file}")
            updated += 1
        else:
            skipped += 1
    
    print()
    print(f"Summary:")
    print(f"  Updated: {updated} files")
    print(f"  Skipped: {skipped} files (no changes needed)")
    print(f"  Errors: {errors} files")

if __name__ == '__main__':
    main()
