"""
Template / Boilerplate Code Filter.

Eliminates common starter code, framework templates, and standard library patterns
from similarity comparisons. This is the #1 fix for low precision caused by
all students using the same base code provided by instructors.
"""

from __future__ import annotations

from typing import Dict, Any, List, Set, Optional
from collections import Counter
import hashlib

from .deep_analysis import DeepCodeAnalyzer


class BoilerplateFilter:
    """
    Filters out template/boilerplate code from similarity calculations.
    
    Maintains a database of known template patterns, and can subtract these
    patterns from similarity scores. When a matching code block is found
    that exists in the template database, it does not count towards
    plagiarism detection.
    """
    
    def __init__(self):
        self.template_subtrees: Set[str] = set()
        self.template_patterns: Set[str] = set()
        self.template_fingerprints: Set[str] = set()
        self.analyzer = DeepCodeAnalyzer()
        self.enabled = True
        
    def add_template(self, parsed_code: Dict[str, Any]) -> None:
        """
        Add an instructor-provided template/starter code to be filtered out.
        
        Args:
            parsed_code: Parsed AST representation of the template code
        """
        analysis = self.analyzer.analyze(parsed_code)
        
        # Extract all unique subtree hashes from template
        for subtree_hash in analysis.get('subtrees', []):
            self.template_subtrees.add(subtree_hash)
            
        # Extract pattern signatures
        for pattern in analysis.get('patterns', []):
            self.template_patterns.add(pattern['signature'])
            
        # Add structure fingerprint
        if analysis.get('structure_fingerprint'):
            self.template_fingerprints.add(analysis['structure_fingerprint'])
    
    def calculate_boilerplate_ratio(self, parsed_code: Dict[str, Any]) -> float:
        """
        Calculate what percentage of code is template/boilerplate.
        
        Args:
            parsed_code: Parsed code to check
            
        Returns:
            Ratio between 0.0 (no boilerplate) and 1.0 (all boilerplate)
        """
        if not self.enabled:
            return 0.0
            
        analysis = self.analyzer.analyze(parsed_code)
        
        subtrees = set(analysis.get('subtrees', []))
        patterns = set(p['signature'] for p in analysis.get('patterns', []))
        
        if not subtrees and not patterns:
            return 0.0
            
        matching_subtrees = subtrees.intersection(self.template_subtrees)
        matching_patterns = patterns.intersection(self.template_patterns)
        
        subtree_ratio = len(matching_subtrees) / max(len(subtrees), 1)
        pattern_ratio = len(matching_patterns) / max(len(patterns), 1)
        
        return (subtree_ratio * 0.7 + pattern_ratio * 0.3)
    
    def adjust_similarity_score(
        self,
        raw_score: float,
        parsed_a: Dict[str, Any],
        parsed_b: Dict[str, Any]
    ) -> float:
        """
        Adjust similarity score by subtracting boilerplate overlap.
        
        Args:
            raw_score: Original similarity score
            parsed_a: First code submission
            parsed_b: Second code submission
            
        Returns:
            Adjusted score with boilerplate removed
        """
        if not self.enabled:
            return raw_score
            
        bp_ratio_a = self.calculate_boilerplate_ratio(parsed_a)
        bp_ratio_b = self.calculate_boilerplate_ratio(parsed_b)
        
        # The maximum expected overlap from boilerplate is the minimum of the two ratios
        max_boilerplate_overlap = min(bp_ratio_a, bp_ratio_b)
        
        # Discount the score by the boilerplate overlap proportion
        adjusted_score = (raw_score - max_boilerplate_overlap) / (1.0 - max_boilerplate_overlap)
        
        # Ensure we don't go below 0
        return max(adjusted_score, 0.0)
    
    def is_boilerplate_match(
        self,
        matching_subtrees: List[str],
        matching_patterns: List[str]
    ) -> bool:
        """
        Check if a match consists primarily of boilerplate code.
        
        Args:
            matching_subtrees: List of matching subtree hashes
            matching_patterns: List of matching pattern signatures
            
        Returns:
            True if the match is almost entirely boilerplate
        """
        if not self.enabled:
            return False
            
        boilerplate_subtree_count = sum(1 for h in matching_subtrees if h in self.template_subtrees)
        boilerplate_pattern_count = sum(1 for s in matching_patterns if s in self.template_patterns)
        
        subtree_ratio = boilerplate_subtree_count / max(len(matching_subtrees), 1)
        pattern_ratio = boilerplate_pattern_count / max(len(matching_patterns), 1)
        
        # If 85% or more of the match is boilerplate, discard it
        return (subtree_ratio > 0.85) and (pattern_ratio > 0.8)


# Global filter instance
global_boilerplate_filter = BoilerplateFilter()
