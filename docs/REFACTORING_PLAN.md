# CodeProvenance Refactoring Plan: From Working System to Research-Grade Platform

## Executive Summary

This document outlines the systematic refactoring needed to elevate CodeProvenance from a functional plagiarism detector to a **unified code similarity evaluation and forensic analysis platform** suitable for research publication and industry adoption.

### Current State
- ✅ Working detection pipeline
- ✅ Multiple similarity engines
- ✅ Benchmark framework
- ✅ External tool integration

### Target State
- 🎯 Research-grade platform
- 🎯 Formal intermediate representations
- 🎯 Versioned strategy architecture
- 🎯 Forensic intelligence layer
- 🎯 Explicit pipeline phases
- 🎯 Publication-ready documentation

---

## Critical Issues Identified

| Issue | Severity | Impact | Effort |
|-------|----------|--------|--------|
| Engine version sprawl | 🔴 Critical | Reproducibility, evaluation integrity | Medium |
| Missing IR layer | 🔴 Critical | Module drift, debugging pain | High |
| Pipeline too generic | 🟡 High | Readability, onboarding | Medium |
| Forensics buried | 🟡 High | Strategic value hidden | Low |
| Dataset schema missing | 🟡 Medium | Cross-dataset comparison | Low |

---

## Phase 1: Foundation (Weeks 1-2)

### 1.1 Formalize Intermediate Representation (IR)

**Problem:** Implicit data structures between parser/normalizer/similarity cause module drift and debugging pain.

**Solution:** Create explicit IR layer with formal contracts.

```
core/
  ir/
    __init__.py
    base_ir.py              # Abstract base class
    ast_ir.py               # AST-based representation
    token_ir.py             # Token-based representation
    graph_ir.py             # Graph-based representation
    ir_converter.py         # Convert between representations
```

**Implementation:**

```python
# core/ir/base_ir.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class IRMetadata:
    """Metadata for any IR representation."""
    language: str
    source_hash: str
    timestamp: str
    representation_type: str

class BaseIR(ABC):
    """Abstract base for all intermediate representations."""
    
    def __init__(self, metadata: IRMetadata):
        self.metadata = metadata
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        pass
    
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseIR':
        """Deserialize from dictionary."""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate IR integrity."""
        pass

# core/ir/ast_ir.py
@dataclass
class ASTNode:
    """Represents a node in the AST."""
    node_type: str
    value: str
    children: List['ASTNode']
    line_start: int
    line_end: int
    metadata: Dict[str, Any]

class ASTIR(BaseIR):
    """AST-based intermediate representation."""
    
    def __init__(self, root: ASTNode, metadata: IRMetadata):
        super().__init__(metadata)
        self.root = root
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.__dict__,
            "root": self._node_to_dict(self.root)
        }
    
    def _node_to_dict(self, node: ASTNode) -> Dict[str, Any]:
        return {
            "node_type": node.node_type,
            "value": node.value,
            "children": [self._node_to_dict(c) for c in node.children],
            "line_start": node.line_start,
            "line_end": node.line_end,
            "metadata": node.metadata
        }
```

**Benefits:**
- ✅ Formal contracts between modules
- ✅ Reproducibility guaranteed
- ✅ Debugging becomes straightforward
- ✅ Visualization becomes possible

---

### 1.2 Fix Engine Version Sprawl

**Problem:** `adapters/codeprovenance_engine_v[1-5].py` creates fragile versioning, ambiguous evaluation, and reproducibility issues.

**Solution:** Versioned strategy registration pattern.

```
similarity/
  engines/
    codeprovenance/
      __init__.py
      base.py                 # Base class
      v1.py                   # Version 1 implementation
      v2.py                   # Version 2 implementation
      v3.py                   # Version 3 implementation
      registry.py             # Engine registry
```

**Implementation:**

```python
# similarity/engines/codeprovenance/registry.py
from typing import Dict, Type
from .base import BaseCodeProvenanceEngine

ENGINE_REGISTRY: Dict[str, Type[BaseCodeProvenanceEngine]] = {}

def register_engine(version: str):
    """Decorator to register an engine version."""
    def decorator(cls):
        ENGINE_REGISTRY[version] = cls
        return cls
    return decorator

def get_engine(version: str) -> BaseCodeProvenanceEngine:
    """Get engine instance by version."""
    if version not in ENGINE_REGISTRY:
        raise ValueError(f"Unknown engine version: {version}")
    return ENGINE_REGISTRY[version]()

# similarity/engines/codeprovenance/v1.py
from .base import BaseCodeProvenanceEngine
from .registry import register_engine

@register_engine("codeprovenance:v1")
class CodeProvenanceV1(BaseCodeProvenanceEngine):
    """Version 1: Basic token similarity."""
    
    @property
    def version(self) -> str:
        return "codeprovenance:v1"
    
    @property
    def name(self) -> str:
        return "CodeProvenance v1"
    
    def compare(self, code_a: str, code_b: str) -> float:
        # V1 implementation
        ...

# similarity/engines/codeprovenance/v2.py
@register_engine("codeprovenance:v2")
class CodeProvenanceV2(BaseCodeProvenanceEngine):
    """Version 2: Token + AST hybrid."""
    
    @property
    def version(self) -> str:
        return "codeprovenance:v2"
    
    @property
    def name(self) -> str:
        return "CodeProvenance v2"
    
    def compare(self, code_a: str, code_b: str) -> float:
        # V2 implementation
        ...
```

**Configuration Usage:**

```yaml
# config/benchmark.yaml
engines:
  - codeprovenance:v1
  - codeprovenance:v2
  - codeprovenance:v3
  - jplag
  - moss
```

**Benefits:**
- ✅ Clear version contracts
- ✅ Reproducible evaluations
- ✅ Easy to add new versions
- ✅ Historical integrity maintained

---

## Phase 2: Architecture Elevation (Weeks 3-4)

### 2.1 Elevate Analysis to Forensics

**Problem:** `analysis/` directory buries strategically important forensic intelligence.

**Solution:** Rename and restructure as `forensics/`.

```
forensics/
  __init__.py
  causal/
    __init__.py
    ranking.py              # Causal similarity ranking
    attribution.py          # Root cause attribution
  attribution/
    __init__.py
    error_analysis.py       # Error categorization
    failure_patterns.py     # Failure pattern detection
  clone_taxonomy/
    __init__.py
    type_classifier.py      # Clone type classification
    technique_detector.py   # Technique detection
  visualizations/
    __init__.py
    heatmaps.py             # Token-level heatmaps
    ast_alignment.py        # AST alignment visualization
    causal_graphs.py        # Causal similarity graphs
```

**Benefits:**
- ✅ Strategic value emphasized
- ✅ Clear forensic purpose
- ✅ Ready for explainability features
- ✅ Publication-ready structure

---

### 2.2 Make Pipeline Phases Explicit

**Problem:** Generic "stages" reduce readability and onboarding ease.

**Solution:** Create explicit pipeline phases.

```
pipeline/
  __init__.py
  phases/
    __init__.py
    ingest.py               # Phase 1: File ingestion
    normalize.py            # Phase 2: Code normalization
    represent.py            # Phase 3: IR generation
    compare.py              # Phase 4: Similarity computation
    aggregate.py            # Phase 5: Result aggregation
    evaluate.py             # Phase 6: Metric evaluation
    report.py               # Phase 7: Report generation
  orchestrator.py           # Coordinates phases
  config.py                 # Configuration
```

**Implementation:**

```python
# pipeline/phases/ingest.py
from dataclasses import dataclass
from typing import List
from pathlib import Path

@dataclass
class IngestedFile:
    path: Path
    content: str
    language: str
    metadata: dict

class IngestionPhase:
    """Phase 1: Load and validate input files."""
    
    def execute(self, paths: List[Path]) -> List[IngestedFile]:
        """Ingest files from paths."""
        results = []
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            content = path.read_text(encoding='utf-8')
            language = self._detect_language(path)
            
            results.append(IngestedFile(
                path=path,
                content=content,
                language=language,
                metadata={"size": len(content)}
            ))
        return results
    
    def _detect_language(self, path: Path) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            '.py': 'python',
            '.java': 'java',
            '.js': 'javascript',
            '.c': 'c',
            '.cpp': 'cpp',
        }
        return ext_map.get(path.suffix, 'unknown')

# pipeline/orchestrator.py
from typing import List, Dict, Any
from .phases import (
    IngestionPhase,
    NormalizationPhase,
    RepresentationPhase,
    ComparisonPhase,
    AggregationPhase,
    EvaluationPhase,
    ReportingPhase
)

class PipelineOrchestrator:
    """Coordinates execution of all pipeline phases."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.phases = [
            IngestionPhase(),
            NormalizationPhase(),
            RepresentationPhase(),
            ComparisonPhase(),
            AggregationPhase(),
            EvaluationPhase(),
            ReportingPhase()
        ]
    
    def execute(self, inputs: List[str]) -> Dict[str, Any]:
        """Execute full pipeline."""
        data = {"inputs": inputs}
        
        for phase in self.phases:
            data = phase.execute(data, self.config)
        
        return data
```

**Benefits:**
- ✅ Clear execution flow
- ✅ Easy to debug individual phases
- ✅ Simple to add/remove phases
- ✅ Onboarding becomes trivial

---

## Phase 3: Dataset & Reporting (Weeks 5-6)

### 3.1 Add Dataset Contract Schema

**Problem:** No formal metadata standard for cross-dataset comparison.

**Solution:** Create dataset schema with contracts.

```
datasets/
  __init__.py
  schema.py                 # Dataset metadata contract
  validators.py             # Dataset validation
  bigclonebench.py
  codesearchnet.py
  ...existing loaders...
```

**Implementation:**

```python
# datasets/schema.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

class CloneType(Enum):
    """Standardized clone types."""
    TYPE_1 = "type1"  # Identical
    TYPE_2 = "type2"  # Renamed
    TYPE_3 = "type3"  # Restructured
    TYPE_4 = "type4"  # Semantic

class Difficulty(Enum):
    """Dataset difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

@dataclass
class DatasetMetadata:
    """Contract for dataset metadata."""
    name: str
    version: str
    language: str
    clone_types: List[CloneType]
    difficulty: Difficulty
    size: int  # Number of pairs
    source: str  # Where it came from
    license: str
    ground_truth_format: str  # "binary", "continuous", "multi-class"
    description: str
    
    def validate(self) -> bool:
        """Validate metadata completeness."""
        required = [
            self.name,
            self.version,
            self.language,
            self.clone_types,
            self.size > 0,
            self.source,
            self.ground_truth_format
        ]
        return all(required)

class DatasetContract:
    """Base class for all dataset loaders."""
    
    @property
    def metadata(self) -> DatasetMetadata:
        """Return dataset metadata."""
        raise NotImplementedError
    
    def load(self, **kwargs) -> Any:
        """Load dataset."""
        raise NotImplementedError
    
    def validate(self) -> bool:
        """Validate dataset integrity."""
        return self.metadata.validate()

# datasets/validators.py
from typing import List, Dict, Any
from .schema import DatasetMetadata

class DatasetValidator:
    """Validates datasets against schema."""
    
    @staticmethod
    def validate_metadata(metadata: DatasetMetadata) -> List[str]:
        """Validate metadata and return errors."""
        errors = []
        
        if not metadata.name:
            errors.append("Dataset name is required")
        
        if not metadata.version:
            errors.append("Dataset version is required")
        
        if not metadata.language:
            errors.append("Language is required")
        
        if not metadata.clone_types:
            errors.append("At least one clone type is required")
        
        if metadata.size <= 0:
            errors.append("Dataset size must be positive")
        
        return errors
    
    @staticmethod
    def validate_ground_truth(pairs: List[Dict]) -> List[str]:
        """Validate ground truth format."""
        errors = []
        
        for i, pair in enumerate(pairs):
            if 'label' not in pair:
                errors.append(f"Pair {i} missing label")
            elif pair['label'] not in [0, 1]:
                errors.append(f"Pair {i} has invalid label: {pair['label']}")
        
        return errors
```

**Usage Example:**

```python
# datasets/bigclonebench.py
from .schema import DatasetContract, DatasetMetadata, CloneType, Difficulty

class BigCloneBenchDataset(DatasetContract):
    
    @property
    def metadata(self) -> DatasetMetadata:
        return DatasetMetadata(
            name="BigCloneBench",
            version="bceval_2024",
            language="java",
            clone_types=[CloneType.TYPE_1, CloneType.TYPE_2, CloneType.TYPE_3, CloneType.TYPE_4],
            difficulty=Difficulty.HARD,
            size=55000,
            source="https://onedrive.live.com/...",
            license="Academic use only",
            ground_truth_format="binary",
            description="Industry-standard Java clone detection benchmark"
        )
    
    def load(self, **kwargs):
        # Implementation
        ...
```

**Benefits:**
- ✅ Consistent metadata across datasets
- ✅ Cross-dataset comparison becomes possible
- ✅ Validation catches issues early
- ✅ Documentation becomes self-describing

---

### 3.2 Upgrade Reporting Layer

**Problem:** Current reporting is underpowered for the system's ambition.

**Solution:** Add 3-tier reporting with visualizations.

```
reporting/
  __init__.py
  tiers/
    __init__.py
    scientific.py           # Paper-ready reports
    operational.py          # Dashboard reports
    forensic.py             # Case-level drilldown
  visualizations/
    __init__.py
    heatmaps.py             # Token-level heatmaps
    ast_alignment.py        # AST alignment diagrams
    causal_graphs.py        # Causal similarity graphs
    distributions.py        # Score distributions
  generators/
    __init__.py
    json_generator.py
    html_generator.py
    pdf_generator.py
    latex_generator.py      # For papers
```

**Implementation:**

```python
# reporting/tiers/scientific.py
from dataclasses import dataclass
from typing import Dict, List, Any
import json

@dataclass
class ScientificReport:
    """Paper-ready benchmark report."""
    title: str
    abstract: str
    methodology: str
    results: Dict[str, Any]
    tables: List[Dict]
    figures: List[str]  # Paths to generated figures
    statistical_significance: Dict[str, Any]
    reproducibility_info: Dict[str, Any]
    
    def to_latex(self) -> str:
        """Generate LaTeX format for papers."""
        latex = f"""
\\section{{Results}}

\\subsection{{Overall Performance}}

{self._results_to_latex()}

\\subsection{{Statistical Significance}}

{self._significance_to_latex()}

\\subsection{{Reproducibility}}

{self._reproducibility_to_latex()}
"""
        return latex
    
    def _results_to_latex(self) -> str:
        """Convert results to LaTeX table."""
        rows = []
        for engine, metrics in self.results.items():
            rows.append(f"{engine} & {metrics['precision']:.4f} & {metrics['recall']:.4f} & {metrics['f1']:.4f} \\\\")
        
        return f"""
\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{l|ccc}}
\\hline
Engine & Precision & Recall & F1 \\\\
\\hline
{chr(10).join(rows)}
\\hline
\\end{{tabular}}
\\caption{{Benchmark Results}}
\\end{{table}}
"""

# reporting/visualizations/heatmaps.py
from typing import List, Tuple
import numpy as np
import matplotlib.pyplot as plt

class TokenHeatmapGenerator:
    """Generate token-level similarity heatmaps."""
    
    def generate(
        self,
        code_a: str,
        code_b: str,
        similarity_matrix: np.ndarray,
        output_path: str
    ) -> str:
        """Generate heatmap visualization."""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        # Tokenize
        tokens_a = self._tokenize(code_a)
        tokens_b = self._tokenize(code_b)
        
        # Plot similarity matrix
        im = axes[0].imshow(similarity_matrix, cmap='YlOrRd', aspect='auto')
        axes[0].set_xticks(range(len(tokens_b)))
        axes[0].set_xticklabels(tokens_b, rotation=45, ha='right')
        axes[0].set_yticks(range(len(tokens_a)))
        axes[0].set_yticklabels(tokens_a)
        axes[0].set_title('Token Similarity Matrix')
        plt.colorbar(im, ax=axes[0])
        
        # Highlight matches
        threshold = 0.8
        matches = np.where(similarity_matrix > threshold)
        for i, j in zip(matches[0], matches[1]):
            axes[0].add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, 
                                           fill=False, edgecolor='red', linewidth=2))
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return output_path
```

**Benefits:**
- ✅ Publication-ready reports
- ✅ Interactive dashboards
- ✅ Forensic drilldown capability
- ✅ Visualization for explainability

---

## Phase 4: Integration & Validation (Weeks 7-8)

### 4.1 Update Configuration System

```yaml
# config/benchmark_v2.yaml
system:
  name: "CodeProvenance"
  version: "2.0"
  mode: "research"

pipeline:
  phases:
    - ingest
    - normalize
    - represent
    - compare
    - aggregate
    - evaluate
    - report

engines:
  - codeprovenance:v1
  - codeprovenance:v2
  - codeprovenance:v3
  - jplag
  - moss

datasets:
  - bigclonebench
  - codesearchnet
  - synthetic

evaluation:
  layers:
    - sensitivity
    - precision
    - generalization
  weights:
    sensitivity: 0.4
    precision: 0.3
    generalization: 0.3

reporting:
  tiers:
    - scientific
    - operational
    - forensic
  visualizations:
    - heatmaps
    - ast_alignment
    - causal_graphs

forensics:
  enabled: true
  causal_analysis: true
  attribution: true
  clone_taxonomy: true
```

### 4.2 Migration Guide

**Step 1: Update Imports**
```python
# Old
from benchmark.normalization.canonicalizer import Canonicalizer

# New
from benchmark.normalizer.canonicalizer import Canonicalizer
```

**Step 2: Update Engine References**
```python
# Old
from benchmark.adapters.codeprovenance_engine_v3 import CodeProvenanceEngine

# New
from benchmark.similarity.engines.codeprovenance import get_engine
engine = get_engine("codeprovenance:v3")
```

**Step 3: Update Pipeline Usage**
```python
# Old
from benchmark.pipeline.runner import run_benchmark

# New
from benchmark.pipeline.orchestrator import PipelineOrchestrator
orchestrator = PipelineOrchestrator(config)
results = orchestrator.execute(inputs)
```

---

## Timeline & Milestones

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1-2 | Foundation | IR layer, engine registry |
| 3-4 | Architecture | Forensics, explicit pipeline |
| 5-6 | Dataset & Reporting | Schema, 3-tier reporting |
| 7-8 | Integration | Config update, migration guide |

---

## Success Metrics

### Technical Metrics
- ✅ All engines use versioned registration
- ✅ IR layer used by 100% of modules
- ✅ Pipeline phases explicit and documented
- ✅ Dataset schema validated for all loaders
- ✅ Reporting generates LaTeX for papers

### Quality Metrics
- ✅ Code complexity reduced (cyclomatic complexity < 10)
- ✅ Test coverage > 80%
- ✅ Documentation coverage > 90%
- ✅ Onboarding time reduced by 50%

### Research Metrics
- ✅ Reproducible evaluations (same config → same results)
- ✅ Cross-dataset comparison enabled
- ✅ Statistical significance testing automated
- ✅ Publication-ready reports generated

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes | Maintain backward compatibility layer |
| Migration complexity | Provide automated migration scripts |
| Performance regression | Benchmark before/after each phase |
| Scope creep | Strict phase boundaries |

---

## Conclusion

This refactoring plan transforms CodeProvenance from a functional system into a **research-grade platform** that:

1. **Maintains reproducibility** through versioned strategies
2. **Enables debugging** through formal IR
3. **Clarifies execution** through explicit phases
4. **Emphasizes strategic value** through forensics layer
5. **Supports research** through dataset contracts and reporting

**The result:** A system that competes with MOSS, JPlag, and CodeXGLUE while uniquely combining benchmarking, multi-engine comparison, and explainability.

**Next step:** Execute Phase 1 (Foundation) to establish the architectural groundwork.

---

*Document Version: 1.0*  
*Created: 2026-04-02*  
*Status: Ready for Review*