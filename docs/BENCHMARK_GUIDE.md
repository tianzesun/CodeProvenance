# CodeProvenance Benchmark System - Comprehensive Guide

## Authoritative Benchmark Suite (2026 Standard)

This is the official publication-grade benchmark suite. All evaluations must use this comparator set.

| Tier | Category | Systems |
|------|----------|---------|
| **1** | Canonical Baselines | MOSS, JPlag, NiCad |
| **2** | Practical / Scalable | Dolos, PMD CPD, SourcererCC |
| **3** | Advanced / Research | STRANGE, Deckard |
| **4** | Industry Reality Check | Turnitin, Codequiry |
| **5** | Modern LLM Baseline | Transformer Semantic, LLM Similarity |
| **6** | Specialized | Vendetect |

### Evaluation Scenarios

All systems are evaluated across three critical scenarios:

1.  **Classic Plagiarism** (Copy + rename)
    - Must beat MOSS/JPlag
2.  **Near-miss / Obfuscation** (Reordering, refactoring)
    - Must beat NiCad / Deckard
3.  **AI-assisted Rewriting** (Same logic, different code)
    - Must beat embedding/LLM baseline

---

## Executive Summary

The CodeProvenance Benchmark System is a **self-improving, evaluation-driven engineering loop** for code similarity detection algorithms. It provides a rigorous, reproducible framework for measuring detector capabilities across multiple dimensions.

### Key Features

- ✅ **Three-Layer Evaluation Design** - Sensitivity, Precision, and Generalization
- ✅ **12 Datasets** - From synthetic to real-world student code
- ✅ **10 Dataset Loaders** - Standardized data access
- ✅ **Multiple Engines** - Token, AST, and Hybrid similarity detection
- ✅ **Statistical Rigor** - Confidence intervals, significance testing
- ✅ **Reproducible** - Version-pinned datasets, deterministic execution

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    BENCHMARK SYSTEM                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Layer 1    │    │   Layer 2    │    │   Layer 3    │      │
│  │ Sensitivity  │ →  │  Precision   │ →  │Generalization│      │
│  │  (17+ tech)  │    │  (Real code) │    │(Cross-lang)  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         ↓                   ↓                   ↓               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              UNIFIED SCORING ENGINE                       │  │
│  │  Weighted combination: 40% + 30% + 30% = Overall Score   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Three-Layer Evaluation Design

### Layer 1: Sensitivity Analysis

**Purpose:** Measure detector's ability to catch **17+ plagiarism techniques**

**What it tests:**
- Can the detector catch simple variable renaming?
- Can it detect structural changes (loop transformations)?
- Can it identify semantic clones (same logic, different code)?

**Techniques Tested (17+):**

| # | Technique | Description | Challenge Level |
|---|-----------|-------------|-----------------|
| 1 | Rename Variables | Change variable/function names | Easy |
| 2 | Restructure Statements | Reorder independent statements | Easy |
| 3 | Change Loop Type | Convert for↔while loops | Medium |
| 4 | Inline Function | Replace function call with body | Medium |
| 5 | Extract Function | Move code to new function | Medium |
| 6 | Add Dead Code | Insert unreachable code | Easy |
| 7 | Change Data Structures | Replace list↔dict↔set | Medium |
| 8 | Change Control Flow | Convert if-elif to nested if | Medium |
| 9 | Add Comments | Insert excessive comments | Easy |
| 10 | Change Whitespace | Modify indentation/spacing | Easy |
| 11 | Modify String Literals | Change string values | Easy |
| 12 | Change Variable Order | Swap assignment order | Medium |
| 13 | Negate Condition | Flip if↔if not | Medium |
| 14 | Combine Loops | Merge multiple loops | Hard |
| 15 | Split Loops | Divide single loop into multiple | Hard |
| 16 | Change Function Signature | Reorder parameters | Medium |
| 17 | Replace with Equivalent | Use alternative syntax | Medium |
| 18 | Semantic Clone | Complete rewrite, same logic | Hard |
| 19 | Chain Transformation | Apply 3+ techniques | Very Hard |

**Metrics Reported:**
- **Per-technique recall** - Did we catch each technique?
- **Overall F1** - Balance of precision and recall
- **Confusion matrix** - TP/FP/TN/FN per technique

**Example Output:**
```
CLONE-TYPE RECALL MATRIX
Engine          | T1    | T2    | T3    | T4    | Overall
----------------|-------|-------|-------|-------|--------
token           | 1.00  | 0.60  | 0.80  | 0.40  | 0.70
ast             | 1.00  | 0.90  | 0.85  | 0.70  | 0.86
hybrid          | 1.00  | 0.95  | 0.90  | 0.80  | 0.91
hybrid_canon    | 1.00  | 0.98  | 0.92  | 0.85  | 0.94  ← Best
```

---

### Layer 2: Precision Analysis

**Purpose:** Measure **false positive rate** on real student code

**What it tests:**
- Does the detector flag legitimate code as plagiarized?
- What's the precision when comparing real submissions?
- How many innocent students get flagged?

**Dataset:** Real student assignments (or synthetic approximations)

**Metrics Reported:**
- **Precision** - Of flagged pairs, how many are actually clones?
- **Recall** - Of actual clones, how many did we catch?
- **F1 Score** - Harmonic mean of precision and recall
- **False Positive Rate** - Percentage of innocent students flagged
- **Score Distribution** - Histogram of similarity scores

**Example Output:**
```
PRECISION ANALYSIS
Metric                  | Value
------------------------|-------
Precision               | 0.9231
Recall                  | 0.7250
F1 Score                | 0.8169
False Positive Rate     | 0.0312
True Positives          | 29
False Positives         | 2
True Negatives          | 97
False Negatives         | 10
```

**Interpretation:**
- **High precision (0.92)** - When we flag something, we're usually right
- **Moderate recall (0.73)** - We miss some clones (acceptable trade-off)
- **Low FPR (0.03)** - Only 3% of innocent students flagged

---

### Layer 3: Generalization Analysis

**Purpose:** Test **cross-language and cross-project** detection

**What it tests:**
- Does the detector work across programming languages?
- Does it generalize to unseen code styles?
- Is it overfitting to specific patterns?

**Datasets Used:**
- **Multi-language benchmarks** - Same algorithm in Python, Java, JavaScript
- **Cross-project code** - Different coding styles and conventions

**Metrics Reported:**
- **Per-language performance** - How well does it work in each language?
- **Cross-language variance** - Is performance consistent across languages?
- **Generalization score** - Overall ability to generalize

**Example Output:**
```
GENERALIZATION ANALYSIS
Language      | Pairs | Mean Score | Max Score | Min Score
--------------|-------|------------|-----------|----------
python        | 45    | 0.7823     | 0.9845    | 0.1234
java          | 45    | 0.7654     | 0.9756    | 0.1567
javascript    | 45    | 0.7589     | 0.9678    | 0.1890
--------------|-------|------------|-----------|----------
Cross-lang    | 135   | 0.7689     | 0.9845    | 0.1234
Variance      |       | 0.00098    |           |
Gen. Score    |       | 0.9510     |           |
```

**Interpretation:**
- **Low variance (0.001)** - Performance is consistent across languages
- **High generalization (0.95)** - Detector works well on unseen code

---

## Unified Scoring Formula

The **overall benchmark score** combines all three layers:

```python
Overall Score = (Layer1 × 0.40) + (Layer2 × 0.30) + (Layer3 × 0.30)
```

| Layer | Weight | Rationale |
|-------|--------|-----------|
| **Sensitivity** | 40% | Most important - can we catch clones? |
| **Precision** | 30% | Critical for production - avoid false accusations |
| **Generalization** | 30% | Essential for real-world use |

**Example Calculation:**
```
Layer 1 (Sensitivity): 0.94 F1 × 0.40 = 0.376
Layer 2 (Precision):   0.82 F1 × 0.30 = 0.246
Layer 3 (Generalization): 0.95 Score × 0.30 = 0.285
─────────────────────────────────────────────────
Overall Score:         0.376 + 0.246 + 0.285 = 0.907 (90.7%)
```

---

## Dataset Registry

### Layer 1: Public Reproducibility (In Git)

| Dataset | Pairs | Language | Purpose |
|---------|-------|----------|---------|
| `synthetic` | 400 | Python | Controlled ground truth |
| `xiangtan` | 75 | Java | Java clone detection |
| `google_codejam` | 9 | Python | Algorithmic solutions |
| `kaggle_student_code` | 292 | Python | Student plagiarism |

**Total:** 776 pairs

### Layer 2: External Benchmarks (Downloaded)

| Dataset | Size | Language | Purpose |
|---------|------|----------|---------|
| `bigclonebench` | 55K files | Java | Industry-standard benchmark |
| `codexglue_clone` | 1.7M pairs | Java | Microsoft clone detection |
| `codesearchnet` | 457K functions | Python | Semantic similarity |
| `codesearchnet_java` | 497K functions | Java | Java semantic similarity |
| `codesearchnet_misc` | 1M functions | Multi | JS/Go/PHP/Ruby |
| `codexglue_defect` | 27K programs | C | Defect detection |
| `poj104` | 53K programs | C | C code plagiarism |
| `codesimilaritydataset` | 100 snippets | Python | Python similarity |

**Total:** ~3.7M code samples

### Layer 3: Evaluation Only (H2 Databases)

| Dataset | Size | Purpose |
|---------|------|---------|
| `bigclonebench_h2_db` | 5.5GB | Controlled evaluation |

---

## Directory Structure

```
benchmark/
├── __init__.py              # Module exports
├── __main__.py              # CLI entry point
├── registry.py              # Engine registration
│
├── similarity/              # Core detection engines
│   ├── base_engine.py       # Abstract interface
│   ├── engines.py           # Token, AST, Hybrid
│   ├── token_winnowing.py   # Token-based detection
│   ├── ast_subtree.py       # AST structural analysis
│   └── hybrid.py            # Combined approach
│
├── datasets/                # Dataset loaders (10 total)
│   ├── bigclonebench.py     # BigCloneBench loader
│   ├── codesearchnet.py     # CodeSearchNet Python
│   ├── codesearchnet_java.py # CodeSearchNet Java
│   ├── codesearchnet_misc.py # Multi-language
│   ├── code_similarity_dataset.py # Similarity pairs
│   ├── codexglue_clone.py   # CodeXGLUE clone
│   ├── codexglue_defect.py  # CodeXGLUE defect
│   ├── google_codejam.py    # Google Code Jam
│   ├── kaggle_student_code.py # Kaggle student code
│   ├── poj104.py            # POJ-104 C code
│   ├── synthetic_generator.py # Synthetic data
│   └── xiangtan.py          # Xiangtan dataset
│
├── pipeline/                # Orchestration
│   ├── config.py            # Benchmark configuration
│   ├── loader.py            # Dataset loading
│   ├── stages.py            # Pipeline stages
│   ├── runner.py            # Execution engine
│   └── evaluation_framework.py # Three-layer framework
│
├── analysis/                # Result analysis
│   ├── failure_analysis.py  # Error categorization
│   ├── error_attribution.py # Root cause analysis
│   ├── causal_ranking.py    # Improvement prioritization
│   ├── speed_benchmark.py   # Performance testing
│   └── stability_analysis.py # Consistency checks
│
├── metrics/                 # Evaluation metrics
│   ├── __init__.py          # precision, recall, f1, map, mrr
│   └── significance.py      # Statistical testing
│
├── reporting/               # Output generation
│   ├── json_writer.py       # JSON reports
│   ├── html_report.py       # HTML reports
│   ├── leaderboard.py       # Rankings
│   └── reproducibility.py   # Verification
│
├── normalizer/              # Code normalization
│   ├── base_normalizer.py   # Base class
│   ├── canonicalizer.py     # Identifier/literal normalization
│   ├── identifier_normalizer.py # Variable renaming
│   ├── jplag_normalizer.py  # JPlag-specific
│   └── moss_normalizer.py   # MOSS-specific
│
├── parsers/                 # Code parsing
│   ├── ast_parser.py        # AST extraction
│   ├── base_parser.py       # Base parser
│   ├── jplag_parser.py      # JPlag format
│   ├── moss_parser.py       # MOSS format
│   └── nicad_parser.py      # NiCad format
│
├── runners/                 # Execution runners
│   ├── base_runner.py       # Base class
│   └── __init__.py
│
├── adapters/                # External tool integration
│   ├── codeprovenance_engine.py # Our engine (v1)
│   ├── codeprovenance_engine_v2.py # v2
│   ├── codeprovenance_engine_v3.py # v3
│   ├── codeprovenance_engine_v4.py # v4
│   ├── codeprovenance_engine_v5.py # v5 (latest)
│   ├── jplag_engine.py      # JPlag adapter
│   ├── jplag_runner.py      # JPlag executor
│   ├── moss_runner.py       # MOSS executor
│   ├── nicad_runner.py      # NiCad executor
│   ├── pmd_runner.py        # PMD executor
│   ├── dolos_runner.py      # Dolos executor
│   └── python_graph_builder.py # Graph construction
│
├── evaluation/              # Comparative evaluation
│   ├── comparative.py       # Before/after comparison
│   ├── pairwise.py          # Pairwise evaluation
│   ├── ranking.py           # MAP, MRR calculation
│   └── threshold/           # Threshold analysis
│
├── abstraction/             # Advanced analysis
│   ├── algorithmic_equivalence.py # Logic equivalence
│   └── semantic_abstraction.py # Semantic analysis
│
├── schemas/                 # Data validation
│   └── result_schema.py     # Result structure
│
├── data/                    # Dataset files
│   ├── README.md            # Data documentation
│   ├── dataset_manifest.json # Dataset registry
│   ├── dataset_versions.lock # Version pinning
│   ├── download_external.sh # Download script
│   └── [12 dataset dirs]
│
└── web_dashboard/           # User interface
    └── [Dashboard files]
```

---

## Usage Guide

### Quick Start

```bash
# Run default benchmark
python -m benchmark run --config config/benchmark.yaml

# Run specific engine
python -m benchmark run --config config/benchmark.yaml --engine hybrid

# Generate synthetic dataset
python -m benchmark generate --output data/my_dataset.json

# Compare engines
python -m benchmark compare --config config/benchmark.yaml
```

### Configuration File

```yaml
# config/benchmark.yaml
dataset:
  name: synthetic
  version: v1
  splits:
    train: 0.7
    validation: 0.15
    test: 0.15

engines:
  - token_winnowing
  - ast_structural
  - hybrid

metrics:
  - precision
  - recall
  - f1
  - map
  - mrr

evaluation:
  layers:
    - sensitivity
    - precision
    - generalization
  weights:
    sensitivity: 0.4
    precision: 0.3
    generalization: 0.3

output:
  format: json
  path: reports/
  include_details: true
```

### Python API

```python
from benchmark.pipeline.evaluation_framework import ThreeLayerBenchmarkRunner
from benchmark.similarity.engines import HybridEngine

# Initialize
engine = HybridEngine()
runner = ThreeLayerBenchmarkRunner(engine)

# Run benchmark
result = runner.run(
    base_codes=my_code_samples,
    student_assignments=real_submissions,
    language_samples=cross_lang_data
)

# Access results
print(f"Overall Score: {result.overall_score:.2%}")
print(f"Layer 1 (Sensitivity): {result.layer1_sensitivity['overall_f1']:.2%}")
print(f"Layer 2 (Precision): {result.layer2_precision['f1']:.2%}")
print(f"Layer 3 (Generalization): {result.layer3_generalization['generalization_score']:.2%}")
```

---

## Interpreting Results

### Good Performance Indicators

| Metric | Good | Acceptable | Poor |
|--------|------|------------|------|
| **Overall F1** | > 0.85 | 0.70 - 0.85 | < 0.70 |
| **Precision** | > 0.90 | 0.80 - 0.90 | < 0.80 |
| **Recall** | > 0.80 | 0.60 - 0.80 | < 0.60 |
| **False Positive Rate** | < 0.05 | 0.05 - 0.10 | > 0.10 |
| **Generalization Score** | > 0.90 | 0.80 - 0.90 | < 0.80 |

### Example: Hybrid Engine v5

```
THREE-LAYER AUTHORITY BENCHMARK
═══════════════════════════════════════════════════════════════

Layer 1 (Sensitivity): 94.00% F1
  ✅ Type-1 (Identical):    100% recall
  ✅ Type-2 (Renamed):       98% recall
  ✅ Type-3 (Restructured):  92% recall
  ⚠️  Type-4 (Semantic):     85% recall

Layer 2 (Precision): 82.00% F1
  ✅ Precision:              92% (low false positives)
  ⚠️  Recall:                 73% (misses some clones)
  ✅ False Positive Rate:     3% (acceptable)

Layer 3 (Generalization): 95.00% Score
  ✅ Python:                 96% performance
  ✅ Java:                   94% performance
  ✅ JavaScript:             93% performance
  ✅ Cross-lang variance:    0.001 (very consistent)

───────────────────────────────────────────────────────────────
Overall Score: 90.70%
Rating: ⭐⭐⭐⭐⭐ EXCELLENT
```

### Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Low Type-2 recall** | Misses renamed variables | Add identifier normalization |
| **High false positives** | Innocent students flagged | Increase threshold |
| **Low generalization** | Works on Python, fails Java | Add multi-language training |
| **Slow performance** | Long execution time | Optimize token comparison |

---

## Iteration Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    IMPROVEMENT CYCLE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. RUN BASELINE                                            │
│     ↓                                                       │
│  2. ANALYZE FAILURES                                        │
│     ↓                                                       │
│  3. IDENTIFY ROOT CAUSE                                     │
│     ↓                                                       │
│  4. IMPLEMENT FIX                                           │
│     ↓                                                       │
│  5. RE-RUN BENCHMARK                                        │
│     ↓                                                       │
│  6. COMPARE RESULTS                                         │
│     ↓                                                       │
│  (repeat until target reached)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Step-by-Step Process

1. **Run baseline:**
   ```bash
   python -m benchmark run --config config/benchmark.yaml --output reports/run_001.json
   ```

2. **Analyze failures:**
   ```bash
   # Check improvement_targets in report JSON
   cat reports/run_001.json | jq '.improvement_targets'
   ```

3. **Implement fix:**
   - Modify `benchmark/similarity/` for algorithm improvements
   - Modify `benchmark/normalizer/` for normalization improvements
   - Modify `benchmark/pipeline/` for orchestration improvements

4. **Re-run benchmark:**
   ```bash
   python -m benchmark run --config config/benchmark.yaml --output reports/run_002.json
   ```

5. **Compare results:**
   ```bash
   # Compare run_001 vs run_002
   python -m benchmark compare --before reports/run_001.json --after reports/run_002.json
   ```

---

## Best Practices

### For Benchmark Users

1. **Always use version-pinned datasets** - Ensures reproducibility
2. **Run all three layers** - Don't optimize for just one metric
3. **Report confidence intervals** - Show statistical significance
4. **Document changes** - Track what improved (and what regressed)
5. **Test on held-out data** - Avoid overfitting to benchmark

### For Engine Developers

1. **Start with Layer 1** - Get sensitivity working first
2. **Add normalization early** - Identifier renaming is common
3. **Balance precision/recall** - Don't sacrifice one for the other
4. **Test cross-language** - Real-world code is multi-language
5. **Profile performance** - Speed matters for production use

### For Dataset Maintainers

1. **Never modify datasets** - Only detector changes
2. **Version everything** - Pin dataset versions
3. **Document sources** - Track where data came from
4. **Verify checksums** - Ensure data integrity
5. **Separate layers** - Keep public/external/evaluation distinct

---

## Statistical Significance

### Confidence Intervals

All metrics include **95% confidence intervals** calculated via bootstrap:

```python
from benchmark.metrics.significance import bootstrap_confidence_interval

# Calculate confidence interval
ci = bootstrap_confidence_interval(
    scores=all_scores,
    metric_fn=lambda x: sum(x) / len(x),  # mean
    n_bootstrap=1000,
    confidence=0.95
)

print(f"Mean: {ci['value']:.4f}")
print(f"95% CI: [{ci['lower']:.4f}, {ci['upper']:.4f}]")
print(f"p-value: {ci['p_value']:.4f}")
```

### Significance Testing

Use **McNemar's test** to compare two engines:

```python
from benchmark.metrics.significance import mcnemar_test

result = mcnemar_test(
    correct_a=engine_a_correct,  # Boolean array
    correct_b=engine_b_correct   # Boolean array
)

print(f"Statistic: {result['statistic']:.4f}")
print(f"p-value: {result['p_value']:.4f}")
print(f"Significant: {result['significant']}")
```

**Interpretation:**
- **p < 0.05** - Statistically significant difference
- **p ≥ 0.05** - No significant difference (could be noise)

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Missing dependency | `pip install datasets pyyaml` |
| `FileNotFoundError` | Dataset not downloaded | Run `download_external.sh` |
| `MemoryError` | Dataset too large | Use `max_samples` parameter |
| `TimeoutError` | Slow comparison | Optimize engine or reduce pairs |

### Getting Help

1. Check `benchmark/data/README.md` for dataset issues
2. Check `docs/ARCHITECTURE.md` for design questions
3. Review `benchmark/pipeline/evaluation_framework.py` for layer details
4. Examine `benchmark/similarity/engines.py` for engine implementation

---

## Conclusion

The CodeProvenance Benchmark System provides a **rigorous, reproducible framework** for evaluating code similarity detectors. The three-layer design ensures comprehensive evaluation:

- **Layer 1 (Sensitivity)** - Can we catch clones?
- **Layer 2 (Precision)** - Do we avoid false accusations?
- **Layer 3 (Generalization)** - Does it work on real-world code?

By following this guide, you can:
- ✅ Understand the benchmark design
- ✅ Interpret results correctly
- ✅ Improve your detector systematically
- ✅ Compare engines fairly
- ✅ Track progress over time

**Happy benchmarking!** 🚀

---

*Document Version: 1.0*  
*Last Updated: 2026-04-02*  
*Status: Production Ready*