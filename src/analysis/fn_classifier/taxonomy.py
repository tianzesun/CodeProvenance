"""FN Classification Taxonomy - FN.md spec."""
from typing import Dict, List, Any, Set, NamedTuple, Optional
from dataclasses import dataclass, field
from enum import Enum

# Level-1 categories
class FNCategory(str, Enum):
    LEXICAL = "lexical_variation"
    STRUCTURAL = "structural_variation"
    SEMANTIC = "semantic_variation"
    OBFUSCATION = "obfuscation"
    AI_GENERATED = "ai_generated"
    CROSS_LANGUAGE = "cross_language"
    NOISE = "noise"

# Level-2 subcategories
SUBCATEGORIES = {
    FNCategory.LEXICAL: {"variable_renaming", "formatting_change", "comment_change"},
    FNCategory.STRUCTURAL: {"statement_reordering", "loop_transformation", "function_inlining", "function_splitting"},
    FNCategory.SEMANTIC: {"algorithm_equivalent", "logic_rewrite"},
    FNCategory.OBFUSCATION: {"dead_code_insertion", "control_flow_flattening", "opaque_predicates"},
    FNCategory.AI_GENERATED: {"llm_style_pattern", "over_generalized"},
    FNCategory.CROSS_LANGUAGE: {"cross_language_clone"},
    FNCategory.NOISE: {"data_error", "false_positive_in_truth"},
}

def label(category: FNCategory, subcategory: str) -> str:
    """Create hierarchical label: 'category.subcategory'."""
    return f"{category.value}.{subcategory}"

@dataclass
class FNResult:
    """Single classified FN result."""
    file1: str
    file2: str
    similarity: float
    labels: List[str] = field(default_factory=list)  # multi-label
    features: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0

@dataclass 
class FNAnalysis:
    """Complete FN analysis report."""
    total_fn: int
    by_category: Dict[str, int]
    results: List[FNResult]
    distribution: Dict[str, float]  # percentage

    def summary(self) -> str:
        lines = [f"FN Breakdown ({self.total_fn} total):"]
        for cat, pct in sorted(self.distribution.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {pct:.0f}%")
        return "\n".join(lines)