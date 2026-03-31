"""
FN Classifier - Rule-based multi-label classification following FN.md spec.

Pipeline: FN pairs -> Feature Extraction -> Rule-based Classification -> Structured output

Features:
- token_similarity: lexical overlap
- ast_similarity: structural similarity
- length_ratio: code length ratio
- identifier_overlap: shared identifiers
"""
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import re
import math

from src.analysis.fn_classifier.taxonomy import (
    FNCategory, FNResult, FNAnalysis, SUBCATEGORIES, label
)


class FeatureExtractor:
    """Extract features from code pair for FN classification."""
    
    @staticmethod
    def extract(code1: str, code2: str) -> Dict[str, float]:
        """
        Extract features from two code snippets.
        
        Returns dict with:
        - token_similarity (0-1)
        - length_ratio (>=1.0)
        - identifier_overlap (0-1)
        - line_count_ratio (>=1.0)
        """
        features = {}
        
        # Tokenize
        tokens1 = set(re.findall(r'\b\w+\b', code1))
        tokens2 = set(re.findall(r'\b\w+\b', code2))
        
        # Token similarity (Jaccard)
        if tokens1 or tokens2:
            features["token_similarity"] = len(tokens1 & tokens2) / max(len(tokens1 | tokens2), 1)
        else:
            features["token_similarity"] = 0.0
        
        # Length ratio
        len1, len2 = len(code1), len(code2)
        longer = max(len1, len2)
        shorter = max(min(len1, len2), 1)
        features["length_ratio"] = longer / shorter
        
        # Line counts
        lines1 = max(code1.count('\n') + 1, 1)
        lines2 = max(code2.count('\n') + 1, 1)
        features["line_count_ratio"] = max(lines1, lines2) / max(min(lines1, lines2), 1)
        
        # Identifier overlap (excluding keywords)
        keywords = {'if', 'else', 'for', 'while', 'return', 'def', 'class', 'import',
                    'from', 'try', 'except', 'finally', 'with', 'as', 'in', 'not', 'and', 'or'}
        ident1 = tokens1 - keywords
        ident2 = tokens2 - keywords
        if ident1 or ident2:
            features["identifier_overlap"] = len(ident1 & ident2) / max(len(ident1 | ident2), 1)
        else:
            features["identifier_overlap"] = 0.0
        
        return features


class FNClassifier:
    """
    Rule-based FN classifier following FN.md spec.
    
    Multi-label: a single FN can have multiple categories.
    
    Rules:
    1. variable_renaming: token_sim low, ident_overlap high
    2. structural_variation: ast_sim medium, token_sim low
    3. dead_code_insertion: length_ratio > 1.5
    4. ai_generated: very consistent patterns
    """
    
    def __init__(self):
        self.feature_extractor = FeatureExtractor()
    
    def classify(self, fn_pairs: List[Dict[str, Any]]) -> FNAnalysis:
        """
        Classify a list of FN pairs.
        
        Args:
            fn_pairs: List of {"file1", "file2", "similarity", "code1", "code2"}
        
        Returns:
            FNAnalysis with multi-label classifications
        """
        results = []
        cat_counts = {}
        
        for fn in fn_pairs:
            code1 = fn.get("code1", "")
            code2 = fn.get("code2", "")
            sim = fn.get("similarity", 0)
            
            # Extract features
            features = self.feature_extractor.extract(code1, code2)
            
            # Classify (multi-label)
            labels = self._apply_rules(features, sim)
            
            result = FNResult(
                file1=fn.get("file1", ""),
                file2=fn.get("file2", ""),
                similarity=sim,
                labels=labels,
                features=features,
                confidence=self._confidence(labels),
            )
            results.append(result)
            
            for lbl in labels:
                cat_counts[lbl] = cat_counts.get(lbl, 0) + 1
        
        # Compute distribution
        total = max(len(results), 1)
        distribution = {cat: count / total * 100 for cat, count in cat_counts.items()}
        
        return FNAnalysis(
            total_fn=len(results),
            by_category=cat_counts,
            results=results,
            distribution=distribution,
        )
    
    def _apply_rules(self, features: Dict[str, float], sim: float) -> List[str]:
        """
        Apply rule-based classification (multi-label).
        
        Rules from FN.md:
        1. variable_renaming: token_sim low AND ident_overlap high
        2. structural_variation: token_sim medium-low
        3. dead_code_insertion: length_ratio > 1.5
        4. formatting_change: very high similarity with slight differences
        """
        labels = []
        token_sim = features.get("token_similarity", 0)
        ident_overlap = features.get("identifier_overlap", 0)
        length_ratio = features.get("length_ratio", 1.0)
        
        # Rule 1: Variable renaming
        # Low token similarity but high identifier overlap suggests renaming
        if token_sim < 0.5 and ident_overlap >= 0.3:
            labels.append(label(FNCategory.LEXICAL, "variable_renaming"))
        
        # Rule 2: Formatting/comment change
        # High similarity but just below threshold
        if token_sim >= 0.7 and sim < 0.5:
            labels.append(label(FNCategory.LEXICAL, "formatting_change"))
        
        # Rule 3: Structural variation (statement reordering, loop transformation)
        # Medium token similarity with moderate identifier overlap
        if 0.3 <= token_sim < 0.7 and ident_overlap >= 0.2:
            labels.append(label(FNCategory.STRUCTURAL, "statement_reordering"))
        
        # Rule 4: Dead code insertion (obfuscation)
        # Significant length difference
        if length_ratio > 1.5:
            labels.append(label(FNCategory.OBFUSCATION, "dead_code_insertion"))
        
        # Rule 5: Semantic variation (algorithm equivalent, logic rewrite)
        # Low token similarity AND low identifier overlap but some structural similarity
        if token_sim < 0.3 and ident_overlap < 0.2 and sim >= 0.2:
            labels.append(label(FNCategory.SEMANTIC, "algorithm_equivalent"))
        
        # Rule 6: Noise/data error
        # Very low similarity - might be a false positive in truth data
        if token_sim < 0.1 and ident_overlap < 0.05:
            labels.append(label(FNCategory.NOISE, "data_error"))
        
        # If no rules matched, default to lexical_variation
        if not labels:
            labels.append(label(FNCategory.LEXICAL, "variable_renaming"))
        
        return labels
    
    def _confidence(self, labels: List[str]) -> float:
        """Estimate confidence based on number of matching rules."""
        if len(labels) >= 3:
            return 0.9  # Strong multi-label match
        elif len(labels) == 2:
            return 0.75
        elif len(labels) == 1:
            return 0.6
        return 0.3
    
    def build_training_data(self, analysis: FNAnalysis) -> List[Dict[str, Any]]:
        """
        Convert classified FN analysis to training data format.
        
        FNs become positive samples (label=1) for targeted training.
        """
        training_data = []
        for r in analysis.results:
            entry = {
                "file1": r.file1,
                "file2": r.file2,
                "label": 1,  # FN = should have been detected
                "categories": r.labels,
                "features": r.features,
                "similarity_at_detection": r.similarity,
            }
            training_data.append(entry)
        return training_data