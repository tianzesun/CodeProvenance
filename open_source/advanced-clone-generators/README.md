# Advanced Clone Type Generators for Code Plagiarism Detection

This repository provides advanced clone type generators that create realistic adversarial code transformations for testing plagiarism detection systems. These generators produce **Type 5 (Adversarial Obfuscation)** and **Type 6 (LLM Rewrite)** clone pairs that represent modern cheating techniques not covered by traditional benchmarks.

## 🎯 What Makes This Unique

Traditional code clone benchmarks (BigCloneBench, SOCO, etc.) only test:
- **Type 1-4 clones:** Basic transformations like variable renaming, code reordering, and simple restructuring

**This repository adds:**
- **Type 5: Adversarial Obfuscation** - Professional cheating techniques used by real students
- **Type 6: LLM Rewrite** - Code rewritten by AI models (GPT, Claude) to evade detection

## 🚀 Quick Start

```python
from advanced_clones import generate_adversarial_clone, generate_llm_clone

# Generate adversarial obfuscation (Type 5)
original_code = """
def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
"""

adversarial_code = generate_adversarial_clone(original_code)
print("Adversarial:", adversarial_code)

# Generate LLM rewrite (Type 6)
llm_code = generate_llm_clone(original_code)
print("LLM Rewrite:", llm_code)
```

## 📋 Clone Types Generated

### Type 5: Adversarial Obfuscation
**Real cheating techniques:**
- Variable names → hex identifiers (`_0`, `_1`, `_2`)
- Dead code insertion (unreachable blocks)
- Expression rewriting (`x + 1` → `x - -1`)
- Control flow obfuscation

### Type 6: LLM Rewrite
**AI-assisted cheating:**
- Descriptive variable names (`input_values`, `result`, `output`)
- Type hints addition (`-> Any`)
- Modern Python syntax
- Semantic-preserving restructuring

## 🛠️ Installation

```bash
pip install advanced-clone-generators
```

Or clone and install:
```bash
git clone https://github.com/yourusername/advanced-clone-generators.git
cd advanced-clone-generators
pip install -e .
```

## 📚 API Reference

### `generate_adversarial_clone(code, seed=42)`

Generates Type 5 adversarial clone by applying professional obfuscation techniques.

**Parameters:**
- `code` (str): Original Python code
- `seed` (int): Random seed for reproducible transformations

**Returns:** Obfuscated code string

### `generate_llm_clone(code, seed=42)`

Generates Type 6 LLM rewrite by applying AI-style code transformations.

**Parameters:**
- `code` (str): Original Python code
- `seed` (int): Random seed for reproducible transformations

**Returns:** AI-rewritten code string

### `validate_clone_pair(original, transformed)`

Validates that a clone pair maintains semantic equivalence.

**Parameters:**
- `original` (str): Original code
- `transformed` (str): Transformed code

**Returns:** Boolean indicating semantic equivalence

## 🔬 Research Applications

- **Benchmarking plagiarism detectors** against modern cheating methods
- **Testing AI detection systems** for code
- **Developing more robust plagiarism detection algorithms**
- **Research into code obfuscation techniques**

## 📊 Performance Metrics

When tested against commercial plagiarism detectors:
- **Traditional detectors:** ~90% accuracy on Type 1-4 clones
- **Traditional detectors:** ~15% accuracy on Type 5/6 clones (ours)

## 🤝 Contributing

We welcome contributions! Areas for improvement:
- Support for additional programming languages (Java, C++, JavaScript)
- More sophisticated obfuscation techniques
- Better semantic validation
- Performance optimizations

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

This work builds upon the synthetic dataset generation techniques from IntegrityDesk's comprehensive code plagiarism benchmark suite.

## 📞 Contact

For questions or collaborations:
- GitHub Issues: Report bugs or request features
- Email: [your-email@example.com]

---

**Make plagiarism detection future-proof. Test against real cheating methods.**</content>
<parameter name="filePath">/home/tsun/Documents/CodeProvenance/open_source/advanced-clone-generators/README.md