#!/usr/bin/env python3
"""Demo script showing AST-based analysis immunity to obfuscation.

Run: python scripts/demo_ast_analysis.py

Shows how AST analysis detects AI code even after variable renaming,
comment removal, and other surface-level attacks.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.engines.ai_detection import compute_ast_score

# Original AI-generated code
ORIGINAL_AI_CODE = """
import os
import sys
from pathlib import Path

def process_user_data(user_data: dict) -> dict:
    '''Process user data and return validated results.
    
    This function validates input and returns cleaned data.
    '''
    result = {}
    try:
        if user_data is None:
            return result
        if 'name' in user_data:
            result['name'] = str(user_data['name']).strip()
        if 'age' in user_data:
            try:
                result['age'] = int(user_data['age'])
            except (ValueError, TypeError):
                result['age'] = 0
    except Exception:
        return {}
    return result

def validate_user_data(user_data: dict) -> bool:
    '''Validate user data.'''
    if user_data is None:
        return False
    try:
        return len(user_data) > 0
    except TypeError:
        return False

def transform_user_data(user_data: dict) -> dict:
    '''Transform user data.'''
    result = {}
    try:
        for key, value in user_data.items():
            result[key.upper()] = value
    except AttributeError:
        return {}
    return result
"""

# Attack 1: Variable renaming (defeats text-based detection)
RENAMED_CODE = """
import os
import sys
from pathlib import Path

def a(b: dict) -> dict:
    '''Process user data and return validated results.
    
    This function validates input and returns cleaned data.
    '''
    c = {}
    try:
        if b is None:
            return c
        if 'name' in b:
            c['name'] = str(b['name']).strip()
        if 'age' in b:
            try:
                c['age'] = int(b['age'])
            except (ValueError, TypeError):
                c['age'] = 0
    except Exception:
        return {}
    return c

def d(b: dict) -> bool:
    '''Validate user data.'''
    if b is None:
        return False
    try:
        return len(b) > 0
    except TypeError:
        return False

def e(b: dict) -> dict:
    '''Transform user data.'''
    c = {}
    try:
        for f, g in b.items():
            c[f.upper()] = g
    except AttributeError:
        return {}
    return c
"""

# Attack 2: Comment removal
NO_COMMENTS_CODE = """
import os
import sys
from pathlib import Path

def process_user_data(user_data: dict) -> dict:
    result = {}
    try:
        if user_data is None:
            return result
        if 'name' in user_data:
            result['name'] = str(user_data['name']).strip()
        if 'age' in user_data:
            try:
                result['age'] = int(user_data['age'])
            except (ValueError, TypeError):
                result['age'] = 0
    except Exception:
        return {}
    return result

def validate_user_data(user_data: dict) -> bool:
    if user_data is None:
        return False
    try:
        return len(user_data) > 0
    except TypeError:
        return False

def transform_user_data(user_data: dict) -> dict:
    result = {}
    try:
        for key, value in user_data.items():
            result[key.upper()] = value
    except AttributeError:
        return {}
    return result
"""

# Attack 3: Combined (rename + remove comments)
OBFUSCATED_CODE = """
import os
import sys
from pathlib import Path

def a(b: dict) -> dict:
    c = {}
    try:
        if b is None:
            return c
        if 'name' in b:
            c['name'] = str(b['name']).strip()
        if 'age' in b:
            try:
                c['age'] = int(b['age'])
            except (ValueError, TypeError):
                c['age'] = 0
    except Exception:
        return {}
    return c

def d(b: dict) -> bool:
    if b is None:
        return False
    try:
        return len(b) > 0
    except TypeError:
        return False

def e(b: dict) -> dict:
    c = {}
    try:
        for f, g in b.items():
            c[f.upper()] = g
    except AttributeError:
        return {}
    return c
"""

# Human code for comparison
HUMAN_CODE = """
import sys

def proc(d):
    res = {}
    if d:
        if 'name' in d:
            res['name'] = d['name'].strip()
        if 'age' in d:
            try:
                res['age'] = int(d['age'])
            except:
                res['age'] = 0
    return res
"""


def main():
    print("=" * 80)
    print("AST-Based Analysis: Immunity to Obfuscation")
    print("=" * 80)
    print()
    print("AST analysis detects AI code by structure, not surface features.")
    print("This makes it resistant to variable renaming and comment removal.")
    print()

    samples = [
        ("Original AI Code", ORIGINAL_AI_CODE),
        ("Attack 1: Variables Renamed", RENAMED_CODE),
        ("Attack 2: Comments Removed", NO_COMMENTS_CODE),
        ("Attack 3: Combined Obfuscation", OBFUSCATED_CODE),
        ("Human Code (for comparison)", HUMAN_CODE),
    ]

    results = []

    for name, code in samples:
        print("-" * 80)
        print(f"Sample: {name}")
        print("-" * 80)
        print(code[:200] + "..." if len(code) > 200 else code)
        print()

        result = compute_ast_score(code)
        results.append((name, result))

        print(f"AI Score: {result['ai_score']:.1%}")
        print()
        print("Key Structural Features:")
        features = result["features"]
        print(f"  Function Count: {features['function_count']}")
        print(f"  Function Length CV: {features['function_length_cv']:.3f} (low = uniform)")
        print(
            f"  Import Clustering: {features['import_clustering_score']:.3f} (high = perfect org)"
        )
        print(f"  Defensive Patterns: {features['defensive_pattern_count']}")
        print(f"  Docstring Coverage: {features['docstring_coverage']:.1%}")
        print(f"  Type Hint Coverage: {features['type_hint_coverage']:.1%}")
        print(f"  Complexity Uniformity: {features['complexity_uniformity']:.3f} (high = similar)")
        print()

    print("=" * 80)
    print("Comparison: Obfuscation Resistance")
    print("=" * 80)
    print()

    original_score = results[0][1]["ai_score"]
    print(f"Original AI Code:        {original_score:.1%}")
    print()

    for name, result in results[1:4]:
        score = result["ai_score"]
        delta = abs(score - original_score)
        print(f"{name:30} {score:.1%}  (Δ {delta:.1%})")

    print()
    human_score = results[4][1]["ai_score"]
    print(f"Human Code (baseline):   {human_score:.1%}")
    print()

    print("=" * 80)
    print("Key Insights")
    print("=" * 80)
    print(
        """
AST-based analysis is RESISTANT to:
✓ Variable renaming (a, b, c instead of user_data, result)
✓ Comment removal (strips all docstrings)
✓ Combined attacks (rename + strip)

Why? Because it analyzes STRUCTURE, not content:
- Function length uniformity (all ~15-25 lines)
- Perfect import organization (alphabetical, at top)
- Defensive pattern density (try/except everywhere)
- Type hint consistency (all or none)
- Complexity uniformity (all functions similar McCabe score)

Text-based detectors (perplexity, pattern matching) would fail on
renamed/stripped code. AST analysis maintains detection accuracy because
the AI's structural "fingerprint" remains unchanged.

This is crucial for production deployment where students will attempt
to evade detection through obfuscation.
"""
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
