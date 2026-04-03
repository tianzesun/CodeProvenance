# User Guide: Navigating IntegrityDesk

> **A Step-by-Step Manual for Educators, Students, and Review Committees**

IntegrityDesk is designed to be powerful yet intuitive. This guide walks you through the core workflow—from submission to evidence-based review.

---

## 1. Submission Workflow

IntegrityDesk supports batch processing of hundreds of submissions at once.

1.  **Dashboard**: Navigate to the main dashboard.
2.  **Upload Submissions**: Drag and drop a folder or upload a ZIP file containing student work.
3.  **Language Detection**: The system automatically identifies the programming language (Python, C++, Java, etc.).
4.  **Instant Scan**: For batches <100 files, initial results are available in under 10 seconds.

---

## 2. Interpreting the Dashboard (Risk 4)

We replace "smart interpretations" with raw forensic evidence to ensure your decision is objective.

- **Similarity Index (0-1.0)**: The primary composite score. A score of 0.85 indicates critical overlap.
- **Agreement Index**: How much the independent engines (AST, Embedding, etc.) align. High consensus increases the defensibility of the match.
- **Uncertainty Margin**: The statistical error range. A margin of ±0.03 is common for high-confidence matches.
- **Engine Contribution**: See which forensic indicator (structural, lexical, or semantic) provided the strongest evidence.

---

## 3. Side-by-Side Evidence Review

Clicking on any suspicious pair opens the **Evidence Review** interface.

- **Synchronized Scrolling**: Scroll through both files simultaneously.
- **Evidence Blocks**: Highlighted regions where similarity was detected.
- **Transformation Notes**: Explanatory notes like "variable renaming detected" or "structural alignment match."
- **Code Snippets**: View the exact code from both submissions side-by-side.

---

## 4. Professional Reporting (Publication-Style)

For disciplinary cases, you can generate a **Forensic Evidence Report**.

1.  **Export Report**: Click "Export PDF" or "View HTML Report."
2.  **Professional Aesthetic**: The report is styled for academic committees (ACM/IEEE style).
3.  **Executive Summary**: A high-level view for the committee, followed by technical details for the student's defense.
4.  **Cryptographic Signature**: Each report has a unique hash at the bottom to ensure its integrity and prevent tampering.

---

## 5. Frequently Asked Questions (FAQ)

### Is it MOSS-compatible?
Yes. IntegrityDesk includes a Winnowing engine that uses the same core algorithm as MOSS but adds 5 additional layers of forensic analysis for greater accuracy.

### Can it detect AI-generated code?
Yes. Our semantic embedding and stylometry engines are designed to identify the patterns common in LLM-generated code (GPT-4, Claude, etc.).

### What about false positives (FP)?
Our **Bayesian Arbitration Layer** is specifically designed to reduce FPs. If only one engine (e.g., Token) shows a high score while the others (e.g., AST, Stylometry) do not, the overall score is automatically penalized and flagged for review.

---

## 6. Support & Resources

- **Community**: Join our community forum for tips on academic integrity.
- **Documentation**: Access the [Scientific White Paper](SCIENTIFIC_WHITE_PAPER.md) for a deep dive into our methodology.
- **Support**: Contact your institutional IT department or reach out to us at `support@codeprovenance.io`.

---
**IntegrityDesk Academic Support Team**
*Clear Evidence. Fair Decisions.*
