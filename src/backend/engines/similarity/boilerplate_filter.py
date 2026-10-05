"""
Template / Boilerplate Code Filter.

Eliminates common starter code, framework templates, and standard library patterns
from similarity comparisons. This is the #1 fix for low precision caused by
all students using the same base code provided by instructors.
"""

from __future__ import annotations

import posixpath
import re
from typing import Any

from .deep_analysis import DeepCodeAnalyzer

#: ``something.config.js`` style tool configuration files.
_CONFIG_NAME_RE = re.compile(r"^[\w.-]+\.config\.(?:js|cjs|mjs|ts|json)$")

#: base-name prefix -> tool, checked in this order.
_TOOL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("tailwind", "tailwind"), ("vite", "vite"), ("webpack", "webpack"), ("babel", "babel"),
    ("tsconfig", "typescript"), ("typescript", "typescript"), ("package", "npm"),
    ("yarn", "npm"), ("eslint", "eslint"), (".eslint", "eslint"), ("prettier", "prettier"),
    (".prettier", "prettier"), ("jest", "jest"), ("next", "nextjs"), ("nuxt", "nuxt"),
    ("vue", "vue"), ("angular", "angular"), ("svelte", "svelte"), ("rollup", "rollup"),
    ("snowpack", "snowpack"), ("parcel", "parcel"), (".parcel", "parcel"), ("gulp", "gulp"),
    ("grunt", "grunt"), ("docker", "docker"), ("readme", "readme"), ("license", "license"),
    ("changelog", "changelog"), ("contributing", "contributing"), (".git", "git"),
)  # fmt: skip


class BoilerplateFilter:
    """
    Filters out template/boilerplate code from similarity calculations.

    Maintains a database of known template patterns, and can subtract these
    patterns from similarity scores. When a matching code block is found
    that exists in the template database, it does not count towards
    plagiarism detection.
    """

    def __init__(self):
        self.template_subtrees: set[str] = set()
        self.template_patterns: set[str] = set()
        self.template_fingerprints: set[str] = set()
        self.analyzer = DeepCodeAnalyzer()
        self.enabled = True

        # Semantic file-type filtering to prevent inappropriate comparisons
        self.config_file_types = {
            "tailwind.config.js",
            "tailwind.config.ts",
            "tailwind.config.mjs",
            "vite.config.js",
            "vite.config.ts",
            "vite.config.mjs",
            "webpack.config.js",
            "webpack.config.ts",
            "babel.config.js",
            "babel.config.json",
            "tsconfig.json",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            ".eslintrc.js",
            ".eslintrc.json",
            ".prettierrc",
            "jest.config.js",
            "jest.config.ts",
            "next.config.js",
            "next.config.ts",
            "nuxt.config.js",
            "nuxt.config.ts",
            "vue.config.js",
            "angular.json",
            "svelte.config.js",
            "rollup.config.js",
            "snowpack.config.js",
            "parcelrc",
            ".parcelrc",
            "gulpfile.js",
            "gruntfile.js",
            "dockerfile",
            "docker-compose.yml",
            ".gitignore",
            ".gitattributes",
            "readme.md",
            "readme.txt",
            "license",
            "license.md",
            "license.txt",
            "changelog.md",
            "contributing.md",
        }

    def add_template(self, parsed_code: dict[str, Any]) -> None:
        """
        Add an instructor-provided template/starter code to be filtered out.

        Args:
            parsed_code: Parsed AST representation of the template code
        """
        analysis = self.analyzer.analyze(parsed_code)

        # Extract all unique subtree hashes from template
        for subtree_hash in analysis.get("subtrees", []):
            self.template_subtrees.add(subtree_hash)

        # Extract pattern signatures
        for pattern in analysis.get("patterns", []):
            self.template_patterns.add(pattern["signature"])

        # Add structure fingerprint
        if analysis.get("structure_fingerprint"):
            self.template_fingerprints.add(analysis["structure_fingerprint"])

    # ── template state ─────────────────────────────────────────────

    def clear_templates(self) -> None:
        """Forget every registered template."""
        self.template_subtrees.clear()
        self.template_patterns.clear()
        self.template_fingerprints.clear()

    def copy(self) -> BoilerplateFilter:
        """An independent filter with the same templates.

        ``global_boilerplate_filter`` is one object for the whole process, so a
        template added for one course/job silently discounted similarity in every
        other. Pipelines that serve more than one tenant should use a per-job copy.
        """
        clone = BoilerplateFilter()
        clone.enabled = self.enabled
        clone.config_file_types = set(self.config_file_types)
        clone.template_subtrees = set(self.template_subtrees)
        clone.template_patterns = set(self.template_patterns)
        clone.template_fingerprints = set(self.template_fingerprints)
        return clone

    @staticmethod
    def _basename(filename: str) -> str:
        return posixpath.basename(str(filename).replace("\\", "/")).lower()

    def _is_config_file(self, filename: str) -> bool:
        """True for tool configuration files, matched on the base name.

        The test was a SUBSTRING match, so a student's ``license_plate.py`` or
        ``package_tracker.py`` counted as configuration files (and two of them for
        "different tools" were then never compared).
        """
        base = self._basename(filename)
        return base in self.config_file_types or bool(_CONFIG_NAME_RE.match(base))

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

        # Skip comparison if both files are config/tool-specific files
        # but serve different purposes
        if self._is_config_file(filename_a) and self._is_config_file(filename_b):
            a_tool = self._extract_tool_name(filename_a)
            b_tool = self._extract_tool_name(filename_b)

            # If they're for different tools, skip comparison
            if a_tool and b_tool and a_tool != b_tool:
                return True

        return False

    def _extract_tool_name(self, filename: str) -> str | None:
        """
        Extract the tool/framework name from a config filename.

        Examples:
        - 'tailwind.config.js' -> 'tailwind'
        - 'vite.config.ts' -> 'vite'
        - 'webpack.config.js' -> 'webpack'
        - 'package.json' -> 'npm'

        Matched on the base name (``"next" in filename`` used to turn any path containing
        "next", such as ``next_prime.py``, into the Next.js config).
        """
        base = self._basename(filename)
        for prefix, tool in _TOOL_PREFIXES:
            # the prefix, optional letters (``dockerfile``, ``.eslintrc``), then ``.``/``-``/end
            if re.match(rf"{re.escape(prefix)}[a-z]*(?:[.\-]|$)", base):
                return tool
        return None

    def calculate_boilerplate_ratio(self, parsed_code: dict[str, Any]) -> float:
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

        subtrees = set(analysis.get("subtrees", []))
        patterns = {p["signature"] for p in analysis.get("patterns", [])}

        if not subtrees and not patterns:
            return 0.0

        matching_subtrees = subtrees.intersection(self.template_subtrees)
        matching_patterns = patterns.intersection(self.template_patterns)

        subtree_ratio = len(matching_subtrees) / max(len(subtrees), 1)
        pattern_ratio = len(matching_patterns) / max(len(patterns), 1)

        return subtree_ratio * 0.7 + pattern_ratio * 0.3

    def adjust_similarity_score(
        self, raw_score: float, parsed_a: dict[str, Any], parsed_b: dict[str, Any]
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

        if max_boilerplate_overlap >= 1.0:
            # Both submissions ARE the template: there is nothing left to compare
            # (this was a ZeroDivisionError).
            return 0.0

        # Discount the score by the boilerplate overlap proportion
        adjusted_score = (raw_score - max_boilerplate_overlap) / (
            1.0 - max_boilerplate_overlap
        )

        # Keep the result a valid score
        return max(0.0, min(1.0, adjusted_score))

    def is_boilerplate_match(
        self, matching_subtrees: list[str], matching_patterns: list[str]
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

        boilerplate_subtree_count = sum(
            1 for h in matching_subtrees if h in self.template_subtrees
        )
        boilerplate_pattern_count = sum(
            1 for s in matching_patterns if s in self.template_patterns
        )

        subtree_ratio = boilerplate_subtree_count / max(len(matching_subtrees), 1)
        pattern_ratio = boilerplate_pattern_count / max(len(matching_patterns), 1)

        # If 85% or more of the match is boilerplate, discard it
        return (subtree_ratio > 0.85) and (pattern_ratio > 0.8)


# Global filter instance
global_boilerplate_filter = BoilerplateFilter()
