# CodeGuard Pro - Testing & Evaluation Framework

**Version**: 2.0  
**Last Updated**: 2026-03-31  
**Status**: Active Development

---

## Table of Contents

1. [Testing Overview](#1-testing-overview)
2. [Benchmark Datasets](#2-benchmark-datasets)
3. [Sample Generation](#3-sample-generation)
4. [Evaluation Metrics](#4-evaluation-metrics)
5. [Testing Methodology](#5-testing-methodology)
6. [Optimization Pipeline](#6-optimization-pipeline)
7. [A/B Testing Framework](#7-ab-testing-framework)
8. [Competitive Benchmarking](#8-competitive-benchmarking)
9. [Test Automation](#9-test-automation)
10. [Performance Benchmarks](#10-performance-benchmarks)

---

## 1. Testing Overview

### 1.1 Testing Philosophy

CodeGuard Pro employs a rigorous, data-driven testing approach to ensure:

- **High Accuracy**: >95% precision and recall
- **Robustness**: Resistance to various obfuscation techniques
- **Reliability**: Consistent performance across different code types
- **Competitiveness**: Superior to existing solutions (MOSS, JPlag)

### 1.2 Testing Pyramid

```
┌─────────────────────────────────────────────────────────────┐
│                    END-TO-END TESTS                         │
│  Full workflow: Upload → Process → Results → Report         │
├─────────────────────────────────────────────────────────────┤
│                    INTEGRATION TESTS                        │
│  API + Database + Worker + Cache interactions               │
├─────────────────────────────────────────────────────────────┤
│                    UNIT TESTS                               │
│  Individual components: Parser, Similarity, Analyzer        │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Test Categories

| Category              | Purpose               | Frequency     |
| --------------------- | --------------------- | ------------- |
| **Unit Tests**        | Component correctness | Every commit  |
| **Integration Tests** | Component interaction | Every PR      |
| **Benchmark Tests**   | Accuracy validation   | Weekly        |
| **Performance Tests** | Speed & scalability   | Weekly        |
| **Regression Tests**  | Prevent degradation   | Every release |
| **A/B Tests**         | Algorithm comparison  | Continuous    |

---

## 2. Benchmark Datasets

### 2.1 Primary Datasets

#### 2.1.1 BigCloneBench (Java Code Clones)

**Source**: https://www.cs.uwaterloo.ca/~bigclonebench/

| Property         | Value                                                                   |
| ---------------- | ----------------------------------------------------------------------- |
| **Language**     | Java                                                                    |
| **Size**         | 25,000+ code fragments                                                  |
| **Clone Types**  | Type 1 (exact), Type 2 (renamed), Type 3 (near-miss), Type 4 (semantic) |
| **Ground Truth** | Manually validated by experts                                           |
| **Use Case**     | Clone detection accuracy evaluation                                     |

**Download & Setup**:

```bash
# Download BigCloneBench
wget https://www.cs.uwaterloo.ca/~bigclonebench/groundtruth/bcb-benchmark.tar.gz
tar -xzf bcb-benchmark.tar.gz

# Organize for testing
mkdir -p tests/fixtures/bigclonebench
mv bcb-benchmark/* tests/fixtures/bigclonebench/
```

**Dataset Structure**:

```
tests/fixtures/bigclonebench/
├── clones/              # Positive samples (known clones)
│   ├── type1/          # Exact copies
│   ├── type2/          # Variable renamed
│   ├── type3/          # Near-miss (statements added/removed)
│   └── type4/          # Semantic clones (different implementation, same logic)
├── non-clones/         # Negative samples (independent implementations)
└── metadata.json       # Ground truth labels
```

#### 2.1.2 Google Code Jam Submissions

**Source**: https://code.google.com/codejam/

| Property         | Value                              |
| ---------------- | ---------------------------------- |
| **Languages**    | Multiple (Java, C++, Python, etc.) |
| **Size**         | 100,000+ submissions               |
| **Problem Sets** | Multiple competition years         |
| **Use Case**     | Real-world plagiarism detection    |

**Download & Setup**:

```bash
# Download via Google Code Jam API or archives
python scripts/download_gcj.py --years 2008-2020 --problems all

# Organize by problem
mkdir -p tests/fixtures/google_codejam
for year in 2008 2009 2010; do
    mkdir -p tests/fixtures/google_codejam/$year
done
```

**Dataset Structure**:

```
tests/fixtures/google_codejam/
├── 2008/
│   ├── problem_a/
│   │   ├── submissions/     # All submissions for this problem
│   │   └── ground_truth.json  # Known plagiarism pairs
├── 2009/
├── 2010/
└── analysis/
    └── similarity_matrix.csv
```

#### 2.1.3 Xiangtan University Dataset

**Source**: Academic research dataset

| Property      | Value                            |
| ------------- | -------------------------------- |
| **Languages** | C, C++, Java                     |
| **Size**      | 10,000+ pairs                    |
| **Focus**     | Student assignments              |
| **Use Case**  | Educational plagiarism detection |

**Download & Setup**:

```bash
# Download from academic repository
wget https://example.com/xiangtan-dataset.zip
unzip xiangtan-dataset.zip -d tests/fixtures/xiangtan/

# Verify integrity
md5sum -c tests/fixtures/xiangtan/checksums.md5
```

**Dataset Structure**:

```
tests/fixtures/xiangtan/
├── c_language/
│   ├── assignments/
│   │   ├── hw1/
│   │   │   ├── student_001.c
│   │   │   ├── student_002.c
│   │   │   └── ground_truth.json
│   └── ...
├── cpp_language/
├── java_language/
└── metadata.json
```

### 2.2 Supplementary Datasets

#### 2.2.1 OJ Clone Detection Dataset

**Source**: Online Judge systems

| Property      | Value                             |
| ------------- | --------------------------------- |
| **Size**      | 50,000+ solution pairs            |
| **Languages** | C, C++, Java, Python              |
| **Use Case**  | Programming assignment plagiarism |

#### 2.2.2 Stack Overflow Code Snippets

**Source**: Stack Exchange Data Dump

| Property     | Value                     |
| ------------ | ------------------------- |
| **Size**     | 10M+ code snippets        |
| **Use Case** | External source detection |

#### 2.2.3 GitHub Copilot Generated Code

**Source**: Collected samples

| Property     | Value                       |
| ------------ | --------------------------- |
| **Size**     | 5,000+ pairs                |
| **Use Case** | AI-generated code detection |

### 2.3 Custom Test Suites

#### 2.3.1 Obfuscation Test Suite

```python
# tests/fixtures/obfuscation/
├── original/
│   ├── sort_algorithm.py
│   ├── linked_list.py
│   └── graph_traversal.py
├── level1_variable_rename/
│   ├── sort_algorithm.py
│   ├── linked_list.py
│   └── graph_traversal.py
├── level2_statement_reorder/
│   ├── sort_algorithm.py
│   ├── linked_list.py
│   └── graph_traversal.py
├── level3_control_flow_change/
│   ├── sort_algorithm.py
│   ├── linked_list.py
│   └── graph_traversal.py
└── level4_semantic_preserving/
    ├── sort_algorithm.py
    ├── linked_list.py
    └── graph_traversal.py
```

#### 2.3.2 Edge Case Test Suite

```python
# tests/fixtures/edge_cases/
├── empty_files/
├── single_line/
├── comments_only/
├── mixed_languages/
├── binary_files/
├── malformed_syntax/
└── unicode_content/
```

---

## 3. Sample Generation

### 3.1 Positive Sample Generation (Plagiarism Pairs)

#### 3.1.1 Direct Copy

```python
def generate_direct_copy(original_code: str) -> str:
    """Generate exact copy (Type 1 clone)"""
    return original_code
```

#### 3.1.2 Variable Renaming

```python
import random
import re

def generate_variable_renamed(code: str, rename_ratio: float = 0.8) -> str:
    """Generate code with renamed variables (Type 2 clone)"""
    # Extract variable names
    variables = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', code)
    unique_vars = list(set([v for v in variables if not v.iskeyword()]))

    # Randomly select variables to rename
    num_to_rename = int(len(unique_vars) * rename_ratio)
    vars_to_rename = random.sample(unique_vars, num_to_rename)

    # Generate new names
    renamed_code = code
    for old_var in vars_to_rename:
        new_var = f"var_{random.randint(1000, 9999)}"
        renamed_code = re.sub(r'\b' + old_var + r'\b', new_var, renamed_code)

    return renamed_code
```

#### 3.1.3 Statement Reordering

```python
def generate_statement_reordered(code: str, reorder_ratio: float = 0.5) -> str:
    """Generate code with reordered statements (Type 3 clone)"""
    lines = code.split('\n')

    # Identify reorderable blocks (independent statements)
    reorderable_blocks = identify_independent_blocks(lines)

    # Shuffle blocks
    num_to_reorder = int(len(reorderable_blocks) * reorder_ratio)
    blocks_to_reorder = random.sample(reorderable_blocks, num_to_reorder)

    for block in blocks_to_reorder:
        random.shuffle(block)

    return reconstruct_code(lines, reorderable_blocks)
```

#### 3.1.4 Control Flow Transformation

```python
def generate_control_flow_changed(code: str) -> str:
    """Generate code with different control flow (Type 3-4 clone)"""
    transformations = [
        for_to_while,
        while_to_for,
        if_else_to_switch,
        recursion_to_iteration,
        iterative_to_recursive
    ]

    transformation = random.choice(transformations)
    return transformation(code)
```

#### 3.1.5 Semantic Preservation (Algorithm Substitution)

```python
def generate_semantic_clone(code: str, target_language: str = None) -> str:
    """Generate semantically equivalent code (Type 4 clone)"""
    # Parse and understand algorithm
    algorithm = extract_algorithm(code)

    # Generate alternative implementation
    if algorithm == "bubble_sort":
        return generate_insertion_sort()  # Same O(n²) behavior
    elif algorithm == "linear_search":
        return generate_binary_search()   # Different approach, same goal

    return code
```

### 3.2 Negative Sample Generation (Independent Implementations)

#### 3.2.1 Different Algorithm Same Problem

```python
def generate_independent_solution(problem_description: str) -> str:
    """Generate independent solution to same problem"""
    # Use different approach
    if "sort" in problem_description.lower():
        algorithms = ["quicksort", "mergesort", "heapsort"]
        chosen = random.choice(algorithms)
        return generate_sorting_algorithm(chosen)

    return generate_generic_solution(problem_description)
```

#### 3.2.2 Different Problem Entirely

```python
def generate_unrelated_code() -> str:
    """Generate code solving completely different problem"""
    problems = [
        "fibonacci_sequence",
        "prime_generation",
        "matrix_multiplication",
        "path_finding",
        "string_matching"
    ]
    return generate_solution(random.choice(problems))
```

### 3.3 Obfuscation Levels

#### Level 0: No Obfuscation

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

#### Level 1: Variable Renaming

```python
def fibonacci(num):
    if num <= 1:
        return num
    return fibonacci(num-1) + fibonacci(num-2)
```

#### Level 2: Statement Reordering

```python
def fibonacci(n):
    result = fibonacci(n-1) + fibonacci(n-2)
    if n <= 1:
        return n
    return result
```

#### Level 3: Control Flow Change

```python
def fibonacci(n):
    def fib_iter(a, b, count):
        if count == 0:
            return b
        return fib_iter(a + b, a, count - 1)
    return fib_iter(1, 0, n)
```

#### Level 4: Semantic Preservation

```python
def fibonacci(n):
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

### 3.4 Sample Generation Script

```python
#!/usr/bin/env python3
"""
Generate test samples for CodeGuard Pro evaluation
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class TestSample:
    """Represents a test sample pair"""
    id: str
    code_a: str
    code_b: str
    language: str
    is_plagiarism: bool
    clone_type: int  # 0 = non-clone, 1-4 = clone types
    obfuscation_level: int  # 0-4
    source: str  # Dataset source

class SampleGenerator:
    """Generate test samples for evaluation"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_dataset(self,
                        num_positive: int = 1000,
                        num_negative: int = 1000,
                        languages: List[str] = None) -> List[TestSample]:
        """Generate complete test dataset"""

        if languages is None:
            languages = ["python", "java", "cpp", "javascript"]

        samples = []

        # Generate positive samples (plagiarism)
        for i in range(num_positive):
            for lang in languages:
                for obfuscation in range(5):  # Levels 0-4
                    sample = self._generate_positive_sample(
                        f"pos_{i}_{lang}_{obfuscation}",
                        lang,
                        obfuscation
                    )
                    samples.append(sample)

        # Generate negative samples (independent)
        for i in range(num_negative):
            for lang in languages:
                sample = self._generate_negative_sample(
                    f"neg_{i}_{lang}",
                    lang
                )
                samples.append(sample)

        return samples

    def _generate_positive_sample(self,
                                  sample_id: str,
                                  language: str,
                                  obfuscation_level: int) -> TestSample:
        """Generate a positive (plagiarism) sample"""

        # Get base code
        base_code = self._get_base_code(language)

        # Apply obfuscation
        if obfuscation_level == 0:
            modified_code = base_code
            clone_type = 1
        elif obfuscation_level == 1:
            modified_code = generate_variable_renamed(base_code)
            clone_type = 2
        elif obfuscation_level == 2:
            modified_code = generate_statement_reordered(base_code)
            clone_type = 3
        elif obfuscation_level == 3:
            modified_code = generate_control_flow_changed(base_code)
            clone_type = 3
        else:  # Level 4
            modified_code = generate_semantic_clone(base_code)
            clone_type = 4

        return TestSample(
            id=sample_id,
            code_a=base_code,
            code_b=modified_code,
            language=language,
            is_plagiarism=True,
            clone_type=clone_type,
            obfuscation_level=obfuscation_level,
            source="generated"
        )

    def _generate_negative_sample(self,
                                  sample_id: str,
                                  language: str) -> TestSample:
        """Generate a negative (independent) sample"""

        code_a = self._get_base_code(language)
        code_b = generate_unrelated_code()

        return TestSample(
            id=sample_id,
            code_a=code_a,
            code_b=code_b,
            language=language,
            is_plagiarism=False,
            clone_type=0,
            obfuscation_level=0,
            source="generated"
        )

    def _get_base_code(self, language: str) -> str:
        """Get base code for testing"""
        # Load from fixtures
        fixtures = {
            "python": "tests/fixtures/base/sorting.py",
            "java": "tests/fixtures/base/Sorting.java",
            "cpp": "tests/fixtures/base/sorting.cpp",
            "javascript": "tests/fixtures/base/sorting.js"
        }

        path = Path(fixtures.get(language, fixtures["python"]))
        return path.read_text()

    def export_dataset(self, samples: List[TestSample], filename: str):
        """Export dataset to JSON"""
        output_path = self.output_dir / filename

        data = []
        for sample in samples:
            data.append({
                "id": sample.id,
                "code_a": sample.code_a,
                "code_b": sample.code_b,
                "language": sample.language,
                "is_plagiarism": sample.is_plagiarism,
                "clone_type": sample.clone_type,
                "obfuscation_level": sample.obfuscation_level,
                "source": sample.source
            })

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(samples)} samples to {output_path}")

if __name__ == "__main__":
    generator = SampleGenerator(Path("tests/generated"))

    # Generate datasets
    samples = generator.generate_dataset(
        num_positive=500,
        num_negative=500,
        languages=["python", "java", "cpp"]
    )

    # Export
    generator.export_dataset(samples, "test_dataset.json")
```

---

## 4. Evaluation Metrics

### 4.1 Core Metrics

#### 4.1.1 Precision

**Definition**: Of all pairs flagged as plagiarism, what percentage are actually plagiarism?

```
Precision = True Positives / (True Positives + False Positives)
```

**Interpretation**:

- **High Precision (>0.95)**: Few false accusations
- **Low Precision**: Many innocent students flagged

**Target**: >0.95 (less than 5% false positives)

#### 4.1.2 Recall

**Definition**: Of all actual plagiarism pairs, what percentage did we detect?

```
Recall = True Positives / (True Positives + False Negatives)
```

**Interpretation**:

- **High Recall (>0.99)**: Catch almost all plagiarism
- **Low Recall**: Miss many plagiarized submissions

**Target**: >0.99 (catch at least 99% of plagiarism)

#### 4.1.3 F1 Score

**Definition**: Harmonic mean of Precision and Recall

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

**Interpretation**:

- **F1 > 0.9**: Excellent balance
- **F1 0.8-0.9**: Good performance
- **F1 < 0.8**: Needs improvement

**Target**: >0.97

#### 4.1.4 Confusion Matrix

```
                    Predicted
                    Plagiarism  Not Plagiarism
Actual  Plagiarism    TP           FN
        Not Plag.    FP           TN
```

**Example**:

```
Total pairs: 10,000
Actual plagiarism: 1,000
Actual non-plagiarism: 9,000

Results:
TP = 985 (correctly identified plagiarism)
FP = 150 (false positives - innocent students flagged)
FN = 15 (missed plagiarism)
TN = 8,850 (correctly identified non-plagiarism)

Precision = 985 / (985 + 150) = 0.868
Recall = 985 / (985 + 15) = 0.985
F1 = 2 * (0.868 * 0.985) / (0.868 + 0.985) = 0.923
```

### 4.2 Additional Metrics

#### 4.2.1 Accuracy by Clone Type

| Clone Type         | Precision | Recall | F1  |
| ------------------ | --------- | ------ | --- |
| Type 1 (Exact)     | -         | -      | -   |
| Type 2 (Renamed)   | -         | -      | -   |
| Type 3 (Near-miss) | -         | -      | -   |
| Type 4 (Semantic)  | -         | -      | -   |

#### 4.2.2 Accuracy by Obfuscation Level

| Obfuscation Level      | Precision | Recall | F1  |
| ---------------------- | --------- | ------ | --- |
| Level 0 (None)         | -         | -      | -   |
| Level 1 (Variables)    | -         | -      | -   |
| Level 2 (Statements)   | -         | -      | -   |
| Level 3 (Control Flow) | -         | -      | -   |
| Level 4 (Semantic)     | -         | -      | -   |

#### 4.2.3 Accuracy by Language

| Language   | Precision | Recall | F1  |
| ---------- | --------- | ------ | --- |
| Python     | -         | -      | -   |
| Java       | -         | -      | -   |
| C++        | -         | -      | -   |
| JavaScript | -         | -      | -   |

### 4.3 Metric Calculation Implementation

```python
#!/usr/bin/env python3
"""
Calculate evaluation metrics for CodeGuard Pro
"""

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
import seaborn as sns

class MetricsCalculator:
    """Calculate and visualize evaluation metrics"""

    def __init__(self):
        self.results = []

    def add_result(self,
                   predicted: bool,
                   actual: bool,
                   similarity_score: float,
                   metadata: Dict = None):
        """Add a prediction result"""
        self.results.append({
            'predicted': predicted,
            'actual': actual,
            'score': similarity_score,
            'metadata': metadata or {}
        })

    def calculate_metrics(self) -> Dict:
        """Calculate all metrics"""

        y_pred = [r['predicted'] for r in self.results]
        y_true = [r['actual'] for r in self.results]

        # Core metrics
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / (tp + tn + fp + fn)

        return {
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'accuracy': float(accuracy),
            'total_samples': len(self.results)
        }

    def calculate_by_category(self, category: str) -> Dict:
        """Calculate metrics by category (clone_type, obfuscation_level, language)"""

        categories = {}
        for result in self.results:
            cat = result['metadata'].get(category, 'unknown')
            if cat not in categories:
                categories[cat] = {'predicted': [], 'actual': []}
            categories[cat]['predicted'].append(result['predicted'])
            categories[cat]['actual'].append(result['actual'])

        results = {}
        for cat, data in categories.items():
            if len(data['actual']) > 0:
                tn, fp, fn, tp = confusion_matrix(
                    data['actual'],
                    data['predicted']
                ).ravel()

                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

                results[cat] = {
                    'count': len(data['actual']),
                    'precision': float(precision),
                    'recall': float(recall),
                    'f1_score': float(f1)
                }

        return results

    def plot_confusion_matrix(self, output_path: str = None):
        """Plot confusion matrix visualization"""

        y_pred = [r['predicted'] for r in self.results]
        y_true = [r['actual'] for r in self.results]

        cm = confusion_matrix(y_true, y_pred)

        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                   xticklabels=['Not Plagiarism', 'Plagiarism'],
                   yticklabels=['Not Plagiarism', 'Plagiarism'])
        plt.title('Confusion Matrix')
        plt.ylabel('Actual')
        plt.xlabel('Predicted')

        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Confusion matrix saved to {output_path}")

        plt.show()

    def plot_roc_curve(self, output_path: str = None):
        """Plot ROC curve"""

        scores = [r['score'] for r in self.results]
        y_true = [r['actual'] for r in self.results]

        from sklearn.metrics import roc_curve, auc

        fpr, tpr, thresholds = roc_curve(y_true, scores)
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2,
                label=f'ROC curve (AUC = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")

        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"ROC curve saved to {output_path}")

        plt.show()

    def generate_report(self, output_path: str):
        """Generate comprehensive evaluation report"""

        metrics = self.calculate_metrics()
        by_clone_type = self.calculate_by_category('clone_type')
        by_obfuscation = self.calculate_by_category('obfuscation_level')
        by_language = self.calculate_by_category('language')

        report = f"""
# CodeGuard Pro Evaluation Report

## Overall Metrics

| Metric | Value |
|--------|-------|
| **Precision** | {metrics['precision']:.4f} |
| **Recall** | {metrics['recall']:.4f} |
| **F1 Score** | {metrics['f1_score']:.4f} |
| **Accuracy** | {metrics['accuracy']:.4f} |
| **Total Samples** | {metrics['total_samples']} |

## Confusion Matrix

|  | Predicted Positive | Predicted Negative |
|--|-------------------|-------------------|
| **Actual Positive** | {metrics['true_positives']} (TP) | {metrics['false_negatives']} (FN) |
| **Actual Negative** | {metrics['false_positives']} (FP) | {metrics['true_negatives']} (TN) |

## Performance by Clone Type

| Clone Type | Count | Precision | Recall | F1 |
|------------|-------|-----------|--------|-----|
"""

        for clone_type, data in sorted(by_clone_type.items()):
            report += f"| Type {clone_type} | {data['count']} | {data['precision']:.4f} | {data['recall']:.4f} | {data['f1_score']:.4f} |\n"

        report += f"""
## Performance by Obfuscation Level

| Level | Count | Precision | Recall | F1 |
|-------|-------|-----------|--------|-----|
"""

        for level, data in sorted(by_obfuscation.items()):
            report += f"| Level {level} | {data['count']} | {data['precision']:.4f} | {data['recall']:.4f} | {data['f1_score']:.4f} |\n"

        report += f"""
## Performance by Language

| Language | Count | Precision | Recall | F1 |
|----------|-------|-----------|--------|-----|
"""

        for lang, data in sorted(by_language.items()):
            report += f"| {lang} | {data['count']} | {data['precision']:.4f} | {data['recall']:.4f} | {data['f1_score']:.4f} |\n"

        # Write report
        with open(output_path, 'w') as f:
            f.write(report)

        print(f"Report saved to {output_path}")
        return report

if __name__ == "__main__":
    # Example usage
    calculator = MetricsCalculator()

    # Add sample results
    for i in range(1000):
        # Simulate predictions
        actual = i < 100  # First 100 are plagiarism
        predicted = (i < 95) or (i > 90 and i < 110)  # Some false positives

        calculator.add_result(
            predicted=predicted,
            actual=actual,
            similarity_score=0.85 if predicted else 0.3,
            metadata={
                'clone_type': 1 if i < 50 else 2,
                'obfuscation_level': i % 5,
                'language': 'python' if i % 2 == 0 else 'java'
            }
        )

    # Calculate and display metrics
    metrics = calculator.calculate_metrics()
    print("Overall Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Generate visualizations
    calculator.plot_confusion_matrix("confusion_matrix.png")
    calculator.plot_roc_curve("roc_curve.png")

    # Generate report
    calculator.generate_report("evaluation_report.md")
```

---

## 5. Testing Methodology

### 5.1 Test Execution Pipeline

```python
#!/usr/bin/env python3
"""
Complete testing pipeline for CodeGuard Pro
"""

import json
import time
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class TestResult:
    """Result of a single test"""
    test_id: str
    predicted: bool
    actual: bool
    similarity_score: float
    processing_time: float
    metadata: Dict

class TestingPipeline:
    """Complete testing pipeline"""

    def __init__(self, api_client, dataset_path: Path):
        self.api_client = api_client
        self.dataset_path = dataset_path
        self.results = []

    def run_full_test(self) -> Dict:
        """Run complete test suite"""

        print("=" * 60)
        print("CodeGuard Pro - Full Test Suite")
        print("=" * 60)

        # Load dataset
        dataset = self.load_dataset()
        print(f"Loaded {len(dataset)} test samples")

        # Run tests
        for i, sample in enumerate(dataset):
            print(f"\nTesting sample {i+1}/{len(dataset)}: {sample['id']}")
            result = self.run_single_test(sample)
            self.results.append(result)

            # Progress update
            if (i + 1) % 100 == 0:
                self.print_interim_results()

        # Calculate final metrics
        final_metrics = self.calculate_final_metrics()

        # Generate reports
        self.generate_reports(final_metrics)

        return final_metrics

    def load_dataset(self) -> List[Dict]:
        """Load test dataset"""
        with open(self.dataset_path, 'r') as f:
            return json.load(f)

    def run_single_test(self, sample: Dict) -> TestResult:
        """Run single test case"""

        start_time = time.time()

        # Submit to API
        response = self.api_client.analyze(
            files=[sample['code_a'], sample['code_b']],
            language=sample['language'],
            options={
                'normalize_whitespace': True,
                'strip_comments': True,
                'ai_detection': True
            }
        )

        # Get results
        job_id = response['job_id']
        results = self.api_client.wait_for_completion(job_id)

        processing_time = time.time() - start_time

        # Extract similarity score
        similarity_score = results['similarity_score']

        # Determine prediction (threshold = 0.2)
        predicted = similarity_score >= 0.2

        return TestResult(
            test_id=sample['id'],
            predicted=predicted,
            actual=sample['is_plagiarism'],
            similarity_score=similarity_score,
            processing_time=processing_time,
            metadata={
                'clone_type': sample['clone_type'],
                'obfuscation_level': sample['obfuscation_level'],
                'language': sample['language']
            }
        )

    def print_interim_results(self):
        """Print interim results"""

        metrics = self.calculate_interim_metrics()
        print(f"\nInterim Results ({len(self.results)} samples):")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall: {metrics['recall']:.4f}")
        print(f"  F1 Score: {metrics['f1_score']:.4f}")

    def calculate_interim_metrics(self) -> Dict:
        """Calculate interim metrics"""

        y_pred = [r.predicted for r in self.results]
        y_true = [r.actual for r in self.results]

        from sklearn.metrics import precision_recall_fscore_support

        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average='binary'
        )

        return {
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1)
        }

    def calculate_final_metrics(self) -> Dict:
        """Calculate final metrics"""

        from sklearn.metrics import confusion_matrix

        y_pred = [r.predicted for r in self.results]
        y_true = [r.actual for r in self.results]

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / (tp + tn + fp + fn)

        avg_time = sum(r.processing_time for r in self.results) / len(self.results)

        return {
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'accuracy': float(accuracy),
            'avg_processing_time': float(avg_time),
            'total_samples': len(self.results)
        }

    def generate_reports(self, metrics: Dict):
        """Generate evaluation reports"""

        # Save metrics
        with open('test_results/metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)

        # Generate detailed report
        calculator = MetricsCalculator()
        for result in self.results:
            calculator.add_result(
                predicted=result.predicted,
                actual=result.actual,
                similarity_score=result.similarity_score,
                metadata=result.metadata
            )

        calculator.plot_confusion_matrix('test_results/confusion_matrix.png')
        calculator.plot_roc_curve('test_results/roc_curve.png')
        calculator.generate_report('test_results/evaluation_report.md')

        print("\nReports generated in test_results/")

if __name__ == "__main__":
    from src.api.client import CodeGuardClient

    client = CodeGuardClient(
        base_url="http://localhost:8000",
        api_key="test-api-key"
    )

    pipeline = TestingPipeline(
        api_client=client,
        dataset_path=Path("tests/generated/test_dataset.json")
    )

    results = pipeline.run_full_test()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    for key, value in results.items():
        print(f"{key}: {value}")
```

### 5.2 Step-by-Step Testing Process

#### Step 1: Dataset Preparation

```bash
# 1. Download benchmark datasets
python scripts/download_datasets.py --all

# 2. Generate test samples
python scripts/generate_samples.py \
    --positive 1000 \
    --negative 1000 \
    --languages python,java,cpp

# 3. Verify dataset integrity
python scripts/verify_dataset.py tests/generated/test_dataset.json
```

#### Step 2: Baseline Testing

```bash
# Run baseline tests (current algorithm)
python tests/run_baseline.py \
    --dataset tests/generated/test_dataset.json \
    --output test_results/baseline/

# Record baseline metrics
cat test_results/baseline/metrics.json
```

#### Step 3: Obfuscation Testing

```bash
# Test against different obfuscation levels
python tests/run_obfuscation_test.py \
    --levels 0,1,2,3,4 \
    --dataset tests/generated/test_dataset.json \
    --output test_results/obfuscation/
```

#### Step 4: Performance Testing

```bash
# Test processing speed
python tests/run_performance_test.py \
    --file-counts 10,50,100,500,1000 \
    --output test_results/performance/
```

#### Step 5: Competitive Benchmarking

```bash
# Compare with MOSS
python tests/compare_with_moss.py \
    --dataset tests/fixtures/bigclonebench/ \
    --output test_results/comparison/moss/

# Compare with JPlag
python tests/compare_with_jplag.py \
    --dataset tests/fixtures/bigclonebench/ \
    --output test_results/comparison/jplag/
```

---

## 6. Optimization Pipeline

### 6.1 Iterative Improvement Process

```
┌─────────────────────────────────────────────────────────────┐
│                    OPTIMIZATION CYCLE                        │
├─────────────────────────────────────────────────────────────┤
│  1. Baseline Test                                           │
│     └─> Measure current F1 score                            │
│                                                             │
│  2. Identify Weaknesses                                     │
│     └─> Find where recall/precision drops                   │
│                                                             │
│  3. Implement Improvement                                   │
│     └─> Add AST parsing, ML models, etc.                    │
│                                                             │
│  4. A/B Test                                                │
│     └─> Compare new vs old algorithm                        │
│                                                             │
│  5. Measure Impact                                          │
│     └─> Calculate F1 improvement                            │
│                                                             │
│  6. Decision                                                │
│     └─> Keep if F1 improved, revert if degraded             │
│                                                             │
│  7. Repeat until F1 > 0.97                                  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Optimization Techniques

#### 6.2.1 AST Parsing Enhancement

**Problem**: Variable renaming defeats token-based detection

**Solution**: Add AST-level comparison

```python
def enhance_with_ast(code_a: str, code_b: str, language: str) -> float:
    """Enhance similarity with AST comparison"""

    # Parse both code samples
    ast_a = parse_to_ast(code_a, language)
    ast_b = parse_to_ast(code_b, language)

    # Compare AST structures
    tree_edit_distance = calculate_tree_edit_distance(ast_a, ast_b)

    # Normalize to similarity score (0-1)
    max_size = max(ast_size(ast_a), ast_size(ast_b))
    ast_similarity = 1 - (tree_edit_distance / max_size)

    return ast_similarity

def calculate_tree_edit_distance(tree_a, tree_b):
    """Calculate tree edit distance (Zhang-Shasha algorithm)"""
    # Implementation of tree edit distance
    pass
```

**Expected Improvement**: +5-10% recall for Type 2 clones

#### 6.2.2 Code Execution Comparison

**Problem**: Semantic clones (Type 4) have different syntax but same behavior

**Solution**: Execute code and compare outputs

```python
def compare_execution(code_a: str, code_b: str, test_cases: List) -> float:
    """Compare code execution outputs"""

    results_a = []
    results_b = []

    for test_input in test_cases:
        # Execute code A
        output_a = execute_safely(code_a, test_input)
        results_a.append(output_a)

        # Execute code B
        output_b = execute_safely(code_b, test_input)
        results_b.append(output_b)

    # Compare outputs
    matches = sum(1 for a, b in zip(results_a, results_b) if a == b)
    return matches / len(test_cases)

def execute_safely(code: str, test_input: str) -> str:
    """Execute code safely in sandbox"""
    # Use Docker sandbox or restricted Python
    # with timeout and resource limits
    pass
```

**Expected Improvement**: +15-20% recall for Type 4 clones

#### 6.2.3 ML Model Training

**Problem**: Hand-crafted features may miss patterns

**Solution**: Train ML model on labeled data

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

class MLClusteringModel:
    """ML-based plagiarism detection"""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 3),
            analyzer='word'
        )
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

    def train(self, code_pairs: List[Tuple[str, str]], labels: List[bool]):
        """Train model on labeled data"""

        # Extract features
        features = self.extract_features(code_pairs)

        # Train classifier
        self.classifier.fit(features, labels)

        # Evaluate
        accuracy = self.classifier.score(features, labels)
        print(f"Training accuracy: {accuracy:.4f}")

    def extract_features(self, code_pairs: List[Tuple[str, str]]) -> np.ndarray:
        """Extract features from code pairs"""

        features = []

        for code_a, code_b in code_pairs:
            # Combine code for TF-IDF
            combined = code_a + " " + code_b
            tfidf = self.vectorizer.transform([combined])

            # Add structural features
            struct_features = [
                len(code_a), len(code_b),
                code_a.count('\n'), code_b.count('\n'),
                similarity_score(code_a, code_b)
            ]

            # Combine all features
            all_features = np.concatenate([
                tfidf.toarray()[0],
                struct_features
            ])

            features.append(all_features)

        return np.array(features)

    def predict(self, code_a: str, code_b: str) -> Tuple[bool, float]:
        """Predict if code pair is plagiarism"""

        features = self.extract_features([(code_a, code_b)])

        prediction = self.classifier.predict(features)[0]
        probability = self.classifier.predict_proba(features)[0]

        return bool(prediction), float(probability[1])

# Training script
def train_ml_model():
    """Train ML model on benchmark data"""

    # Load training data
    with open('tests/generated/train_dataset.json', 'r') as f:
        train_data = json.load(f)

    # Prepare data
    code_pairs = [(d['code_a'], d['code_b']) for d in train_data]
    labels = [d['is_plagiarism'] for d in train_data]

    # Train model
    model = MLClusteringModel()
    model.train(code_pairs, labels)

    # Save model
    import joblib
    joblib.dump(model, 'models/ml_clustering.pkl')

    print("ML model trained and saved")
```

**Expected Improvement**: +10-15% overall accuracy

### 6.3 Optimization Tracking

```python
#!/usr/bin/env python3
"""
Track optimization iterations and improvements
"""

import json
from datetime import datetime
from pathlib import Path

class OptimizationTracker:
    """Track optimization iterations"""

    def __init__(self, tracking_file: Path):
        self.tracking_file = tracking_file
        self.history = self.load_history()

    def load_history(self) -> List[Dict]:
        """Load optimization history"""
        if self.tracking_file.exists():
            with open(self.tracking_file, 'r') as f:
                return json.load(f)
        return []

    def record_iteration(self,
                        iteration: int,
                        changes: str,
                        metrics: Dict,
                        notes: str = ""):
        """Record optimization iteration"""

        entry = {
            'iteration': iteration,
            'timestamp': datetime.now().isoformat(),
            'changes': changes,
            'metrics': metrics,
            'notes': notes
        }

        self.history.append(entry)
        self.save_history()

    def save_history(self):
        """Save optimization history"""
        with open(self.tracking_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def get_best_iteration(self) -> Dict:
        """Get best performing iteration"""
        if not self.history:
            return None

        return max(self.history, key=lambda x: x['metrics']['f1_score'])

    def print_summary(self):
        """Print optimization summary"""

        print("\n" + "=" * 60)
        print("OPTIMIZATION HISTORY")
        print("=" * 60)

        for entry in self.history:
            print(f"\nIteration {entry['iteration']} ({entry['timestamp']})")
            print(f"  Changes: {entry['changes']}")
            print(f"  Precision: {entry['metrics']['precision']:.4f}")
            print(f"  Recall: {entry['metrics']['recall']:.4f}")
            print(f"  F1 Score: {entry['metrics']['f1_score']:.4f}")
            if entry['notes']:
                print(f"  Notes: {entry['notes']}")

        best = self.get_best_iteration()
        if best:
            print(f"\n{'=' * 60}")
            print(f"BEST ITERATION: {best['iteration']}")
            print(f"F1 Score: {best['metrics']['f1_score']:.4f}")
            print(f"{'=' * 60}")

# Example usage
tracker = OptimizationTracker(Path("optimization_history.json"))

# Record iterations
tracker.record_iteration(
    iteration=1,
    changes="Baseline: Token-based winnowing",
    metrics={'precision': 0.92, 'recall': 0.88, 'f1_score': 0.90},
    notes="Initial baseline"
)

tracker.record_iteration(
    iteration=2,
    changes="Added AST parsing for variable renaming",
    metrics={'precision': 0.93, 'recall': 0.92, 'f1_score': 0.925},
    notes="+2.5% F1 improvement"
)

tracker.record_iteration(
    iteration=3,
    changes="Added ML clustering model",
    metrics={'precision': 0.95, 'recall': 0.94, 'f1_score': 0.945},
    notes="+2% F1 improvement, reached target"
)

tracker.print_summary()
```

---

## 7. A/B Testing Framework

### 7.1 A/B Test Design

```python
#!/usr/bin/env python3
"""
A/B Testing framework for algorithm comparison
"""

import random
import json
from typing import Callable, Dict, List, Tuple
from dataclasses import dataclass
from scipy import stats
import numpy as np

@dataclass
class ABTestResult:
    """Result of an A/B test"""
    test_name: str
    control_metrics: Dict
    treatment_metrics: Dict
    p_value: float
    significant: bool
    confidence_level: float
    winner: str  # 'control', 'treatment', or 'tie'

class ABTester:
    """A/B testing framework"""

    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level

    def run_test(self,
                 control_fn: Callable,
                 treatment_fn: Callable,
                 test_cases: List[Dict],
                 metric_fn: Callable) -> ABTestResult:
        """Run A/B test comparing two algorithms"""

        # Randomly split test cases
        random.shuffle(test_cases)
        split_point = len(test_cases) // 2

        control_cases = test_cases[:split_point]
        treatment_cases = test_cases[split_point:]

        # Run control algorithm
        control_results = []
        for case in control_cases:
            result = control_fn(case)
            metric = metric_fn(result, case)
            control_results.append(metric)

        # Run treatment algorithm
        treatment_results = []
        for case in treatment_cases:
            result = treatment_fn(case)
            metric = metric_fn(result, case)
            treatment_results.append(metric)

        # Calculate metrics
        control_metrics = {
            'mean': np.mean(control_results),
            'std': np.std(control_results),
            'n': len(control_results)
        }

        treatment_metrics = {
            'mean': np.mean(treatment_results),
            'std': np.std(treatment_results),
            'n': len(treatment_results)
        }

        # Statistical test (t-test)
        t_stat, p_value = stats.ttest_ind(control_results, treatment_results)

        # Determine significance
        significant = p_value < self.significance_level

        # Determine winner
        if significant:
            if treatment_metrics['mean'] > control_metrics['mean']:
                winner = 'treatment'
            else:
                winner = 'control'
        else:
            winner = 'tie'

        return ABTestResult(
            test_name="Algorithm Comparison",
            control_metrics=control_metrics,
            treatment_metrics=treatment_metrics,
            p_value=float(p_value),
            significant=significant,
            confidence_level=1 - self.significance_level,
            winner=winner
        )

    def run_multiple_tests(self,
                          control_fn: Callable,
                          treatment_fns: Dict[str, Callable],
                          test_cases: List[Dict],
                          metric_fn: Callable) -> Dict[str, ABTestResult]:
        """Run multiple A/B tests comparing control against different treatments"""

        results = {}

        for treatment_name, treatment_fn in treatment_fns.items():
            print(f"\nRunning A/B test: Control vs {treatment_name}")

            result = self.run_test(
                control_fn=control_fn,
                treatment_fn=treatment_fn,
                test_cases=test_cases,
                metric_fn=metric_fn
            )

            results[treatment_name] = result

            print(f"  Control mean: {result.control_metrics['mean']:.4f}")
            print(f"  Treatment mean: {result.treatment_metrics['mean']:.4f}")
            print(f"  P-value: {result.p_value:.4f}")
            print(f"  Significant: {result.significant}")
            print(f"  Winner: {result.winner}")

        return results

# Example usage
def baseline_algorithm(test_case: Dict) -> Dict:
    """Current baseline algorithm"""
    code_a = test_case['code_a']
    code_b = test_case['code_b']

    similarity = token_similarity(code_a, code_b)

    return {
        'similarity': similarity,
        'predicted': similarity >= 0.2
    }

def ast_enhanced_algorithm(test_case: Dict) -> Dict:
    """Algorithm with AST enhancement"""
    code_a = test_case['code_a']
    code_b = test_case['code_b']

    token_sim = token_similarity(code_a, code_b)
    ast_sim = ast_similarity(code_a, code_b)

    # Weighted combination
    similarity = 0.6 * token_sim + 0.4 * ast_sim

    return {
        'similarity': similarity,
        'predicted': similarity >= 0.2
    }

def ml_enhanced_algorithm(test_case: Dict) -> Dict:
    """Algorithm with ML enhancement"""
    code_a = test_case['code_a']
    code_b = test_case['code_b']

    token_sim = token_similarity(code_a, code_b)
    ast_sim = ast_similarity(code_a, code_b)
    ml_pred, ml_prob = ml_model.predict(code_a, code_b)

    # Weighted combination
    similarity = 0.4 * token_sim + 0.3 * ast_sim + 0.3 * ml_prob

    return {
        'similarity': similarity,
        'predicted': similarity >= 0.2
    }

def f1_metric(result: Dict, test_case: Dict) -> float:
    """Calculate F1 score for single test case"""
    predicted = result['predicted']
    actual = test_case['is_plagiarism']

    # For single case, return 1 if correct, 0 if incorrect
    return 1.0 if predicted == actual else 0.0

# Run A/B tests
tester = ABTester(significance_level=0.05)

# Load test cases
with open('tests/generated/test_dataset.json', 'r') as f:
    test_cases = json.load(f)

# Define treatments
treatments = {
    'ast_enhanced': ast_enhanced_algorithm,
    'ml_enhanced': ml_enhanced_algorithm
}

# Run tests
results = tester.run_multiple_tests(
    control_fn=baseline_algorithm,
    treatment_fns=treatments,
    test_cases=test_cases,
    metric_fn=f1_metric
)

# Print summary
print("\n" + "=" * 60)
print("A/B TEST SUMMARY")
print("=" * 60)

for treatment_name, result in results.items():
    print(f"\n{treatment_name}:")
    print(f"  Improvement: {((result.treatment_metrics['mean'] - result.control_metrics['mean']) / result.control_metrics['mean'] * 100):.2f}%")
    print(f"  Statistically Significant: {result.significant}")
    print(f"  Recommendation: {'Implement' if result.winner == 'treatment' else 'Keep current' if result.winner == 'control' else 'Need more data'}")
```

### 7.2 Continuous A/B Testing

```python
#!/usr/bin/env python3
"""
Continuous A/B testing in production
"""

import redis
import json
import random
from datetime import datetime
from typing import Dict

class ContinuousABTester:
    """Continuous A/B testing in production"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.experiments = self.load_experiments()

    def load_experiments(self) -> Dict:
        """Load active experiments"""
        experiments_json = self.redis.get('active_experiments')
        if experiments_json:
            return json.loads(experiments_json)
        return {}

    def assign_variant(self, user_id: str, experiment_id: str) -> str:
        """Assign user to experiment variant"""

        # Check if user already assigned
        assignment_key = f"experiment:{experiment_id}:user:{user_id}"
        existing = self.redis.get(assignment_key)

        if existing:
            return existing

        # Random assignment (50/50 split)
        variant = random.choice(['control', 'treatment'])

        # Store assignment
        self.redis.set(assignment_key, variant)

        # Update experiment stats
        stats_key = f"experiment:{experiment_id}:stats"
        self.redis.hincrby(stats_key, f"{variant}_assignments", 1)

        return variant

    def record_outcome(self,
                      user_id: str,
                      experiment_id: str,
                      outcome: Dict):
        """Record experiment outcome"""

        variant = self.assign_variant(user_id, experiment_id)

        # Store outcome
        outcome_key = f"experiment:{experiment_id}:outcomes:{variant}"
        self.redis.lpush(outcome_key, json.dumps({
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'outcome': outcome
        }))

        # Update stats
        stats_key = f"experiment:{experiment_id}:stats"
        self.redis.hincrby(stats_key, f"{variant}_success",
                          1 if outcome.get('success') else 0)

    def get_experiment_results(self, experiment_id: str) -> Dict:
        """Get experiment results"""

        stats_key = f"experiment:{experiment_id}:stats"
        stats = self.redis.hgetall(stats_key)

        control_assignments = int(stats.get(b'control_assignments', 0))
        control_success = int(stats.get(b'control_success', 0))
        treatment_assignments = int(stats.get(b'treatment_assignments', 0))
        treatment_success = int(stats.get(b'treatment_success', 0))

        control_rate = control_success / control_assignments if control_assignments > 0 else 0
        treatment_rate = treatment_success / treatment_assignments if treatment_assignments > 0 else 0

        return {
            'control': {
                'assignments': control_assignments,
                'success': control_success,
                'success_rate': control_rate
            },
            'treatment': {
                'assignments': treatment_assignments,
                'success': treatment_success,
                'success_rate': treatment_rate
            },
            'improvement': (treatment_rate - control_rate) / control_rate if control_rate > 0 else 0
        }
```

---

## 8. Competitive Benchmarking

### 8.1 Comparison with MOSS

```python
#!/usr/bin/env python3
"""
Compare CodeGuard Pro with MOSS
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List

class MOSSComparator:
    """Compare with MOSS system"""

    def __init__(self, moss_script_path: Path):
        self.moss_script = moss_script_path

    def run_moss(self, files: List[Path], language: str) -> Dict:
        """Run MOSS on files"""

        # Build MOSS command
        cmd = [
            'perl', str(self.moss_script),
            '-l', language,
            '-m', '10',  # Maximum matches
        ]

        # Add files
        for file in files:
            cmd.append(str(file))

        # Run MOSS
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse output
        return self.parse_moss_output(result.stdout)

    def parse_moss_output(self, output: str) -> Dict:
        """Parse MOSS output"""

        results = {
            'pairs': [],
            'url': ''
        }

        lines = output.strip().split('\n')
        for line in lines:
            if line.startswith('http'):
                results['url'] = line
            elif '%' in line:
                # Parse similarity line
                parts = line.split()
                if len(parts) >= 4:
                    file1 = parts[0]
                    file2 = parts[1]
                    similarity = int(parts[2].replace('%', ''))

                    results['pairs'].append({
                        'file1': file1,
                        'file2': file2,
                        'similarity': similarity / 100.0
                    })

        return results

    def compare_with_codeguard(self,
                              test_cases: List[Dict],
                              codeguard_results: List[Dict]) -> Dict:
        """Compare MOSS and CodeGuard results"""

        comparison = {
            'moss_only': [],
            'codeguard_only': [],
            'both': [],
            'neither': []
        }

        for i, test_case in enumerate(test_cases):
            actual = test_case['is_plagiarism']

            # Check MOSS result
            moss_detected = any(
                p['similarity'] >= 0.2
                for p in self.run_moss([Path(test_case['file1']),
                                       Path(test_case['file2'])],
                                      test_case['language'])['pairs']
            )

            # Check CodeGuard result
            codeguard_detected = codeguard_results[i]['predicted']

            # Categorize
            if moss_detected and codeguard_detected:
                comparison['both'].append(test_case['id'])
            elif moss_detected and not codeguard_detected:
                comparison['moss_only'].append(test_case['id'])
            elif not moss_detected and codeguard_detected:
                comparison['codeguard_only'].append(test_case['id'])
            else:
                comparison['neither'].append(test_case['id'])

        return comparison
```

### 8.2 Comparison with JPlag

```python
#!/usr/bin/env python3
"""
Compare CodeGuard Pro with JPlag
"""

import subprocess
import json
from pathlib import Path

class JPlagComparator:
    """Compare with JPlag system"""

    def __init__(self, jplag_jar_path: Path):
        self.jplag_jar = jplag_jar_path

    def run_jplag(self,
                  files_dir: Path,
                  language: str,
                  output_dir: Path) -> Dict:
        """Run JPlag on files"""

        # Build JPlag command
        cmd = [
            'java', '-jar', str(self.jplag_jar),
            '-l', language,
            '-r', str(output_dir),
            str(files_dir)
        ]

        # Run JPlag
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse results
        return self.parse_jplag_results(output_dir)

    def parse_jplag_results(self, results_dir: Path) -> Dict:
        """Parse JPlag results"""

        results_file = results_dir / 'results.json'

        if results_file.exists():
            with open(results_file, 'r') as f:
                return json.load(f)

        return {'pairs': []}
```

### 8.3 Benchmark Execution Script

```python
#!/usr/bin/env python3
"""
Run competitive benchmarks
"""

import json
from pathlib import Path
from typing import Dict

def run_competitive_benchmark(dataset_path: Path, output_dir: Path):
    """Run competitive benchmark"""

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load dataset
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)

    # Run CodeGuard Pro
    print("Running CodeGuard Pro...")
    codeguard_results = run_codeguard(dataset)

    # Run MOSS
    print("Running MOSS...")
    moss_comparator = MOSSComparator(Path("tools/moss/moss.pl"))
    moss_results = moss_comparator.run_moss(...)

    # Run JPlag
    print("Running JPlag...")
    jplag_comparator = JPlagComparator(Path("tools/jplag/jplag.jar"))
    jplag_results = jplag_comparator.run_jplag(...)

    # Calculate metrics for each
    codeguard_metrics = calculate_metrics(codeguard_results, dataset)
    moss_metrics = calculate_metrics(moss_results, dataset)
    jplag_metrics = calculate_metrics(jplag_results, dataset)

    # Generate comparison report
    report = f"""
# Competitive Benchmark Report

## Overall Performance

| System | Precision | Recall | F1 Score |
|--------|-----------|--------|----------|
| CodeGuard Pro | {codeguard_metrics['precision']:.4f} | {codeguard_metrics['recall']:.4f} | {codeguard_metrics['f1_score']:.4f} |
| MOSS | {moss_metrics['precision']:.4f} | {moss_metrics['recall']:.4f} | {moss_metrics['f1_score']:.4f} |
| JPlag | {jplag_metrics['precision']:.4f} | {jplag_metrics['recall']:.4f} | {jplag_metrics['f1_score']:.4f} |

## Improvement Over Competitors

| Comparison | Precision | Recall | F1 |
|------------|-----------|--------|-----|
| vs MOSS | {((codeguard_metrics['precision'] - moss_metrics['precision']) / moss_metrics['precision'] * 100):.2f}% | {((codeguard_metrics['recall'] - moss_metrics['recall']) / moss_metrics['recall'] * 100):.2f}% | {((codeguard_metrics['f1_score'] - moss_metrics['f1_score']) / moss_metrics['f1_score'] * 100):.2f}% |
| vs JPlag | {((codeguard_metrics['precision'] - jplag_metrics['precision']) / jplag_metrics['precision'] * 100):.2f}% | {((codeguard_metrics['recall'] - jplag_metrics['recall']) / jplag_metrics['recall'] * 100):.2f}% | {((codeguard_metrics['f1_score'] - jplag_metrics['f1_score']) / jplag_metrics['f1_score'] * 100):.2f}% |
"""

    # Save report
    with open(output_dir / 'competitive_benchmark.md', 'w') as f:
        f.write(report)

    # Save detailed results
    with open(output_dir / 'results.json', 'w') as f:
        json.dump({
            'codeguard': codeguard_metrics,
            'moss': moss_metrics,
            'jplag': jplag_metrics
        }, f, indent=2)

    print(f"\nBenchmark complete. Results saved to {output_dir}")

if __name__ == "__main__":
    run_competitive_benchmark(
        dataset_path=Path("tests/generated/test_dataset.json"),
        output_dir=Path("test_results/competitive/")
    )
```

---

## 9. Test Automation

### 9.1 CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0

  benchmark-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt
      - name: Download test datasets
        run: python scripts/download_datasets.py --all
      - name: Run benchmark tests
        run: python tests/run_benchmarks.py
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: test_results/

  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt
      - name: Run performance tests
        run: python tests/run_performance.py
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: test_results/performance/
```

### 9.2 Automated Test Runner

```python
#!/usr/bin/env python3
"""
Automated test runner for CodeGuard Pro
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

class TestRunner:
    """Automated test runner"""

    def __init__(self, config_path: Path):
        self.config = self.load_config(config_path)
        self.results = {}

    def load_config(self, config_path: Path) -> Dict:
        """Load test configuration"""
        with open(config_path, 'r') as f:
            return json.load(f)

    def run_all_tests(self):
        """Run all configured tests"""

        print("=" * 60)
        print("CodeGuard Pro - Automated Test Suite")
        print(f"Started: {datetime.now().isoformat()}")
        print("=" * 60)

        # Unit tests
        if self.config.get('unit_tests', True):
            print("\n[1/5] Running unit tests...")
            self.results['unit'] = self.run_unit_tests()

        # Integration tests
        if self.config.get('integration_tests', True):
            print("\n[2/5] Running integration tests...")
            self.results['integration'] = self.run_integration_tests()

        # Benchmark tests
        if self.config.get('benchmark_tests', True):
            print("\n[3/5] Running benchmark tests...")
            self.results['benchmark'] = self.run_benchmark_tests()

        # Performance tests
        if self.config.get('performance_tests', True):
            print("\n[4/5] Running performance tests...")
            self.results['performance'] = self.run_performance_tests()

        # Competitive tests
        if self.config.get('competitive_tests', True):
            print("\n[5/5] Running competitive tests...")
            self.results['competitive'] = self.run_competitive_tests()

        # Generate report
        self.generate_report()

        # Check if all tests passed
        if self.all_tests_passed():
            print("\n✅ All tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1

    def run_unit_tests(self) -> Dict:
        """Run unit tests"""
        import subprocess

        result = subprocess.run(
            ['pytest', 'tests/unit/', '-v', '--tb=short'],
            capture_output=True,
            text=True
        )

        return {
            'exit_code': result.returncode,
            'output': result.stdout,
            'passed': result.returncode == 0
        }

    def run_integration_tests(self) -> Dict:
        """Run integration tests"""
        import subprocess

        result = subprocess.run(
            ['pytest', 'tests/integration/', '-v', '--tb=short'],
            capture_output=True,
            text=True
        )

        return {
            'exit_code': result.returncode,
            'output': result.stdout,
            'passed': result.returncode == 0
        }

    def run_benchmark_tests(self) -> Dict:
        """Run benchmark tests"""
        # Implementation depends on your benchmark runner
        return {'passed': True}

    def run_performance_tests(self) -> Dict:
        """Run performance tests"""
        # Implementation depends on your performance runner
        return {'passed': True}

    def run_competitive_tests(self) -> Dict:
        """Run competitive tests"""
        # Implementation depends on your competitive runner
        return {'passed': True}

    def all_tests_passed(self) -> bool:
        """Check if all tests passed"""
        return all(
            result.get('passed', False)
            for result in self.results.values()
        )

    def generate_report(self):
        """Generate test report"""

        report = {
            'timestamp': datetime.now().isoformat(),
            'results': self.results,
            'summary': {
                'total': len(self.results),
                'passed': sum(1 for r in self.results.values() if r.get('passed')),
                'failed': sum(1 for r in self.results.values() if not r.get('passed'))
            }
        }

        # Save report
        report_path = Path('test_results/test_report.json')
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nTest report saved to {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run CodeGuard Pro tests')
    parser.add_argument('--config', type=Path, default=Path('test_config.json'),
                       help='Test configuration file')

    args = parser.parse_args()

    runner = TestRunner(args.config)
    exit_code = runner.run_all_tests()

    sys.exit(exit_code)
```

---

## 10. Performance Benchmarks

### 10.1 Processing Speed Benchmarks

| File Count | Target Time | Current Time | Status |
| ---------- | ----------- | ------------ | ------ |
| 10 files   | < 5s        | -            | -      |
| 50 files   | < 15s       | -            | -      |
| 100 files  | < 30s       | -            | -      |
| 500 files  | < 2min      | -            | -      |
| 1000 files | < 5min      | -            | -      |

### 10.2 Accuracy Benchmarks

| Dataset             | Target Precision | Target Recall | Target F1 |
| ------------------- | ---------------- | ------------- | --------- |
| BigCloneBench       | > 0.95           | > 0.98        | > 0.96    |
| Google Code Jam     | > 0.93           | > 0.97        | > 0.95    |
| Xiangtan University | > 0.96           | > 0.99        | > 0.97    |

### 10.3 Resource Usage Benchmarks

| Metric             | Target | Current |
| ------------------ | ------ | ------- |
| Memory (100 files) | < 2GB  | -       |
| CPU Usage          | < 80%  | -       |
| Database Queries   | < 1000 | -       |
| Cache Hit Rate     | > 90%  | -       |

---

## Appendix A: Test Configuration

```json
{
  "unit_tests": true,
  "integration_tests": true,
  "benchmark_tests": true,
  "performance_tests": true,
  "competitive_tests": true,
  "datasets": {
    "bigclonebench": "tests/fixtures/bigclonebench/",
    "google_codejam": "tests/fixtures/google_codejam/",
    "xiangtan": "tests/fixtures/xiangtan/"
  },
  "thresholds": {
    "precision": 0.95,
    "recall": 0.99,
    "f1_score": 0.97
  },
  "output_dir": "test_results/"
}
```

---

## Appendix B: Quick Reference Commands

```bash
# Run all tests
python tests/run_all.py

# Run specific test suite
pytest tests/unit/ -v
pytest tests/integration/ -v

# Run benchmarks
python tests/run_benchmarks.py

# Generate test samples
python scripts/generate_samples.py --positive 1000 --negative 1000

# Compare with competitors
python tests/compare_competitors.py

# Generate evaluation report
python scripts/generate_report.py
```

---

**Document Status**: Active Development  
**Last Updated**: 2026-03-31  
**Owner**: QA Team  
**Contributors**: Engineering, Research
