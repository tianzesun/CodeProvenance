#!/usr/bin/env python3
"""Demo script showing transformer perplexity vs bigram perplexity.

Run: python scripts/demo_transformer_perplexity.py

Requires: pip install transformers torch
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Sample codes for comparison
AI_GENERATED_CODE = """
def process_user_data(data: dict) -> dict:
    \"\"\"Process user data and return validated results.
    
    This function takes a dictionary containing user information,
    validates the fields, and returns a processed dictionary.
    
    Args:
        data: Dictionary containing user information
        
    Returns:
        Dictionary with processed and validated data
    \"\"\"
    # Initialize the result dictionary
    result = {}
    
    # First, let's validate the input data
    if not data or not isinstance(data, dict):
        return result
    
    # Now we process each field
    if 'name' in data:
        # Extract and clean the name field
        result['name'] = str(data['name']).strip()
    
    if 'age' in data:
        # Convert age to integer and validate
        try:
            result['age'] = int(data['age'])
        except (ValueError, TypeError):
            result['age'] = 0
    
    # Return the processed data
    return result
"""

HUMAN_CODE = """
def proc_data(d):
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
"""


def main():
    print("=" * 70)
    print("Transformer Perplexity Demo")
    print("=" * 70)
    print()

    # Check if transformers installed
    try:
        import torch
        import transformers

        print(f"✓ torch {torch.__version__}")
        print(f"✓ transformers {transformers.__version__}")
        print()
    except ImportError as e:
        print("✗ Missing dependencies:")
        print(f"  {e}")
        print()
        print("Install with:")
        print("  pip install transformers torch")
        return 1

    # Import our analyzer
    from src.backend.engines.ai_detection import compute_ai_score
    from src.backend.engines.similarity.ai_detection import AIDetectionEngine

    print("Analyzing AI-generated code...")
    print("-" * 70)
    print(AI_GENERATED_CODE[:200] + "...")
    print()

    result_ai = compute_ai_score(AI_GENERATED_CODE)
    print(f"Transformer Perplexity: {result_ai['raw_perplexity']:.2f}")
    print(f"AI Score: {result_ai['ai_score']:.3f}")
    print(f"Interpretation: {result_ai['interpretation']}")
    print()

    print("=" * 70)
    print()
    print("Analyzing human-written code...")
    print("-" * 70)
    print(HUMAN_CODE)
    print()

    result_human = compute_ai_score(HUMAN_CODE)
    print(f"Transformer Perplexity: {result_human['raw_perplexity']:.2f}")
    print(f"AI Score: {result_human['ai_score']:.3f}")
    print(f"Interpretation: {result_human['interpretation']}")
    print()

    print("=" * 70)
    print("COMPARISON")
    print("=" * 70)
    print(
        f"AI Code:    Perplexity={result_ai['raw_perplexity']:6.2f}  AI Score={result_ai['ai_score']:.3f}"
    )
    print(
        f"Human Code: Perplexity={result_human['raw_perplexity']:6.2f}  AI Score={result_human['ai_score']:.3f}"
    )
    print()

    # Compare with old bigram-based perplexity
    print("Comparing with old bigram-based detection...")
    engine = AIDetectionEngine(use_transformer=False)  # Old mode
    old_result_ai = engine.analyze(AI_GENERATED_CODE, "python")
    old_result_human = engine.analyze(HUMAN_CODE, "python")

    print(f"Old (bigram) AI detection:    {old_result_ai['ai_probability']:.3f}")
    print(f"Old (bigram) Human detection: {old_result_human['ai_probability']:.3f}")
    print(
        f"Discrimination (AI - Human):  {old_result_ai['ai_probability'] - old_result_human['ai_probability']:.3f}"
    )
    print()

    # New with transformer
    engine_v2 = AIDetectionEngine(use_transformer=True)  # New mode
    new_result_ai = engine_v2.analyze(AI_GENERATED_CODE, "python")
    new_result_human = engine_v2.analyze(HUMAN_CODE, "python")

    print(f"New (transformer) AI detection:    {new_result_ai['ai_probability']:.3f}")
    print(f"New (transformer) Human detection: {new_result_human['ai_probability']:.3f}")
    print(
        f"Discrimination (AI - Human):       {new_result_ai['ai_probability'] - new_result_human['ai_probability']:.3f}"
    )
    print()

    improvement = (new_result_ai["ai_probability"] - new_result_human["ai_probability"]) - (
        old_result_ai["ai_probability"] - old_result_human["ai_probability"]
    )

    print(f"Improvement in discrimination: {improvement:+.3f}")
    if improvement > 0:
        print("✓ Transformer perplexity improves AI vs Human discrimination!")
    print()


if __name__ == "__main__":
    sys.exit(main() or 0)
