# Certification Module - Production-Grade Statistical Analysis

This module provides publication-level statistical analysis and certification reports for code similarity detection systems.

## Overview

The certification system answers the critical questions:

1. **Is your system better?** - Statistical significance tests
2. **By how much?** - Effect sizes and confidence intervals
3. **Under what conditions?** - Stratified analysis
4. **Is the difference statistically significant?** - McNemar, Wilcoxon tests
5. **Can the result be reproduced exactly?** - Reproducibility tracking

## Architecture

```
certification/
├── __init__.py              - Module exports
├── models.py                - Core data models (BenchmarkRecord, EngineMetrics)
├── statistical_tests.py     - McNemar, Wilcoxon, paired bootstrap tests
├── confidence_intervals.py  - Bootstrap, Wilson, Clopper-Pearson CIs
├── effect_size.py           - Cohen's d, Cliff's Delta
├── stratified.py            - Stratified analysis across dimensions
├── tables.py                - Publication-grade table generation
├── plots.py                 - Visualization data structures
├── reproducibility.py       - Reproducibility tracking
└── report_builder.py        - Main report orchestration
```

## Core Data Model

### BenchmarkRecord

The fundamental unit of evaluation data:

```python
@dataclass(frozen=True)
class BenchmarkRecord:
    pair_id: str          # Unique identifier for code pair
    label: int            # Ground truth (1=clone, 0=non-clone)
    engine: str           # Engine name
    score: float          # Similarity score [0.0, 1.0]
    decision: bool        # Binary classification decision
    clone_type: int       # Clone type (0-4)
    difficulty: str       # EASY, HARD, EXPERT
    language: str         # Programming language
    metadata: Dict        # Additional metadata
```

## Statistical Tests

### McNemar's Test

Tests whether two classifiers have significantly different error rates on the same test set.

```python
from benchmark.certification import mcnemar_test

result = mcnemar_test(y_true, decisions_a, decisions_b)
print(f"p-value: {result.p_value:.6f}")
print(f"Significant: {result.significant}")
```

### Wilcoxon Signed-Rank Test

Tests whether score distributions are significantly different.

```python
from benchmark.certification import wilcoxon_signed_rank_test

result = wilcoxon_signed_rank_test(scores_a, scores_b)
print(f"p-value: {result.p_value:.6f}")
```

### Paired Bootstrap Test

Computes confidence intervals for metric differences.

```python
from benchmark.certification import paired_statistical_tests

results = paired_statistical_tests(
    y_true, scores_a, scores_b,
    decisions_a, decisions_b,
    metric_fn=f1_score
)
```

## Effect Sizes

### Cohen's d

Standardized mean difference (parametric):

```python
from benchmark.certification import cohens_d

result = cohens_d(scores_a, scores_b)
print(f"Cohen's d: {result.value:.4f} ({result.magnitude})")
```

Interpretation:
- |d| < 0.2: Negligible
- 0.2 ≤ |d| < 0.5: Small
- 0.5 ≤ |d| < 0.8: Medium
- |d| ≥ 0.8: Large

### Cliff's Delta

Non-parametric effect size (robust to outliers):

```python
from benchmark.certification import cliffs_delta

result = cliffs_delta(scores_a, scores_b)
print(f"Cliff's δ: {result.value:.4f} ({result.magnitude})")
```

Interpretation:
- |δ| < 0.147: Negligible
- 0.147 ≤ |δ| < 0.33: Small
- 0.33 ≤ |δ| < 0.474: Medium
- |δ| ≥ 0.474: Large

## Confidence Intervals

### Bootstrap CI

Gold standard for uncertainty estimation:

```python
from benchmark.certification import bootstrap_ci

result = bootstrap_ci(y_true, y_pred, f1_score, n_bootstrap=2000)
print(f"95% CI: [{result.ci_lower:.4f}, {result.ci_upper:.4f}]")
```

### Wilson Score Interval

Recommended for binomial proportions:

```python
from benchmark.certification import wilson_score_interval

ci = wilson_score_interval(successes, trials, confidence_level=0.95)
print(f"Accuracy: {ci.point_estimate:.4f} [{ci.ci_lower:.4f}, {ci.ci_upper:.4f}]")
```

## Stratified Analysis

Break down results by:

### Clone Type (I-IV)

Shows robustness to different clone types:

```python
from benchmark.certification import StratifiedAnalyzer

analyzer = StratifiedAnalyzer(n_bootstrap=1000)
results = analyzer.analyze(records, engine_name="my_engine")

for clone_type, metrics in results.by_clone_type.items():
    print(f"Type {clone_type}: F1={metrics.f1:.4f}")
```

### Difficulty Level

Shows resistance to obfuscation:

```python
for difficulty, metrics in results.by_difficulty.items():
    print(f"{difficulty}: F1={metrics.f1:.4f}")
```

### Programming Language

Shows generalization across languages:

```python
for language, metrics in results.by_language.items():
    print(f"{language}: F1={metrics.f1:.4f}")
```

## Report Generation

### Building a Report

```python
from benchmark.certification import CertificationReportBuilder, BenchmarkRecord

# Create records
records = [
    BenchmarkRecord(
        pair_id="pair_001",
        label=1,
        engine="my_engine",
        score=0.85,
        decision=True,
        clone_type=1,
        difficulty="EASY",
        language="python",
    ),
    # ... more records
]

# Build report
builder = CertificationReportBuilder(
    baseline_engine="baseline",
    n_bootstrap=2000,
    confidence_level=0.95,
    alpha=0.05,
    seed=42,
)

report = builder.build(records, dataset_name="my_dataset")

# Save outputs
report.save_json("reports/certification/report.json")
report.save_html("reports/certification/report.html")

# Print summary
print(report.summary())
```

### Report Contents

1. **Executive Summary**
   - Number of engines evaluated
   - Best performing engine
   - Significant differences found

2. **Main Results Table**
   - Precision, Recall, F1, Accuracy
   - 95% Confidence intervals

3. **Statistical Significance**
   - McNemar's test p-values
   - Wilcoxon test p-values
   - Effect sizes

4. **Stratified Results**
   - Performance by clone type
   - Performance by difficulty
   - Performance by language

5. **Reproducibility Statement**
   - Dataset hash
   - Code commit
   - Configuration hash
   - Random seed

## CLI Usage

### Run Certification

```bash
system certify run \
  --dataset my_dataset \
  --engines engine1,engine2,engine3 \
  --baseline engine1 \
  --output reports/certification \
  --format all
```

### Compare Two Engines

```bash
system certify compare \
  --records-a engine1_results.json \
  --records-b engine2_results.json \
  --name-a "Engine 1" \
  --name-b "Engine 2" \
  --output reports/certification
```

## Output Formats

### JSON

Machine-readable format for CI integration:

```json
{
  "report_id": "cert_my_dataset_20260402_203000",
  "timestamp": "2026-04-02T20:30:00",
  "engines": ["engine1", "engine2"],
  "n_samples": 1000,
  "main_results": {...},
  "significance_tests": {...},
  "stratified_results": {...},
  "reproducibility": {...}
}
```

### HTML

Interactive report with:
- Styled tables
- Color-coded significance
- Executive summary
- Reproducibility statement

## Reproducibility

Every report includes:

```python
{
  "dataset_hash": "a1b2c3d4e5f6",
  "code_commit": "48b7f958433e88c1efdde723993b09534687293b",
  "config_hash": "e3b0c44298fc1c149afbf4c8996fb924",
  "random_seed": 42,
  "python_version": "3.11.5",
  "numpy_version": "1.24.3",
  "scipy_version": "1.11.4",
  "platform": "Linux 6.8.0"
}
```

This ensures results can be exactly reproduced.

## Best Practices

1. **Always use paired tests** when comparing on the same dataset
2. **Report confidence intervals** for all metrics
3. **Include effect sizes** - statistical significance alone is not enough
4. **Use stratified analysis** to identify weaknesses
5. **Include reproducibility information** for auditability
6. **Apply multiple comparison correction** when comparing multiple engines

## References

- McNemar, Q. (1947). Note on the sampling error of the difference between correlated proportions.
- Wilcoxon, F. (1945). Individual comparisons by ranking methods.
- Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences.
- Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions.
- Efron, B., & Tibshirani, R. J. (1993). An introduction to the bootstrap.
- Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms.