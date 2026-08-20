"""File Type Classification for Academic Integrity Detection.

This module classifies files into semantic categories to enable
file-type aware similarity detection that prevents false positives
in configuration files, build artifacts, and other non-CODE content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FileType(str, Enum):
    """Classification of file semantic purpose."""

    CODE = "CODE"  # Business logic, functions, algorithms
    CONFIG = "CONFIG"  # Build tools, framework config, env config
    SCRIPT = "SCRIPT"  # Automation, deployment scripts
    DATA = "DATA"  # JSON, YAML, static datasets
    MIXED = "MIXED"  # Unknown / ambiguous


@dataclass
class FileTypeClassification:
    """Result of file type classification."""

    file_type: FileType
    confidence: float  # 0.0-1.0
    domain: str | None = None  # e.g., "tailwind", "react", "next"
    reasons: list[str] = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


# File extension to type mapping
EXTENSION_MAP: dict[str, FileType] = {
    # Config files
    ".json": FileType.CONFIG,
    ".yaml": FileType.CONFIG,
    ".yml": FileType.CONFIG,
    ".toml": FileType.CONFIG,
    ".ini": FileType.CONFIG,
    ".cfg": FileType.CONFIG,
    ".env": FileType.CONFIG,
    ".env.example": FileType.CONFIG,
    ".editorconfig": FileType.CONFIG,
    ".prettierrc": FileType.CONFIG,
    ".eslintrc": FileType.CONFIG,
    ".babelrc": FileType.CONFIG,
    ".postcssrc": FileType.CONFIG,
    ".tailwindrc": FileType.CONFIG,
    ".vite": FileType.CONFIG,  # vite.config.* files
    ".webpack": FileType.CONFIG,
    ".next": FileType.CONFIG,  # next.config.*
    # Package management
    "package.json": FileType.CONFIG,
    "pyproject.toml": FileType.CONFIG,
    "requirements.txt": FileType.CONFIG,
    "Pipfile": FileType.CONFIG,
    "poetry.lock": FileType.CONFIG,
    "Cargo.toml": FileType.CONFIG,
    "go.mod": FileType.CONFIG,
    # Scripts
    ".sh": FileType.SCRIPT,
    ".bash": FileType.SCRIPT,
    ".zsh": FileType.SCRIPT,
    ".fish": FileType.SCRIPT,
    ".ps1": FileType.SCRIPT,
    ".bat": FileType.SCRIPT,
    ".cmd": FileType.SCRIPT,
    # Database
    ".sql": FileType.SCRIPT,  # SQL migration scripts
    # Data files
    ".csv": FileType.DATA,
    ".xml": FileType.DATA,
    ".proto": FileType.DATA,
}

# Domain-specific config file patterns
CONFIG_DOMAIN_PATTERNS: dict[str, set[str]] = {
    "tailwind": {"tailwind.config.js", "tailwind.config.ts"},
    "postcss": {"postcss.config.js", "postcss.config.ts"},
    "babel": {
        "babel.config.js",
        "babel.config.ts",
        ".babelrc",
        ".babelrc.js",
        ".babelrc.json",
    },
    "eslint": {
        "eslint.config.js",
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.json",
        ".eslintrc.yml",
    },
    "prettier": {
        "prettier.config.js",
        ".prettierrc",
        ".prettierrc.js",
        ".prettierrc.json",
        ".prettierrc.yml",
    },
    "vite": {"vite.config.js", "vite.config.ts"},
    "webpack": {"webpack.config.js", "webpack.config.ts", "webpack.config.mjs"},
    "next": {"next.config.js", "next.config.ts"},
    "nuxt": {"nuxt.config.js", "nuxt.config.ts"},
    "angular": {"angular.json", ".angular.json"},
    "docker": {"dockerfile", "docker-compose.yml", "docker-compose.yaml"},
    "kubernetes": {"kubernetes.yml", "kubernetes.yaml", "*.k8s.yml", "*.k8s.yaml"},
    "aws": {"serverless.yml", "serverless.yaml", "cdk.json", "sam.yaml"},
    "github": {"action.yml", "action.yaml", ".github/workflows/*.yml"},
}

# Build tool indicators
BUILD_TOOL_INDICATORS = {
    "webpack": ["webpack", "webpack-cli", "html-webpack-plugin"],
    "vite": ["vite", "vite-plugin-", "vite.config"],
    "rollup": ["rollup", "rollup-plugin-"],
    "parcel": ["parcel", "parcel-bundler"],
    "gulp": ["gulp", "gulpfile"],
    "grunt": ["grunt", "gruntfile"],
}

# Framework config patterns
FRAMEWORK_CONFIG_PATTERNS = {
    "react": ["react", "jsx", "tsx"],
    "vue": ["vue", "vuex", "vue.config"],
    "angular": ["angular", "ng-", "angular.json"],
    "svelte": ["svelte", "svelte.config"],
    "next": ["next", "next.config", "_app.js", "_document.js"],
    "nuxt": ["nuxt", "nuxt.config", "nuxt.config"],
}


class FileTypeClassifier:
    """Classifies files into semantic categories for similarity detection."""

    def __init__(self) -> None:
        self._config_file_names = self._build_config_file_set()

    def _build_config_file_set(self) -> set[str]:
        """Build set of known config file names."""
        config_files = set()
        for patterns in CONFIG_DOMAIN_PATTERNS.values():
            for pattern in patterns:
                config_files.add(pattern.lower())
        return config_files

    def classify(
        self,
        filename: str,
        content: str | None = None,
    ) -> FileTypeClassification:
        """Classify a file into a semantic category.

        Args:
            filename: The file name (with or without path).
            content: Optional file content for deeper analysis.

        Returns:
            FileTypeClassification with type, confidence, and domain.
        """
        # Extract just the filename
        name = self._extract_filename(filename)

        # Check for exact config file matches
        if name.lower() in self._config_file_names:
            domain = self._identify_config_domain(name)
            return FileTypeClassification(
                file_type=FileType.CONFIG,
                confidence=0.95,
                domain=domain,
                reasons=[f"Known config file: {name}"],
            )

        # Check extension-based classification
        ext_type = self._classify_by_extension(name)
        if ext_type is not None:
            if ext_type == FileType.CONFIG:
                domain = self._identify_config_domain(name)
                return FileTypeClassification(
                    file_type=FileType.CONFIG,
                    confidence=0.90,
                    domain=domain,
                    reasons=[f"Config extension: {self._get_extension(name)}"],
                )
            return FileTypeClassification(
                file_type=ext_type,
                confidence=0.85,
                reasons=[f"Extension: {self._get_extension(name)}"],
            )

        # Content-based classification if content provided
        if content:
            return self._classify_by_content(content, name)

        # Default to MIXED for unknown files
        return FileTypeClassification(
            file_type=FileType.MIXED,
            confidence=0.50,
            reasons=["Unknown file type"],
        )

    def _extract_filename(self, path: str) -> str:
        """Extract filename from path."""
        if "/" in path:
            return path.rsplit("/", 1)[-1]
        if "\\" in path:
            return path.rsplit("\\", 1)[-1]
        return path

    def _get_extension(self, filename: str) -> str:
        """Get file extension."""
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1]
        return ""

    def _classify_by_extension(self, filename: str) -> FileType | None:
        """Classify by file extension."""
        ext = self._get_extension(filename)

        # Check exact extension match
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext]

        # Check for config files without standard extensions
        for config_pattern in self._config_file_names:
            if filename.lower() == config_pattern or filename.lower().endswith(
                config_pattern.replace(".", "")
            ):
                return FileType.CONFIG

        return None

    def _identify_config_domain(self, filename: str) -> str | None:
        """Identify the config domain for a config file."""
        name_lower = filename.lower()

        for domain, patterns in CONFIG_DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if name_lower == pattern.lower() or pattern.lower() in name_lower:
                    return domain

        return None

    def _classify_by_content(
        self, content: str, filename: str
    ) -> FileTypeClassification:
        """Classify by analyzing file content."""
        reasons = []

        # Check for JSON/YAML structure
        if self._looks_like_config_json(content):
            return FileTypeClassification(
                file_type=FileType.CONFIG,
                confidence=0.80,
                reasons=["JSON-like config structure"],
            )

        if self._looks_like_config_yaml(content):
            return FileTypeClassification(
                file_type=FileType.CONFIG,
                confidence=0.80,
                reasons=["YAML config structure"],
            )

        # Check for build tool indicators
        for tool, indicators in BUILD_TOOL_INDICATORS.items():
            if any(ind in content.lower() for ind in indicators):
                reasons.append(f"Build tool: {tool}")
                return FileTypeClassification(
                    file_type=FileType.CONFIG,
                    confidence=0.85,
                    domain=tool,
                    reasons=reasons,
                )

        # Check for framework indicators
        for framework, indicators in FRAMEWORK_CONFIG_PATTERNS.items():
            if any(ind in content.lower() for ind in indicators):
                reasons.append(f"Framework: {framework}")
                return FileTypeClassification(
                    file_type=FileType.CONFIG,
                    confidence=0.80,
                    domain=framework,
                    reasons=reasons,
                )

        # Default to CODE for files with code-like content
        if self._looks_like_code(content):
            return FileTypeClassification(
                file_type=FileType.CODE,
                confidence=0.70,
                reasons=["Contains code-like structures"],
            )

        return FileTypeClassification(
            file_type=FileType.MIXED,
            confidence=0.50,
            reasons=["Ambiguous content"],
        )

    def _looks_like_config_json(self, content: str) -> bool:
        """Check if content looks like a JSON config file."""
        content = content.strip()
        if not (content.startswith(("{", "["))):
            return False

        # Common config keys
        config_keys = {
            "name",
            "version",
            "scripts",
            "dependencies",
            "devDependencies",
            "build",
            "dev",
            "start",
            "test",
            "private",
            "main",
            "module",
            "tailwind",
            "content",
            "theme",
            "plugins",
        }

        try:
            import json

            data = json.loads(content)
            if isinstance(data, dict):
                keys = set(data.keys())
                return bool(keys & config_keys)
        except (json.JSONDecodeError, ValueError):
            pass

        return False

    def _looks_like_config_yaml(self, content: str) -> bool:
        """Check if content looks like a YAML config file."""
        lines = content.strip().split("\n")

        # Look for key: value patterns typical of configs
        config_patterns = [
            r"^\s*\w+:\s*.+$",
            r"^\s*-\s*.+$",
        ]

        matches = 0
        for line in lines[:20]:  # Check first 20 lines
            for pattern in config_patterns:
                if re.match(pattern, line):
                    matches += 1
                    break

        return matches >= 3

    def _looks_like_code(self, content: str) -> bool:
        """Check if content looks like source code."""
        code_patterns = [
            r"def\s+\w+\s*\(",  # Python function
            r"function\s+\w+\s*\(",  # JS function
            r"\bclass\s+\w+",  # Class definition
            r"\bimport\s+",  # Import statement
            r"\brequire\s*\(",  # require statement
            r"=>\s*{",  # Arrow function
            r"public\s+\w+\s+\w+\s*\(",  # Method definition
        ]

        for pattern in code_patterns:
            if re.search(pattern, content):
                return True

        return False


# Singleton instance
_classifier: FileTypeClassifier | None = None


def get_file_type_classifier() -> FileTypeClassifier:
    """Get the singleton file type classifier."""
    global _classifier
    if _classifier is None:
        _classifier = FileTypeClassifier()
    return _classifier


def classify_file(filename: str, content: str | None = None) -> FileTypeClassification:
    """Convenience function to classify a file."""
    return get_file_type_classifier().classify(filename, content)
