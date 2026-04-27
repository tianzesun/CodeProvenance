# IntegrityDesk Scoring System - Technical Documentation

## Overview
IntegrityDesk uses a calibrated multi-engine fusion pipeline to combine structural, lexical, semantic, behavioral, and source-based evidence into a single explainable risk score.

## Pipeline Architecture

### 1. Feature Extraction
Each submission pair is analyzed by 10+ specialized engines:
- **AST**: Abstract Syntax Tree isomorphism (structural similarity)
- **Token/Fingerprint**: Lexical token analysis (exact matches)
- **Winnowing**: Robust fingerprinting algorithm (clone detection)
- **GST**: Greedy String Tiling (sequence matching)
- **Semantic**: Deep logic analysis via transformers
- **Execution CFG**: Runtime behavior modeling
- **Tree Kernel**: Advanced structural comparison
- **CFG**: Control flow graph analysis
- **Embedding**: Neural similarity representations
- **Ngram**: Statistical pattern analysis
- **Web**: Online source attribution
- **AI Detection**: AI-generated content analysis

### 2. Baseline Correction
Each engine score is normalized to remove language-level background similarity:

```
corrected_e = max(0, (raw_e - baseline_e)) / (1 - baseline_e)
```

Baselines are engine-specific, language-specific, and assignment-family-specific to account for natural overlap patterns.

### 3. Assignment Mode Calibration
Engine weights are adjusted based on assignment context:
- **Foundations Code**: AST 24%, Token 18%, Tree Kernel 14%
- **Algorithmic Code**: AST 20%, Semantic 16%, Execution CFG 14%
- **Systems & Projects**: AST 18%, CFG 14%, Execution CFG 14%
- **SQL & Data Logic**: Semantic 20%, Embedding 16%, Token 15%
- **Notebook & AI**: Semantic 16%, Embedding 14%, AST 14%
- **Reports & Proofs**: Web 22%, Semantic 18%, Embedding 16%

### 4. Precision-Weighted Fusion
Final score combines calibrated engine scores using reliability-based weights:

```
FusedScore = Σ(weight_e × CorrectedScore_e)
where Σ weight_e = 1
```

Weights reflect engine reliability for the selected assignment mode.

### 5. Consensus Guards & Quality Assurance

#### Multi-Engine Requirements:
- **High Risk** (65-85%): Requires ≥2 primary engines above threshold
- **Critical Risk** (85%+): Requires ≥2 primary + ≥1 supporting engines, OR high agreement index
- **AI Detection**: Cannot alone trigger High or Critical risk (advisory only)

#### Evidence Validation:
- Penalizes isolated score spikes from single engines
- Requires cross-validation across complementary detection methods
- Blocks high-severity outcomes without multi-signal consensus

### 6. Risk Level Classification

0-35%: **Low review priority** (minimal concern)
35-65%: **Moderate review priority** (investigate if resources allow)
65-85%: **High review priority** (requires review)
85%+: **Critical review priority** (requires immediate review with corroborating evidence)

## Quality Assurance Features

### Statistical Robustness:
- **Agreement Index**: Measures engine consensus (1.0 = perfect agreement)
- **Uncertainty Quantification**: Confidence intervals for score reliability
- **Cross-Validation**: Prevents overfitting to specific datasets

### Explainability:
- **Per-Engine Contributions**: Breakdown of which engines flagged the pair
- **Evidence Surfaces**: Side-by-side diffs, similarity heatmaps, source attribution
- **Assignment-Specific Views**: Context-aware result presentation

### Performance Optimization:
- **Parallel Processing**: 4 engines run simultaneously
- **Result Caching**: Avoids redundant computations
- **Hot Reloading**: Real-time weight adjustments without restart

## AI Detection Policy

AI-origin signals may elevate review priority but **cannot alone establish misconduct**. This advisory-only approach addresses:
- False positive risks in AI detection technology
- Academic due process requirements
- Ethical considerations for automated decision-making

## Mathematical Foundation

The system uses **precision-weighted ensemble fusion** rather than simple averaging, ensuring that more reliable engines have proportionally greater influence on the final score. This approach provides statistical rigor while maintaining interpretability for academic review workflows.