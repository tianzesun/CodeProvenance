#!/usr/bin/env python3
"""Demo script showing AI model fingerprinting.

Run: python scripts/demo_model_fingerprinting.py

Shows how different AI models leave distinctive "fingerprints" in code.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.engines.ai_detection import detect_model

# Sample codes representing different AI model outputs
SAMPLES = {
    "GPT-4 (obvious)": """
def process_user_data(data: dict) -> dict:
    \"\"\"Process user data and return validated results.
    
    This function takes a dictionary containing user information,
    validates the fields, and returns a processed dictionary.
    
    Args:
        data: Dictionary containing user information
        
    Returns:
        Dictionary with processed and validated data
    \"\"\"
    # First, let's validate the input data
    if not data or not isinstance(data, dict):
        return {}
    
    # Now we'll process each field
    result = {}
    
    # Here's how we handle the name field
    if 'name' in data:
        # This will clean and validate the name
        result['name'] = str(data['name']).strip()
    
    # Next, we process the age field
    if 'age' in data:
        # Let's convert to integer
        try:
            result['age'] = int(data['age'])
        except (ValueError, TypeError):
            result['age'] = 0
    
    # Finally, we return the processed data
    return result
""",
    "Claude (type-safe)": """
from typing import Dict, List, Optional, Union

def process_user_data(data: Dict[str, Union[str, int, None]]) -> Optional[Dict[str, Union[str, int]]]:
    # Important: validate input first
    if not data:
        return None
    
    result: Dict[str, Union[str, int]] = {}
    
    # Safety check - ensure data is a dictionary
    if not isinstance(data, dict):
        return None
    
    # Handle the name field with error handling
    try:
        if 'name' in data:
            # Validate and clean the name
            name_value = data.get('name')
            if name_value:
                result['name'] = str(name_value).strip()
    except Exception as e:
        # I'll log this but continue processing
        pass
    
    # Handle age field with type checking
    try:
        if 'age' in data:
            # Ensure we can convert to int
            age_value = data.get('age')
            if age_value is not None:
                result['age'] = int(age_value)
    except (ValueError, TypeError) as e:
        # Handle edge case where conversion fails
        result['age'] = 0
    
    return result
""",
    "Copilot (minimal)": """
def process_data(data):
    if not data:
        return {}
    result = {}
    if 'name' in data:
        result['name'] = str(data['name']).strip()
    if 'age' in data:
        try:
            result['age'] = int(data['age'])
        except:
            result['age'] = 0
    return result
""",
    "Gemini (functional)": """
def validate_field(value, field_type):
    # Validates a single field against its type
    try:
        return field_type(value)
    except:
        return None

def process_name(name):
    # Processes the name field
    return str(name).strip() if name else None

def process_age(age):
    # Processes the age field
    return validate_field(age, int) or 0

def process_user_data(data):
    # Implements user data processing
    if not data:
        return {}
    
    result = {}
    if 'name' in data:
        result['name'] = process_name(data['name'])
    if 'age' in data:
        result['age'] = process_age(data['age'])
    
    return result
""",
    "Human (practical)": """
def process_data(d):
    # basic cleanup
    res = {}
    if d.get('name'):
        res['name'] = d['name'].strip()
    if 'age' in d:
        try:
            res['age'] = int(d['age'])
        except:
            res['age'] = 0
    return res
""",
}


def main():
    print("=" * 80)
    print("AI Model Fingerprinting Demo")
    print("=" * 80)
    print()
    print("Analyzing code samples to detect which AI model generated them...")
    print()

    for sample_name, code in SAMPLES.items():
        print("-" * 80)
        print(f"Sample: {sample_name}")
        print("-" * 80)
        print(code[:150] + "..." if len(code) > 150 else code)
        print()

        fingerprint = detect_model(code, language="python")

        print(f"Detected Model: {fingerprint.detected_model or 'Unknown'}")
        print(f"Confidence: {fingerprint.confidence:.1%}")
        print()

        print("Model Scores:")
        for model, score in sorted(
            fingerprint.model_scores.items(), key=lambda x: x[1], reverse=True
        ):
            bar_length = int(score * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            print(f"  {model:12} {bar} {score:.3f}")
        print()

        if fingerprint.evidence:
            print(f"Evidence (first 3): {fingerprint.evidence[:3]}")
            print()

    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(
        """
Different AI models have distinctive "fingerprints":

GPT-4:
  - Verbose comments ("Here's", "Let's", "First, we")
  - Excessive docstrings
  - Step-by-step explanations
  - Uniform function lengths

Claude:
  - Type hints everywhere
  - Defensive try/except blocks
  - "Important:", "Safety check" comments
  - Explicit error handling

Copilot:
  - Minimal comments
  - Idiomatic code
  - Follows repository style
  - TODO/FIXME markers

Gemini:
  - Functional decomposition
  - Many small functions
  - "Calculates", "Processes", "Returns" comments
  - Explicit naming

This fingerprinting helps:
1. Identify which tool was used (for policy enforcement)
2. Improve detection accuracy (each model has weaknesses)
3. Detect "hybrid" approaches (student using multiple tools)
"""
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
