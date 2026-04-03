# Architecture Governance - Non-Negotiable Rules

## Overview

This document defines the **non-negotiable architectural rules** that must be enforced at all times. These rules are not suggestions - they are mandatory constraints that ensure system consistency, reproducibility, and maintainability.

## Rule 1: Single Source of Truth for Scoring

**Mandate:** Only ONE module computes final similarity scores.

**Authority:** `src/engines/scoring/fusion_engine.py`

**Enforcement:**
- All other modules MUST be feature providers, not decision makers
- No module may compute final similarity scores except the fusion engine
- All scoring logic must flow through `compute_final_similarity()`

**Verification:**
```python
# CORRECT - Use fusion engine
from src.engines.scoring import compute_final_similarity
result = compute_final_similarity(token_score=0.8, ast_score=0.9)

# WRONG - Don't compute scores directly
similarity = (token_score + ast_score) / 2  # VIOLATION!
```

**Consequences of Violation:**
- Reproducibility breaks
- Debugging becomes impossible
- Results drift across modules
- System becomes unreliable

## Rule 2: Frozen IR Schema

**Mandate:** IR schemas are versioned and immutable.

**Authority:** `src/core/ir/__init__.py`

**Enforcement:**
- All IR schemas must be versioned (V1, V2, V3, LATEST)
- IR metadata is immutable (frozen dataclass)
- All IR implementations must inherit from `BaseIR`
- IR schemas cannot be modified after registration

**Verification:**
```python
# CORRECT - Use versioned IR
from src.core.ir import IRVersion, IRMetadata
metadata = IRMetadata(
    version=IRVersion.V3,
    language="python",
    source_hash="abc123",
    timestamp="2024-01-01T00:00:00",
    representation_type="ast"
)

# WRONG - Don't create unversioned IR
class MyIR:  # VIOLATION!
    pass
```

**Consequences of Violation:**
- IR divergence breaks system consistency
- Forensic explanations become unreliable
- Visualization mismatch with scoring engine
- System-wide inconsistency

## Rule 3: Strict Layer Enforcement

**Mandate:** Dependencies flow in one direction only.

**Dependency Direction:**
```
api → application → domain → core
                 ↓
          engines / evaluation (read-only)
                 ↓
           infrastructure
```

**Enforcement:**
- `domain/` CANNOT import from `infrastructure/`, `api/`, `web/`, `utils/`
- `application/` depends ONLY on `domain/` and `core/`
- `infrastructure/` implements domain interfaces
- `api/`, `web/` are presentation layer only
- No reverse imports. Ever.

**Verification:**
```python
# CORRECT - Domain doesn't import infrastructure
# domain/models.py
from src.core.ir import BaseIR  # OK - core dependency

# WRONG - Domain imports infrastructure
# domain/models.py
from src.infrastructure.db import DatabaseManager  # VIOLATION!
```

**Consequences of Violation:**
- Business logic leaks across layers
- Architecture becomes cosmetic
- Maintenance becomes impossible
- System becomes untestable

## Rule 4: Evaluation/Pipeline Separation

**Mandate:** Evaluation and pipeline have distinct responsibilities.

**Evaluation (`src/evaluation/`):**
- Computes metrics ONLY (precision, recall, F1)
- Does NOT execute engines
- Does NOT contain business logic
- Receives scores from fusion engine

**Pipeline (`src/pipeline/`):**
- Orchestrates execution ONLY
- Does NOT compute metrics
- Does NOT contain business logic
- Delegates scoring to fusion engine

**Enforcement:**
```python
# CORRECT - Evaluation computes metrics
from src.evaluation import Evaluator
evaluator = Evaluator()
result = evaluator.evaluate(predictions, labels)  # Metrics only

# CORRECT - Pipeline orchestrates
from src.pipeline import ScoringPipeline
pipeline = ScoringPipeline()
result = pipeline.execute(code_a, code_b)  # Orchestration only

# WRONG - Evaluation computes scores
# evaluation/core/evaluator.py
score = (ast_score + token_score) / 2  # VIOLATION!

# WRONG - Pipeline computes metrics
# pipeline/scoring_pipeline.py
precision = tp / (tp + fp)  # VIOLATION!
```

**Consequences of Violation:**
- Logical duplication across modules
- Structural separation becomes meaningless
- Debugging becomes impossible
- System becomes inconsistent

## Rule 5: Engine Redundancy Control

**Mandate:** Engine count must be controlled and justified.

**Current State:** 20+ engines (needs consolidation)

**Target State:** 5-7 core engines

**Enforcement:**
- New engines require architecture review
- Redundant engines must be deprecated
- Each engine must have clear, distinct purpose
- Engine overlap must be eliminated

**Engine Categories:**
1. **Token-based** (1 engine): Winnowing similarity
2. **AST-based** (1 engine): Structural similarity
3. **Embedding-based** (1 engine): ML similarity
4. **Execution-based** (1 engine): Runtime similarity
5. **Fusion** (1 engine): Ensemble scoring
6. **Adapters** (N engines): External tools (JPlag, MOSS, etc.)

**Verification:**
```python
# CORRECT - Clear engine purpose
@register_engine("token_winnowing")
class TokenWinnowingEngine(BaseEngine):
    """Token-based similarity using winnowing algorithm."""
    pass

# WRONG - Duplicate purpose
@register_engine("token_embedding")
class TokenEmbeddingEngine(BaseEngine):
    """Token-based similarity using embeddings."""
    pass  # Overlaps with embedding engine!
```

**Consequences of Violation:**
- Maintenance burden exceeds development value
- Debugging becomes impossible
- System becomes opaque
- Quality degrades

## Rule 6: Bootstrap Isolation

**Mandate:** Bootstrap contains ONLY dependency wiring.

**Authority:** `src/bootstrap/__init__.py`

**Enforcement:**
- Bootstrap initializes components only
- No business logic in bootstrap
- No domain rules in bootstrap
- No execution logic in bootstrap

**Allowed in Bootstrap:**
- Dependency injection
- Configuration loading
- Service registration
- Database initialization

**Forbidden in Bootstrap:**
- Business logic
- Domain rules
- Scoring computation
- Metric calculation

**Verification:**
```python
# CORRECT - Bootstrap wires dependencies
class DependencyContainer:
    def _init_engines(self):
        # Register engines only
        registry.register("token", TokenEngine())
        
# WRONG - Bootstrap contains logic
class DependencyContainer:
    def _init_engines(self):
        # VIOLATION - Business logic in bootstrap
        score = self._compute_similarity()
```

**Consequences of Violation:**
- Bootstrap becomes "god module"
- Architecture integrity breaks
- System becomes monolithic
- Maintainability degrades

## Rule 7: Benchmark Isolation

**Mandate:** Benchmark contains external tools only.

**Authority:** `src/benchmark/`

**Enforcement:**
- Benchmark runs external tools (JPlag, MOSS, NiCad)
- Benchmark does NOT compute similarity scores
- Benchmark does NOT contain business logic
- Benchmark delegates to fusion engine for scoring

**Allowed in Benchmark:**
- External tool adapters
- Dataset loaders
- Result collection
- Report generation

**Forbidden in Benchmark:**
- Similarity computation
- Business logic
- Domain rules
- Scoring logic

**Verification:**
```python
# CORRECT - Benchmark runs external tools
class JPlagRunner:
    def run(self, code_a, code_b):
        # Call external JPlag tool
        return self._execute_jplag(code_a, code_b)
        
# WRONG - Benchmark computes scores
class BenchmarkEngine:
    def compare(self, code_a, code_b):
        # VIOLATION - Benchmark computes similarity
        return self._compute_similarity(code_a, code_b)
```

**Consequences of Violation:**
- Benchmark becomes second engines layer
- Evaluation logic duplicates
- System becomes inconsistent
- Debugging becomes impossible

## Enforcement Mechanisms

### 1. Import Validation
```python
# src/__init__.py
def validate_architecture():
    """Enforce architecture boundaries at import time."""
    # Validate domain doesn't import infrastructure
    # Validate dependencies flow correctly
    # Validate no reverse imports
```

### 2. Code Review Checklist
- [ ] Single scoring authority used?
- [ ] IR schema versioned?
- [ ] Layer dependencies correct?
- [ ] Evaluation/pipeline separated?
- [ ] Engine justified?
- [ ] Bootstrap isolated?
- [ ] Benchmark isolated?

### 3. Automated Testing
```python
def test_architecture_boundaries():
    """Test that architecture boundaries are enforced."""
    # Test domain doesn't import infrastructure
    # Test dependencies flow correctly
    # Test no reverse imports
```

### 4. Documentation Requirements
- All modules must document their responsibility
- All engines must document their purpose
- All IR schemas must be versioned
- All dependencies must be justified

## Governance Model

### Decision Authority
1. **Scoring Decisions:** Fusion engine only
2. **IR Schema Changes:** Architecture review required
3. **New Engines:** Architecture review required
4. **Layer Changes:** Architecture review required

### Review Process
1. **Proposal:** Document proposed change
2. **Review:** Architecture team reviews
3. **Approval:** Majority approval required
4. **Implementation:** Follow rules strictly
5. **Verification:** Automated checks pass

### Escalation Path
1. **Rule Violation:** Immediate fix required
2. **Architectural Debate:** Architecture team decides
3. **Emergency Exception:** CTO approval required

## Success Metrics

### Compliance Metrics
- **Import Validation:** 100% of imports validated
- **IR Versioning:** 100% of IR schemas versioned
- **Layer Dependencies:** 0 reverse imports
- **Engine Justification:** 100% of engines documented

### Quality Metrics
- **Reproducibility:** 100% of results reproducible
- **Debuggability:** All decisions traceable to fusion engine
- **Consistency:** No scoring drift across modules
- **Maintainability:** Clear module responsibilities

## Conclusion

These rules are **non-negotiable**. They ensure:

1. **Single Source of Truth:** One place computes scores
2. **Frozen Contracts:** IR schemas are immutable
3. **Strict Layers:** Dependencies flow correctly
4. **Clear Separation:** Modules have distinct responsibilities
5. **Controlled Growth:** Engine count is managed
6. **Isolated Concerns:** Bootstrap and benchmark are isolated

**Violation of these rules will result in:**
- System inconsistency
- Reproducibility failures
- Debugging impossibility
- Maintenance nightmares

**These rules are the foundation of a reliable, scalable, maintainable system.**