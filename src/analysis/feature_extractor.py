"""
Feature Extractor - Standalone feature extraction for FN classification.

Extracts features from code pairs for ML classifier training and rule-based classification.

Features:
- token_similarity: Jaccard similarity of tokens
- length_ratio: ratio of longer to shorter code
- line_count_ratio: ratio of line counts
- identifier_overlap: overlap of identifiers excluding keywords
"""
import re
from typing import Dict


class FeatureExtractor:
    """Extract features from code pair for ML classification."""
    
    @staticmethod
    def extract(code1: str, code2: str) -> Dict[str, float]:
        """Extract features from two code snippets."""
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