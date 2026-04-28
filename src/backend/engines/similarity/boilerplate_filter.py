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

        # Semantic file-type filtering to prevent inappropriate comparisons
        self.config_file_types = {
            'tailwind.config.js', 'tailwind.config.ts', 'tailwind.config.mjs',
            'vite.config.js', 'vite.config.ts', 'vite.config.mjs',
            'webpack.config.js', 'webpack.config.ts',
            'babel.config.js', 'babel.config.json',
            'tsconfig.json', 'package.json', 'package-lock.json', 'yarn.lock',
            '.eslintrc.js', '.eslintrc.json', '.prettierrc',
            'jest.config.js', 'jest.config.ts',
            'next.config.js', 'next.config.ts',
            'nuxt.config.js', 'nuxt.config.ts',
            'vue.config.js',
            'angular.json',
            'svelte.config.js',
            'rollup.config.js',
            'snowpack.config.js',
            'parcelrc', '.parcelrc',
            'gulpfile.js', 'gruntfile.js',
            'dockerfile', 'docker-compose.yml',
            '.gitignore', '.gitattributes',
            'readme.md', 'readme.txt',
            'license', 'license.md', 'license.txt',
            'changelog.md', 'contributing.md'
        }
        
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

    def should_skip_comparison(self, filename_a: str, filename_b: str) -> bool:
        """
        Check if two files should be skipped from plagiarism comparison
        due to semantic incompatibility.

        Args:
            filename_a: Name of first file
            filename_b: Name of second file

        Returns:
            True if comparison should be skipped
        """
        if not self.enabled:
            return False

        name_a = filename_a.lower()
        name_b = filename_b.lower()

        # Skip comparison if both files are config/tool-specific files
        # but serve different purposes
        a_is_config = any(config_type in name_a for config_type in self.config_file_types)
        b_is_config = any(config_type in name_b for config_type in self.config_file_types)

        if a_is_config and b_is_config:
            # Extract the tool/framework name from filename
            a_tool = self._extract_tool_name(name_a)
            b_tool = self._extract_tool_name(name_b)

            # If they're for different tools, skip comparison
            if a_tool and b_tool and a_tool != b_tool:
                return True

        return False

    def _extract_tool_name(self, filename: str) -> str:
        """
        Extract the tool/framework name from a config filename.

        Examples:
        - 'tailwind.config.js' -> 'tailwind'
        - 'vite.config.ts' -> 'vite'
        - 'webpack.config.js' -> 'webpack'
        - 'package.json' -> 'npm'
        """
        filename = filename.lower()

        # Direct mappings for common config files
        if 'tailwind' in filename:
            return 'tailwind'
        elif 'vite' in filename:
            return 'vite'
        elif 'webpack' in filename:
            return 'webpack'
        elif 'babel' in filename:
            return 'babel'
        elif 'typescript' in filename or 'tsconfig' in filename:
            return 'typescript'
        elif 'package' in filename:
            return 'npm'
        elif 'eslint' in filename:
            return 'eslint'
        elif 'prettier' in filename:
            return 'prettier'
        elif 'jest' in filename:
            return 'jest'
        elif 'next' in filename:
            return 'nextjs'
        elif 'nuxt' in filename:
            return 'nuxt'
        elif 'vue' in filename:
            return 'vue'
        elif 'angular' in filename:
            return 'angular'
        elif 'svelte' in filename:
            return 'svelte'
        elif 'rollup' in filename:
            return 'rollup'
        elif 'snowpack' in filename:
            return 'snowpack'
        elif 'parcel' in filename:
            return 'parcel'
        elif 'gulp' in filename:
            return 'gulp'
        elif 'grunt' in filename:
            return 'grunt'
        elif 'docker' in filename:
            return 'docker'
        elif 'readme' in filename:
            return 'readme'
        elif 'license' in filename:
            return 'license'
        elif 'changelog' in filename:
            return 'changelog'
        elif 'contributing' in filename:
            return 'contributing'
        elif 'gitignore' in filename:
            return 'git'
        elif 'gitattributes' in filename:
            return 'git'

        return None
    
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
