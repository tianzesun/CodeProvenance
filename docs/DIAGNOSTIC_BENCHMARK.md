# Diagnostic Intelligence System

## What Makes This Different

Traditional benchmark systems answer: **"How good is my detector?"**

This diagnostic system answers: **"WHY exactly is it failing, and what code should I change?"**

## Components

### 1. Error Attribution Model (EAM)

Per-pair decomposition of similarity error into component losses:

```json
{
    "pair_id": "synthetic_00042",
    "ground_truth": 1.0,
    "predicted_score": 0.32,
    "error": -0.68,
    "component_scores": {"token": 0.45, "ast": 0.22, "structure": 0.15},
    "loss_contribution": {"token": 0.55, "ast": 0.28, "structure": 0.17},
    "primary_cause": "token_loss",
    "clone_type": 2
}
```

### 2. Clone-Type Sensitivity Matrix

The diagnostic table research papers publish:

```
                     T1    T2    T3    T4
token_winnowing      1.00  0.00  0.72  1.00
ast_structural       1.00  1.00  1.00  1.00
hybrid               1.00  0.00  0.98  1.00
```

Key finding: **Type-2 (renamed) clones are the universal weakness** across all engines.

### 3. Threshold Stability Analysis

Determines if the model's performance depends on a specific threshold:

```
Engine             Robustness   Sensitivity   Optimal T
token_winnowing    0.851        0.378         0.01
ast_structural     0.723        0.503         0.95
hybrid             0.785        0.663         0.27
```

- **Token engine**: Most robust, optimal threshold near 0 (everything matches)
- **AST engine**: Most sensitive, optimal threshold near 1 (very strict)
- **Hybrid**: Best trade-off between robustness and discrimination

### 4. Error Attribution (Loss Decomposition)

```
Engine             Token Loss   AST Loss  Struct Loss
token_winnowing    0.9358       0.0424    0.0218
ast_structural     0.0508       0.4301    0.5191
hybrid             0.5098       0.2290    0.2612
```

- Token engine fails due to **token-level changes** (renames)
- AST engine fails due to **over-matching structure**
- Hybrid splits loss across components

### 5. Failure Clustering

Groups failures into "attack surfaces":

```
Engine: hybrid
  Attack Surface: partial_overlap (51 failures)
    Pattern: Partial code match with inserted different logic
    Fix: Implement sliding window matching or LCS
  
  Attack Surface: rename_heavy (11 failures)
    Pattern: Variable/method rename not detected
    Fix: Add identifier normalization
```

## Usage

```bash
# Run full diagnostic benchmark
python -m benchmark.run_diagnostic

# Standard benchmark with metrics
python -m benchmark.run_benchmark
```

## Key Findings from Baseline

1. **Type-2 clone detection is the gap**: All engines score 0.0 recall on renamed clones
2. **Token engine is fragile at low threshold**: Optimal T=0.01 means it barely discriminates
3. **AST engine over-matches**: 100% recall but 109 false positives (54.5% FP rate)
4. **Hybrid is the best trade-off**: F1=0.817 with only 11 FPs
5. **Primary improvement target**: Rename detection (11-64 failures per engine)

## Iteration Workflow

1. Run diagnostic: `python -m benchmark.run_diagnostic`
2. Read recommendation: "Add identifier normalization"
3. Implement fix: Add `identifier_normalization` to normalizer pipeline
4. Re-run diagnostic: Verify improvement on Type-2 clones
5. Compare: Check `clone_type_sensitivity` T2 score improved from 0.00