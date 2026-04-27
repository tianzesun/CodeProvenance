# IntegrityDesk Scoring System - Professional Documentation

## Executive Summary

IntegrityDesk uses a **calibrated multi-engine fusion pipeline** to combine structural, lexical, semantic, behavioral, and source-based evidence into a single explainable risk score. Assignment-specific modes rebalance engine importance, while consensus guards and uncertainty checks reduce false positives and prevent any one weak signal from dominating outcomes.

## Technical Architecture

### Multi-Engine Fusion Pipeline

1. **Feature Extraction**: 10+ specialized engines analyze each submission pair
2. **Baseline Correction**: Engine-specific, language-specific normalization
3. **Assignment Calibration**: Mode-specific weight adjustments
4. **Precision-Weighted Fusion**: Reliability-based score combination
5. **Consensus Guards**: Multi-engine agreement requirements
6. **Quality Assurance**: Statistical validation and uncertainty quantification

### Engine Suite

#### Core Structural Engines
- **AST**: Abstract Syntax Tree isomorphism (structural similarity)
- **Tree Kernel**: Advanced convolution-based structural comparison
- **CFG**: Control flow graph analysis
- **Execution CFG**: Runtime behavior modeling

#### Lexical & Pattern Engines
- **Token/Fingerprint**: Exact match and token pattern detection
- **Winnowing**: Robust fingerprinting for code clones
- **GST**: Greedy String Tiling for sequence matching
- **Ngram**: Statistical code sequence analysis

#### Semantic & AI Engines
- **Semantic**: Transformer-based logic understanding
- **Embedding**: Neural similarity representations
- **AI Detection**: AI-generated content analysis (advisory only)

#### Attribution Engines
- **Web**: Online source and tutorial detection

## Scoring Mathematics

### Baseline Correction Formula
```
corrected_e = max(0, (raw_e - baseline_e)) / (1 - baseline_e)
```

Where `baseline_e` represents expected same-language background similarity for engine `e`.

### Precision-Weighted Fusion
```
FusedScore = Σ(weight_e × CorrectedScore_e)
where Σ weight_e = 1
```

Weights reflect engine reliability for the selected assignment mode and are normalized to ensure proper probability distribution.

### Quality Assurance

#### Multi-Engine Consensus Requirements
- **High Review Priority** (65-85%): Requires ≥2 primary engines above threshold
- **Critical Review Priority** (85%+): Requires ≥2 primary + ≥1 supporting engines, OR high agreement index
- **AI Detection Alone**: Cannot trigger High or Critical priority (advisory only)

#### Statistical Validation
- **Agreement Index**: Measures engine consensus (1.0 = perfect agreement)
- **Uncertainty Quantification**: Confidence intervals for score reliability
- **False Positive Prevention**: Cross-validation and consensus guards

## Assignment Mode Optimization

### Foundations Code
**Context**: CS1/CS2 assignments with high legitimate convergence risk
**Emphasis**: AST (24%), Token (18%), Tree Kernel (14%)
**Rationale**: Beginner cheating often preserves surface structure

### Algorithmic Code
**Context**: Data structures & algorithms with logic preservation
**Emphasis**: AST (20%), Semantic (16%), Execution CFG (14%)
**Rationale**: Logic-preserving plagiarism survives variable renaming

### Systems & Projects
**Context**: Large software engineering projects
**Emphasis**: AST (18%), CFG (14%), Execution CFG (14%)
**Rationale**: Architecture and design similarity matters most

### SQL & Data Logic
**Context**: Database assignments with semantic equivalence
**Emphasis**: Semantic (20%), Embedding (16%), Token (15%)
**Rationale**: Query logic equivalence over syntactic differences

### Notebook & Applied AI
**Context**: Jupyter notebooks with mixed content types
**Emphasis**: Semantic (16%), Embedding (14%), AST (14%)
**Rationale**: Balances code, text, and AI-generated content analysis

### Reports & Proofs
**Context**: Text-based academic writing assignments
**Emphasis**: Web (22%), Semantic (18%), Embedding (16%)
**Rationale**: Focus on source attribution and semantic similarity

## Review Priority Classification

| Score Range | Priority Level | Action Required |
|-------------|----------------|-----------------|
| 0-35% | Low review priority | Minimal concern |
| 35-65% | Moderate review priority | Investigate if resources allow |
| 65-85% | High review priority | Requires review |
| 85%+ | Critical review priority | Requires immediate review with corroborating evidence |

## AI Detection Policy

AI-origin signals may **elevate review priority** but **cannot alone establish misconduct**. This advisory-only approach addresses:

- **False positive risks** in current AI detection technology
- **Academic due process** requirements for automated decisions
- **Ethical considerations** for student assessment

AI detection serves as an **investigation trigger**, not a dispositive determination of academic misconduct.

## Performance & Scalability

- **Parallel Processing**: 4 engines execute simultaneously
- **Result Caching**: Prevents redundant computations
- **Hot Reloading**: Real-time weight adjustments
- **Batch Processing**: Handles large submission sets efficiently

## Explainability Features

### Per-Comparison Analysis
- Engine contribution breakdown
- Confidence scores and uncertainty measures
- Side-by-side diff visualizations
- Similarity heatmaps and pattern analysis

### Assignment-Specific Views
- Context-aware result presentation
- Mode-appropriate evidence surfaces
- Tailored explanations for different assignment types

## Quality Assurance Framework

### Statistical Robustness
- Cross-validation prevents overfitting
- Agreement analysis ensures consensus
- Uncertainty bounds provide confidence intervals

### Academic Integrity Safeguards
- Multi-signal requirements prevent single-engine bias
- AI detection restrictions maintain human oversight
- Transparent scoring enables instructor review

---

**IntegrityDesk provides statistically rigorous, explainable plagiarism detection optimized for academic assessment workflows.**