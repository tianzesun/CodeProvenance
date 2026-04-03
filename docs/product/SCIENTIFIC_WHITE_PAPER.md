# Scientific White Paper: IntegrityDesk Forensic Methodology

> **A Defensible Scientific Benchmarking Infrastructure for Code Similarity Research**

IntegrityDesk was engineered to provide more than just a score. It provides a **defensible scientific proof**. This white paper outlines the core methodologies used to achieve a target F1-score of >0.92 while maintaining less than 1% false positives.

---

## 1. Multi-Engine Fusion Architecture

Legacy tools like MOSS (Winnowing) or JPlag (AST) rely on a single algorithm. IntegrityDesk uses a **Hybrid Multi-Engine Fusion** model, combining four independent forensic signals:

| Engine | Detection Type | Resistance |
|--------|----------------|------------|
| **AST Analysis** | Structural | Resistant to variable renaming and reordering. |
| **Token-Level** | Lexical | Resistant to formatting and white-space changes. |
| **Code Stylometry** | Authorship | Detects unique stylistic markers (naming, comments, structure). |
| **Semantic Embedding** | Logic | Uses LLM vectors to detect behaviorally identical code. |

---

## 2. Bayesian Arbitration Layer (Addressing Risk 2)

Simple averaging of engine scores leads to "Metric Inflation." IntegrityDesk implements a **Bayesian Arbitration Layer** (`src/evaluation/arbitration.py`):

1.  **Engine Precision Priors**: Each engine is assigned a precision score (inverse variance) based on its historical reliability.
2.  **Probabilistic Update**: The fused score is calculated as a posterior mean, weighting each engine's signal by its confidence.
3.  **Agreement Index**: A quantitative measure of consensus between engines. A high score with a low Agreement Index is flagged as "Conflicting Evidence," preventing false positives.
4.  **Uncertainty Margin**: A 95% confidence interval is computed for every result, providing a statistical bound for the committee's decision.

---

## 3. Code Stylometry (Authorship Fingerprinting)

To distinguish between two students writing independent code and a student copying another, we analyze **Stylometric Markers** (`src/engines/features/stylometry.py`):

- **Variable Naming Habits**: Snake_case vs camelCase preferences.
- **Structural Distributions**: Function length and indentation depth.
- **Language Feature Density**: Use of Pythonic idioms like list comprehensions or decorators.
- **Comment Analysis**: Comment density and position.

By comparing these markers, the system can identify "Style Leakage," where a student's natural coding style is replaced by that of another author.

---

## 4. Semantic Behavior Comparison (Type 4 Clones)

The system includes a **Black-Box Execution Similarity** engine (`src/engines/similarity/execution_similarity.py`):

1.  **Input Generation**: Automatically generates test cases for the code.
2.  **Sandbox Execution**: Runs both submissions in isolated environments.
3.  **Behavioral Matching**: Compares the stdout/stderr and return codes.

This detects "Type 4 Clones"—code that is syntactically different (different algorithms, different variables) but behaviorally identical.

---

## 5. Dataset Governance & Integrity (Addressing Risk 3)

IntegrityDesk enforces the highest standards of data integrity via the **Governance Layer** (`src/evaluation/dataset/governance.py`):

- **SHA-256 Fingerprinting**: Every code sample is hashed to prevent duplicate entries and data leakage between training and testing sets.
- **Cross-Dataset Deduplication**: The system automatically scans for overlapping code fragments across registered datasets.
- **Reproducibility Reports**: Generates a cryptographically signed report (`src/evaluation/reproducibility.py`) for every experiment, capturing system state, dataset versions, and result hashes.

---

## 6. Target Performance & Validation

IntegrityDesk targets a publication-grade performance profile:
- **Precision**: >0.98
- **Recall**: >0.99
- **F1-Score**: >0.92
- **FPR**: <0.01

All metrics are validated using **McNemar’s Test** and **Paired Bootstrap Tests** as defined in our [Evaluation Specification](../CONTRIBUTING_EVALUATION.md).

---
**IntegrityDesk R&D Unit**
*Engineering the Future of Academic Integrity.*
