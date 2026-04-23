#!/usr/bin/env python3
"""
Example usage of advanced clone type generators.

This demonstrates how to use the Type 5 (Adversarial Obfuscation) and
Type 6 (LLM Rewrite) clone generators.
"""

from advanced_clones import generate_adversarial_clone, generate_llm_clone, validate_clone_pair


def main():
    # Example Python function
    original_code = '''def find_max(numbers):
    """Find the maximum value in a list."""
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
'''

    print("🎯 Advanced Clone Type Generators Demo")
    print("=" * 50)
    print()

    print("📝 Original Code:")
    print(original_code)
    print()

    # Generate Type 5: Adversarial Obfuscation
    print("🔒 Type 5: Adversarial Obfuscation")
    print("-" * 30)
    adversarial = generate_adversarial_clone(original_code, seed=42)
    print(adversarial)
    print()

    # Generate Type 6: LLM Rewrite
    print("🤖 Type 6: LLM Rewrite")
    print("-" * 30)
    llm_rewrite = generate_llm_clone(original_code, seed=42)
    print(llm_rewrite)
    print()

    # Validate clones
    print("✅ Validation Results:")
    print("-" * 30)
    print(f"Adversarial clone valid: {validate_clone_pair(original_code, adversarial)}")
    print(f"LLM clone valid: {validate_clone_pair(original_code, llm_rewrite)}")
    print()

    print("🎯 Key Differences:")
    print("-" * 30)
    print("Type 5 (Adversarial): Hex variable names, dead code, expression rewriting")
    print("Type 6 (LLM): Descriptive names, type hints, modern syntax")
    print()
    print("These transformations defeat traditional plagiarism detectors!")


if __name__ == "__main__":
    main()</content>
<parameter name="filePath">/home/tsun/Documents/CodeProvenance/open_source/advanced-clone-generators/example.py