# Engine Architecture - Current State & Consolidation Strategy

## Overview

This document outlines the current engine architecture, identifies redundancy, and provides a consolidation strategy to reduce complexity while maintaining functionality.

## Current Engine Landscape

### Similarity Engines (10+ implementations)

| Engine | Type | Purpose | Status |
|--------|------|---------|--------|
| `token_winnowing.py` | Token | Winnowing-based similarity | Active |
| `ast_similarity.py` | AST | AST structural similarity | Active |
| `graph_similarity.py` | Graph | Graph-based similarity | Active |
| `embedding_similarity.py` | Embedding | Embedding-based similarity | Active |
| `execution_similarity.py` | Execution | Runtime execution similarity | Active |
| `hybrid.py` | Hybrid | Multi-modal fusion | Active |
| `codebert_similarity.py` | ML | CodeBERT integration | Active |
| `unixcoder_similarity.py` | ML | UniXcoder integration | Active |
| `deep_analysis.py` | ML | Deep analysis | Active |
| `structural_ast_similarity.py` | AST | Structural AST | Active |

### ML Engines (5+ implementations)

| Engine | Purpose | Status |
|--------|---------|--------|
| `tfidf_detector.py` | TF-IDF detection | Active |
| `fusion_engine.py` | Score fusion | Active |
| `prl_v4.py` | PRL v4 | Active |

### Benchmark Engines (10+ adapters)

| Adapter | Tool | Status |
|---------|------|--------|
| `codeprovenance_engine.py` | CodeProvenance v1 | Active |
| `codeprovenance_engine_v2.py` | CodeProvenance v2 | Active |
| `codeprovenance_engine_v3.py` | CodeProvenance v3 | Active |
| `codeprovenance_engine_v4.py` | CodeProvenance v4 | Active |
| `codeprovenance_engine_v5.py` | CodeProvenance v5 | Active |
| `jplag_engine.py` | JPlag | Active |
| `moss_runner.py` | MOSS | Active |
| `nicad_runner.py` | NiCad | Active |
| `pmd_runner.py` | PMD | Active |
| `dolos_runner.py` | Dolos | Active |

## Redundancy Analysis

### 1. Token-based Redundancy

**Current:**
- `token_winnowing.py` - Winnowing algorithm
- `embedding_similarity.py` - Token embeddings
- `tfidf_detector.py` - TF-IDF

**Issue:** Multiple token-based approaches with overlapping functionality.

**Recommendation:** Keep `token_winnowing.py` as primary, deprecate others.

### 2. AST-based Redundancy

**Current:**
- `ast_similarity.py` - General AST
- `structural_ast_similarity.py` - Structural AST

**Issue:** Two AST implementations with similar goals.

**Recommendation:** Merge into single `ast_similarity.py` with configuration options.

### 3. ML-based Redundancy

**Current:**
- `codebert_similarity.py` - CodeBERT
- `unixcoder_similarity.py` - UniXcoder
- `deep_analysis.py` - Deep analysis

**Issue:** Multiple ML models with overlapping capabilities.

**Recommendation:** Create unified ML interface, keep specialized implementations.

### 4. CodeProvenance Version Redundancy

**Current:**
- 5 versions of CodeProvenance engine

**Issue:** Version sprawl without clear differentiation.

**Recommendation:** Keep only latest stable version, archive others.

## Consolidation Strategy

### Phase 1: Immediate (Current)

1. **Document current state** ✅ (this document)
2. **Identify critical engines** - Keep only essential ones
3. **Mark deprecated engines** - Add deprecation warnings

### Phase 2: Short-term (1-2 weeks)

1. **Merge redundant AST engines**
   ```python
   # Before
   ast_similarity.py
   structural_ast_similarity.py
   
   # After
   ast_similarity.py  # With config for structural mode
   ```

2. **Consolidate token engines**
   ```python
   # Before
   token_winnowing.py
   embedding_similarity.py
   tfidf_detector.py
   
   # After
   token_similarity.py  # With multiple strategies
   ```

3. **Archive old CodeProvenance versions**
   ```bash
   # Move to archive
   mv codeprovenance_engine_v[1-4].py archive/
   # Keep only v5
   ```

### Phase 3: Medium-term (1 month)

1. **Create unified ML interface**
   ```python
   class MLEngine(ABC):
       @abstractmethod
       def encode(self, code: str) -> np.ndarray:
           pass
       
       @abstractmethod
       def similarity(self, code1: str, code2: str) -> float:
           pass
   ```

2. **Implement engine registry with versioning**
   ```python
   @register_engine("token", version="2.0")
   class TokenEngine(MLEngine):
       pass
   ```

3. **Add engine deprecation system**
   ```python
   @deprecated(since="2.0", use="token_similarity.py")
   class TokenWinnowingEngine:
       pass
   ```

### Phase 4: Long-term (3+ months)

1. **Reduce to 3-5 core engines**
   - Token-based (winnowing)
   - AST-based (structural)
   - Embedding-based (ML)
   - Execution-based (runtime)
   - Fusion (ensemble)

2. **External tools via adapters only**
   - JPlag, MOSS, NiCad, etc. remain as adapters
   - No internal implementations

3. **Plugin architecture for extensions**
   ```python
   class EnginePlugin(ABC):
       @abstractmethod
       def get_engine(self) -> BaseEngine:
           pass
   ```

## Recommended Final Engine Structure

```
engines/
├── similarity/
│   ├── token.py          # Token-based similarity (winnowing)
│   ├── ast.py            # AST-based similarity (structural)
│   ├── embedding.py      # Embedding-based similarity (ML)
│   ├── execution.py      # Execution-based similarity
│   └── fusion.py         # Ensemble fusion
├── ml/
│   ├── base.py           # Base ML interface
│   ├── codebert.py       # CodeBERT implementation
│   └── unixcoder.py      # UniXcoder implementation
├── scoring/
│   └── fusion_engine.py  # Final score computation
└── adapters/
    ├── jplag.py          # JPlag adapter
    ├── moss.py           # MOSS adapter
    └── nicad.py          # NiCad adapter
```

## Benefits of Consolidation

1. **Reduced Complexity:** From 20+ engines to 5-7 core engines
2. **Easier Maintenance:** Fewer code paths to maintain
3. **Clearer Responsibilities:** Each engine has single, clear purpose
4. **Better Testing:** Fewer engines = easier to test thoroughly
5. **Improved Performance:** Optimized core engines
6. **Easier Onboarding:** New developers learn fewer systems

## Migration Guide

### For Engine Users

1. **Check deprecation warnings** - Update to new engines
2. **Review configuration** - Some options may change
3. **Test thoroughly** - Ensure behavior matches expectations

### For Engine Developers

1. **Follow new interface** - Implement `BaseEngine` or `MLEngine`
2. **Add versioning** - Use `@register_engine` decorator
3. **Document clearly** - Explain when to use this engine
4. **Add tests** - Ensure comprehensive coverage

## Timeline

| Phase | Duration | Goal |
|-------|----------|------|
| Phase 1 | Current | Document and plan |
| Phase 2 | 1-2 weeks | Merge redundant engines |
| Phase 3 | 1 month | Unified interfaces |
| Phase 4 | 3+ months | Final consolidation |

## Success Metrics

- **Engine count:** Reduce from 20+ to 5-7
- **Code duplication:** Reduce by 50%+
- **Test coverage:** Increase to 90%+
- **Documentation:** 100% of engines documented
- **Performance:** No regression in core metrics

## Conclusion

The current engine architecture has grown organically and now has significant redundancy. By following this consolidation strategy, we can:

1. Maintain all current functionality
2. Reduce complexity and maintenance burden
3. Improve code quality and testability
4. Create a more scalable architecture

**The goal is not to remove features, but to organize them better.**