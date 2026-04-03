# Dataset Governance & Reproducibility Standards

> **A Protocol for Defensive Scientific Benchmarking in Code Similarity**

IntegrityDesk was built on the principle that academic results must be reproducible and verifiable. This document defines the mandatory governance standards for data and experimentation.

---

## 1. Dataset Registration & Integrity

All datasets used in experiments must be registered with the **Dataset Governance Layer** (`src/evaluation/dataset/governance.py`).

1.  **Unique Fingerprinting**: Every file in a dataset is hashed using SHA-256. This ensures its identity is immutable and globally verifiable.
2.  **Metadata Capture**: The system records the dataset version, origin, and description to ensure total transparency.
3.  **Integrity Checks**: Any modification to a registered dataset (adding or removing files) will trigger an "Integrity Fail" flag, preventing its use in benchmark runs until re-validated.

---

## 2. Preventing Contamination (Risk 3)

Data leakage is a primary risk in code similarity research. IntegrityDesk implements **Cross-Dataset Deduplication**:

- **Automatic Overlap Scans**: Before a benchmark run, the system scans for identical file hashes across all registered datasets.
- **Leakage Prevention**: If the same code exists in both a "training/fine-tuning" set and a "test" set, the overlap is automatically flagged.
- **Deduplication Reports**: A report is generated detailing any identical code fragments and their locations.

---

## 3. Automated Reproducibility Reports

To achieve publication-grade credibility, every experiment must be documented with a **Reproducibility Report** (`src/evaluation/reproducibility.py`):

- **System Context**: Records the OS, hardware (CPU/RAM), and Python version used for the run.
- **Configuration Snapshots**: Captures every hyper-parameter, engine weight, and threshold used in the experiment.
- **Dataset Versioning**: Includes the content hashes for every dataset used.
- **Result Hashes**: The final scores (F1, Precision, Recall) are cryptographically signed to prevent manual "score grooming."

---

## 4. Evaluation Specifications

Every evaluation must adhere to the [Formal Evaluation Specification](../CONTRIBUTING_EVALUATION.md), which mandates:

- **95% Confidence Intervals**: No metric can be reported as a single point.
- **Significance Testing**: Mandatory use of **McNemar’s Test** or **Paired Bootstrap Tests** for system comparisons.
- **Standardized Benchmarking**: Results must be compared against established baselines (MOSS, JPlag, Dolos) under identical conditions.

---

## 5. Scope Freeze & CI Gates

To maintain rigor, IntegrityDesk enforces a **Scope Freeze** on certain components:

1.  **Detection Engines**: The core 6 engines are the primary forensic indicators. New engines require a peer-reviewed "Impact Assessment" before integration.
2.  **CI Gates**: Our continuous integration pipeline includes a "Publication Gate" that fails builds if:
    - **F1-score regresses** more than 1% from the established baseline.
    - **Dataset hashes** do not match the registered versions.
    - **Unit test coverage** falls below 90% for core forensic modules.

---
**IntegrityDesk Governance Committee**
*Upholding the Gold Standard of Scientific Integrity.*
