# Benchmark System for CodeProvenance

## Architecture Overview

The benchmark system is a **self-improving, evaluation-driven engineering loop** for code similarity detection algorithms.

### Core Loop

```
┌─────────────────────┐
│ 1. Build Detector   │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 2. Benchmark Engine │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 3. Evaluate Results │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 4. Analyze Weakness │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 5. Improve Detector │
└──────────┬──────────┘
           ↓
      (repeat)
```

## Design Rules

| Rule | Description |
|------|-------------|
| 1 | **Benchmark must NEVER change** - only detector changes |
| 2 | **Dataset must be versioned** - never update silently |
| 3 | **Metrics must be fixed** - otherwise comparisons meaningless |
| 4 | **One baseline per run** - no mixing engines |

## File Structure

```
benchmark/
├── __init__.py              # Engine registration
├── __main__.py              # CLI entry point
├── run_benchmark.py         # End-to-end runner
├── registry.py              # Engine registry
├── similarity/
│   ├── base_engine.py       # THE interface (BaseSimilarityEngine)
│   ├── engines.py           # Concrete engines (token, ast, hybrid)
│   ├── token_winnowing.py   # Token winnowing algorithm
│   ├── ast_subtree.py       # AST structural similarity
│   └── hybrid.py            # Combined similarity
├── datasets/
│   ├── bigclonebench.py     # BigCloneBench loader
│   ├── google_codejam.py    # Google Code Jam loader
│   ├── xiangtan.py          # Xiangtan University loader
│   └── synthetic_generator.py # Synthetic dataset generator
├── analysis/
│   └── failure_analysis.py  # Failure categorization
├── pipeline/
│   ├── config.py           # BenchmarkConfig dataclass
│   ├── loader.py           # CanonicalDataset interface
│   ├── stages.py           # PipelineStage classes
│   └── runner.py           # BenchmarkRunner
├── metrics/
│   └── __init__.py         # precision, recall, f1, map, mrr
└── reporting/
    └── __init__.py         # JSON/HTML writers
```

## Engine Interface (THE Contract)

**All engines MUST implement:**

```python
class BaseSimilarityEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier."""
        pass
    
    @abstractmethod
    def compare(self, code_a: str, code_b: str) -> float:
        """Return similarity in [0.0, 1.0]."""
        pass
```

## Usage

### Run All Engines (Quick)

```bash
python -m benchmark.run_benchmark
```

### Run Specific Engine

```bash
python -m benchmark.run_benchmark --engine hybrid
```

### Custom Dataset Size

```bash
python -m benchmark.run_benchmark \
    --type1 50 --type2 50 --type3 50 --type4 50 --non-clone 200
```

### Generate Synthetic Dataset

```bash
python -m benchmark generate -o data/synthetic_v1.json \
    --type1 50 --type2 50 --type3 50 --type4 50 --non-clone 200
```

### YAML Configuration

```bash
python -m benchmark run --config config/benchmark.yaml \
    --output reports/run_001.json
```

## Clone Types

| Type | Description | Detection Challenge |
|------|-------------|---------------------|
| 1 | Identical | Easy baseline |
| 2 | Renamed identifiers | Requires normalization |
| 3 | Restructured code | Requires AST analysis |
| 4 | Semantic equivalent | Requires deep semantic |

## Authoritative Benchmark Baselines (2026 Standard)

This is the official benchmark suite structure for all evaluations. All baselines
are scientifically accepted and widely used in industry and academia.

| Tier | Category | Systems |
|------|----------|---------|
| **1** | Canonical Baselines | MOSS, JPlag, NiCad |
| **2** | Practical / Scalable | Dolos, PMD CPD, SourcererCC |
| **3** | Advanced / Research | STRANGE, Deckard |
| **4** | Industry Reality Check | Turnitin, Codequiry |
| **5** | Modern LLM Baseline | Transformer Semantic, LLM Similarity |
| **6** | Specialized | Vendetect |

## Benchmark Evaluation Scenarios

All systems are evaluated across three critical scenarios:

1.  **Classic Plagiarism** (Copy + rename)
    - Must beat MOSS/JPlag
2.  **Near-miss / Obfuscation** (Reordering, refactoring)
    - Must beat NiCad / Deckard
3.  **AI-assisted Rewriting** (Same logic, different code)
    - Must beat embedding/LLM baseline

## Engine Performance (Baseline)

| Engine | Precision | Recall | F1 | MAP | MRR |
|--------|-----------|--------|-------|-------|-----|
| token_winnowing_v1 | 0.9259 | 0.6250 | 0.7463 | 0.917 | 1.0 |
| ast_structural_v1 | 0.6504 | 1.0000 | 0.7882 | 1.000 | 1.0 |
| **hybrid_v1** | **0.9355** | **0.7250** | **0.8169** | **0.969** | **1.0** |

### Weaknesses

- **Token wins on precision**: Struggles with renamed variables (20 FN Type-2)
- **AST wins on recall**: High false positive rate (43 FP)
- **Hybrid best overall**: Still misses 20 renamed clones

### Top Improvement Target

1.  **Normalizer**: Add identifier normalization for rename detection (20 failures)
2.  **AST engine**: Improve subtree matching (2 failures)

## Iteration Process

1. Run current baseline: `python -m benchmark.run_benchmark --config config/benchmark.yaml`
2. Analyze failures: Check `improvement_targets` in report JSON
3. Implement fix: Modify `benchmark/similarity/` or `normalizer/`
4. Re-run benchmark: Same config, same dataset
5. Compare: `run_001` vs `run_002` metrics