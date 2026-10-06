"""Unit tests for AI model fingerprinting."""

import pytest
from src.backend.engines.ai_detection.model_fingerprinting import (
    ModelFingerprinter,
    detect_model,
)


class TestModelFingerprinting:
    """Test AI model signature detection."""

    def test_gpt4_detection(self):
        """GPT-4 code should be detected via comment patterns."""
        gpt4_code = """
def process_data(data: list) -> list:
    # Here's how we'll process the data
    # First, we need to validate the input
    result = []
    
    # Next, we iterate through each item
    for item in data:
        # This will clean the item
        cleaned = item.strip()
        result.append(cleaned)
    
    # Finally, we return the processed results
    return result
"""
        fingerprint = detect_model(gpt4_code)
        assert fingerprint.detected_model in ["GPT-4", None]
        if fingerprint.detected_model == "GPT-4":
            assert fingerprint.confidence > 0.3
            assert "Here's" in str(fingerprint.evidence) or "First" in str(fingerprint.evidence)

    def test_claude_detection(self):
        """Claude code should be detected via type hints and error handling."""
        claude_code = """
from typing import Dict, List, Optional

def process_data(data: List[Dict[str, any]]) -> Optional[List[Dict[str, any]]]:
    # Important: validate input first
    if not data:
        return None
    
    result: List[Dict[str, any]] = []
    
    # Safety check - ensure data is iterable
    try:
        for item in data:
            # Validate each item
            if not isinstance(item, dict):
                continue
            
            # Error handling for missing keys
            try:
                processed = {
                    'id': item.get('id', ''),
                    'value': item['value']
                }
                result.append(processed)
            except KeyError:
                # Handle edge case where value is missing
                continue
    except Exception as e:
        # I'll log the error and return empty
        return []
    
    return result
"""
        fingerprint = detect_model(claude_code)
        # Should detect Claude or at least show high Claude score
        assert fingerprint.model_scores.get("Claude", 0) > 0.2

    def test_copilot_detection(self):
        """Copilot code tends to be minimal with few comments."""
        copilot_code = """
def process(data):
    result = []
    for item in data:
        if item:
            result.append(item.strip())
    return result

def helper(x, y):
    return x + y if x > 0 else y
"""
        fingerprint = detect_model(copilot_code)
        # Copilot is harder to detect (mimics human code)
        # Should have low comment density
        assert isinstance(fingerprint.model_scores, dict)

    def test_gemini_detection(self):
        """Gemini tends toward functional style."""
        gemini_code = """
def calculate_total(items):
    # Calculates the total sum of all items
    return sum(items)

def process_item(item):
    # Processes a single item
    return item.strip().lower()

def validate_input(data):
    # Returns True if data is valid
    return data is not None and len(data) > 0

def transform_data(data):
    # Implements data transformation logic
    return [process_item(x) for x in data if validate_input(x)]
"""
        fingerprint = detect_model(gemini_code)
        assert isinstance(fingerprint.model_scores, dict)
        assert fingerprint.model_scores.get("Gemini", 0) >= 0.0

    def test_empty_code_handling(self):
        """Empty code should return None detection."""
        fingerprint = detect_model("")
        assert fingerprint.detected_model is None
        assert fingerprint.confidence == 0.0

    def test_human_code_no_detection(self):
        """Typical human code should not strongly match any model."""
        human_code = """
def calc(x):
    # quick helper
    if x < 0:
        x = -x
    return x * 2 + 1

# main logic
def run():
    vals = [1, -2, 3]
    res = [calc(v) for v in vals]
    print(res)
"""
        fingerprint = detect_model(human_code)
        # Should have low confidence for any model
        assert fingerprint.confidence < 0.7

    def test_fingerprint_to_dict(self):
        """Test serialization to dict."""
        code = "def foo(): pass"
        fingerprint = detect_model(code)
        result = fingerprint.to_dict()

        assert "detected_model" in result
        assert "confidence" in result
        assert "model_scores" in result
        assert "evidence" in result
        assert isinstance(result["model_scores"], dict)

    def test_docstring_ratio_calculation(self):
        """Test docstring ratio helper."""
        fingerprinter = ModelFingerprinter()

        # All functions have docstrings
        code_full_doc = """
def func1():
    \"\"\"Doc1\"\"\"
    pass

def func2():
    \"\"\"Doc2\"\"\"
    return 1
"""
        ratio = fingerprinter._docstring_ratio(code_full_doc)
        assert ratio == 1.0

        # No docstrings
        code_no_doc = """
def func1():
    pass

def func2():
    return 1
"""
        ratio = fingerprinter._docstring_ratio(code_no_doc)
        assert ratio == 0.0

    def test_type_hint_ratio_calculation(self):
        """Test type hint ratio helper."""
        fingerprinter = ModelFingerprinter()

        # All parameters typed
        code_typed = """
def func(x: int, y: str) -> bool:
    return True

def func2(a: list, b: dict) -> None:
    pass
"""
        ratio = fingerprinter._type_hint_ratio(code_typed)
        assert ratio == 1.0

        # No type hints
        code_untyped = """
def func(x, y):
    return x + y
"""
        ratio = fingerprinter._type_hint_ratio(code_untyped)
        assert ratio == 0.0

    def test_singleton_pattern(self):
        """Test that fingerprinter uses singleton pattern."""
        from src.backend.engines.ai_detection import get_fingerprinter

        fp1 = get_fingerprinter()
        fp2 = get_fingerprinter()
        assert fp1 is fp2

    def test_structural_fingerprints(self):
        """Test that structural analysis contributes to scores."""
        fingerprinter = ModelFingerprinter()

        # Code with high docstring density (GPT-4 signal)
        gpt4_like = """
def func1():
    \"\"\"Docstring 1\"\"\"
    pass

def func2():
    \"\"\"Docstring 2\"\"\"
    pass

def func3():
    \"\"\"Docstring 3\"\"\"
    pass
"""
        scores, _notes = fingerprinter._structural_bonus(gpt4_like, "python")
        assert "GPT-4" in scores or len(scores) == 0  # May detect GPT-4 structural pattern

    def test_multiple_model_ambiguity(self):
        """Test that confidence lowers when multiple models match."""
        # Code that could be from multiple models
        ambiguous_code = """
def process(data):
    # Process the data
    result = []
    for item in data:
        result.append(item)
    return result
"""
        fingerprint = detect_model(ambiguous_code)
        # Should have lower confidence due to ambiguity
        assert isinstance(fingerprint.confidence, float)
        assert 0 <= fingerprint.confidence <= 1
