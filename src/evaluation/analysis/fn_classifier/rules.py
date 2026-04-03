"""
FN Rules - Rule-based classification (Level 1).

Implements classification rules from FN.md spec:
- Rule 1: Variable renaming (token_sim low, ident_overlap high)
- Rule 2: Structural variation (ast_sim medium, token_sim low)
- Rule 3: Dead code insertion (length_ratio > 1.5)
- Rule 4: AI generated (very consistent patterns)
"""
from typing import Dict, List, Any

from src.evaluation_dataset.fn_classifier.taxonomy import FNCategory, label


class RuleEngine:
    """Rule-based classifier for FN pairs."""
    
    def classify(self, features: Dict[str, float], similarity: float) -> List[str]:
        """
        Apply rule-based classification (multi-label).
        
        Args:
            features: Dict with token_similarity, identifier_overlap, etc.
            similarity: Original similarity score
        
        Returns:
            List of category labels (multi-label)
        """
        labels = []
        token_sim = features.get("token_similarity", 0)
        ident_overlap = features.get("identifier_overlap", 0)
        length_ratio = features.get("length_ratio", 1.0)
        
        # Rule 1: Variable renaming
        if token_sim < 0.5 and ident_overlap >= 0.3:
            labels.append(label(FNCategory.LEXICAL, "variable_renaming"))
        
        # Rule 2: Formatting change
        if token_sim >= 0.7 and similarity < 0.5:
            labels.append(label(FNCategory.LEXICAL, "formatting_change"))
        
        # Rule 3: Statement reordering
        if 0.3 <= token_sim < 0.7 and ident_overlap >= 0.2:
            labels.append(label(FNCategory.STRUCTURAL, "statement_reordering"))
        
        # Rule 4: Dead code insertion
        if length_ratio > 1.5:
            labels.append(label(FNCategory.OBFUSCATION, "dead_code_insertion"))
        
        # Rule 5: Semantic variation
        if token_sim < 0.3 and ident_overlap < 0.2 and similarity >= 0.2:
            labels.append(label(FNCategory.SEMANTIC, "algorithm_equivalent"))
        
        # Rule 6: Noise/data error
        if token_sim < 0.1 and ident_overlap < 0.05:
            labels.append(label(FNCategory.NOISE, "data_error"))
        
        # Default fallback
        if not labels:
            labels.append(label(FNCategory.LEXICAL, "variable_renaming"))
        
        return labels