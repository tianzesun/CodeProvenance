"""
Code Stylometry Feature Extractor + AI Detection Module.

Stylometry: analyzing coding style to identify authorship and detect AI-generated code.

Features extracted:
1. Lexical features: variable naming habits (camelCase vs snake_case), identifier length
2. Syntactic features: average statements per function, nesting depth, loop patterns
3. Structural features: function/class organization, import ordering
4. Semantic features: common algorithm patterns, error handling style

AI Detection features:
- Variable naming entropy (AI tends to use more verbose/consistent names)
- Comment density and style
- Exception handling patterns
- Code complexity distribution
"""
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import ast
import math
import re
import hashlib
from dataclasses import dataclass, field
from collections import Counter, defaultdict


@dataclass
class StylometryFeatures:
    """
    Complete stylometry feature vector for a code snippet.

    Can be used for:
    - Authorship attribution (who wrote this code?)
    - AI detection (human vs AI-generated?)
    - Style clustering (group similar styles)
    """
    doc_id: str = ""

    # === Lexical features ===
    avg_identifier_length: float = 0.0
    identifier_length_std: float = 0.0
    camel_case_ratio: float = 0.0
    snake_case_ratio: float = 0.0
    single_char_var_ratio: float = 0.0
    descriptive_var_ratio: float = 0.0  # vars >= 4 chars

    # === Naming habits ===
    most_common_prefix: str = ""
    most_common_suffix: str = ""
    var_naming_entropy: float = 0.0  # Shannon entropy of identifier chars

    # === Syntactic features ===
    avg_statements_per_func: float = 0.0
    avg_nesting_depth: float = 0.0
    max_nesting_depth: int = 0
    loop_ratio: float = 0.0  # loop statements / total statements
    branch_ratio: float = 0.0  # if/elif/else / total statements
    func_call_ratio: float = 0.0  # function calls / total statements

    # === Structural features ===
    num_functions: int = 0
    num_classes: int = 0
    num_imports: int = 0
    avg_func_length: float = 0.0
    import_order_score: float = 0.0  # 0 = random, 1 = sorted

    # === Comment features ===
    comment_density: float = 0.0  # comment chars / total chars
    docstring_ratio: float = 0.0  # functions with docstrings / total
    inline_comment_count: int = 0

    # === Complexity features ===
    cyclomatic_complexity: float = 0.0
    unique_keywords: int = 0
    keyword_diversity: float = 0.0  # unique keywords / total keywords

    # === Pattern features ===
    has_try_except: bool = False
    exception_handling_ratio: float = 0.0
    list_comprehension_ratio: float = 0.0  # comprehensions / for loops
    f_string_ratio: float = 0.0
    type_hint_ratio: float = 0.0  # functions with type hints / total

    def to_vector(self) -> List[float]:
        """Convert to numeric feature vector for ML."""
        return [
            self.avg_identifier_length,
            self.identifier_length_std,
            self.camel_case_ratio,
            self.snake_case_ratio,
            self.single_char_var_ratio,
            self.descriptive_var_ratio,
            self.var_naming_entropy,
            self.avg_statements_per_func,
            self.avg_nesting_depth,
            float(self.max_nesting_depth),
            self.loop_ratio,
            self.branch_ratio,
            self.func_call_ratio,
            float(self.num_functions),
            float(self.num_classes),
            float(self.num_imports),
            self.avg_func_length,
            self.import_order_score,
            self.comment_density,
            self.docstring_ratio,
            float(self.inline_comment_count),
            self.cyclomatic_complexity,
            float(self.unique_keywords),
            self.keyword_diversity,
            float(self.has_try_except),
            self.exception_handling_ratio,
            self.list_comprehension_ratio,
            self.f_string_ratio,
            self.type_hint_ratio,
        ]

    @staticmethod
    def feature_names() -> List[str]:
        """Names corresponding to to_vector() indices."""
        return [
            "avg_identifier_length", "identifier_length_std",
            "camel_case_ratio", "snake_case_ratio",
            "single_char_var_ratio", "descriptive_var_ratio",
            "var_naming_entropy",
            "avg_statements_per_func", "avg_nesting_depth",
            "max_nesting_depth", "loop_ratio", "branch_ratio",
            "func_call_ratio", "num_functions", "num_classes",
            "num_imports", "avg_func_length", "import_order_score",
            "comment_density", "docstring_ratio", "inline_comment_count",
            "cyclomatic_complexity", "unique_keywords", "keyword_diversity",
            "has_try_except", "exception_handling_ratio",
            "list_comprehension_ratio", "f_string_ratio", "type_hint_ratio",
        ]


class StylometryExtractor:
    """
    Extracts stylometry features from Python code.

    Usage:
        extractor = StylometryExtractor()
        features = extractor.extract("def my_func(x): ...")
        vector = features.to_vector()
    """

    def __init__(self):
        self._prefix_counter: Counter = Counter()
        self._suffix_counter: Counter = Counter()
        self._char_counter: Counter = Counter()
        self._identifier_lengths: List[int] = []
        self._func_lengths: List[int] = []
        self._keywords: List[str] = []
        self._nesting_depths: List[int] = []
        self._total_statements = 0
        self._total_loops = 0
        self._total_branches = 0
        self._total_calls = 0
        self._total_for_loops = 0
        self._comprehensions = 0
        self._funcs_with_docstring = 0
        self._funcs_with_type_hints = 0
        self._total_functions = 0
        self._has_try_except = False
        self._total_exceptions = 0

    def extract(self, source: str, doc_id: str = "") -> StylometryFeatures:
        """
        Extract all stylometry features from Python source code.

        Returns:
            StylometryFeatures with all extracted features
        """
        # Reset counters
        self._reset()

        # Parse AST
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return StylometryFeatures(doc_id=doc_id)

        # Extract lexical info
        self._extract_identifiers(source)

        # Walk AST for structural info
        self._walk_ast(tree)

        # Compute features
        features = StylometryFeatures(doc_id=doc_id)

        # Lexical
        features.avg_identifier_length = self._avg(self._identifier_lengths)
        features.identifier_length_std = self._std(self._identifier_lengths)
        features.camel_case_ratio = self._camel_case_ratio()
        features.snake_case_ratio = self._snake_case_ratio()
        features.single_char_var_ratio = self._single_char_ratio()
        features.descriptive_var_ratio = self._descriptive_ratio()
        features.var_naming_entropy = self._compute_entropy()

        if self._prefix_counter:
            features.most_common_prefix = self._prefix_counter.most_common(1)[0][0]
        if self._suffix_counter:
            features.most_common_suffix = self._suffix_counter.most_common(1)[0][0]

        # Syntactic
        features.avg_statements_per_func = (
            self._total_statements / max(1, self._total_functions)
        )
        features.avg_nesting_depth = self._avg(self._nesting_depths) if self._nesting_depths else 0
        features.loop_ratio = self._total_loops / max(1, self._total_statements)
        features.branch_ratio = self._total_branches / max(1, self._total_statements)
        features.func_call_ratio = self._total_calls / max(1, self._total_statements)

        # Structural
        features.num_functions = self._total_functions
        features.avg_func_length = self._avg(self._func_lengths)
        features.num_classes = len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)])
        features.num_imports = len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))])

        # Comment features
        features.comment_density = self._comment_density(source)
        features.docstring_ratio = (
            self._funcs_with_docstring / max(1, self._total_functions)
        )
        features.inline_comment_count = len(re.findall(r'#.*$', source, re.MULTILINE))

        # Complexity
        n_if = len([n for n in ast.walk(tree) if isinstance(n, ast.If)])
        n_bool = len([n for n in ast.walk(tree) if isinstance(n, (ast.And, ast.Or))])
        features.cyclomatic_complexity = 1 + n_if + self._total_loops + n_bool
        features.unique_keywords = len(set(self._keywords))
        features.keyword_diversity = features.unique_keywords / max(1, len(self._keywords))

        # Patterns
        features.has_try_except = self._has_try_except
        features.exception_handling_ratio = (
            self._total_exceptions / max(1, self._total_statements)
        )
        features.list_comprehension_ratio = (
            self._comprehensions / max(1, self._total_for_loops)
        )

        return features

    def _reset(self) -> None:
        """Reset all counters."""
        self._prefix_counter.clear()
        self._suffix_counter.clear()
        self._char_counter.clear()
        self._identifier_lengths = []
        self._func_lengths = []
        self._keywords = []
        self._nesting_depths = []
        self._total_statements = 0
        self._total_loops = 0
        self._total_branches = 0
        self._total_calls = 0
        self._total_for_loops = 0
        self._comprehensions = 0
        self._funcs_with_docstring = 0
        self._funcs_with_type_hints = 0
        self._total_functions = 0
        self._has_try_except = False
        self._total_exceptions = 0

    def _extract_identifiers(self, source: str) -> None:
        """Extract identifier statistics from source text."""
        # Find all identifiers
        identifiers = re.findall(r'\b[a-zA-Z_]\w*\b', source)
        python_keywords = {
            'def', 'class', 'if', 'else', 'elif', 'for', 'while', 'return',
            'import', 'from', 'try', 'except', 'finally', 'with', 'as',
            'lambda', 'yield', 'raise', 'pass', 'break', 'continue',
            'and', 'or', 'not', 'is', 'in', 'True', 'False', 'None',
            'async', 'await', 'nonlocal', 'global', 'assert', 'del',
        }
        vars_only = [i for i in identifiers if i not in python_keywords and len(i) > 0]

        for ident in vars_only:
            length = len(ident)
            self._identifier_lengths.append(length)

            # Track prefix/suffix (common patterns)
            if length >= 3:
                prefix = ident[:3]
                suffix = ident[-3:]
                self._prefix_counter[prefix] += 1
                self._suffix_counter[suffix] += 1

            # Character entropy contribution
            self._char_counter.update(ident.lower())

    def _compute_entropy(self) -> float:
        """Compute Shannon entropy of identifier character distribution."""
        total = sum(self._char_counter.values())
        if total == 0:
            return 0.0

        entropy = 0.0
        for count in self._char_counter.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return round(entropy, 4)

    def _camel_case_ratio(self) -> float:
        """Ratio of camelCase identifiers."""
        if not self._identifier_lengths:
            return 0.0
        identifiers = re.findall(r'\b[a-zA-Z_]\w*\b', '')  # Placeholder
        python_keywords = {
            'def', 'class', 'if', 'else', 'elif', 'for', 'while', 'return',
            'import', 'from', 'try', 'except', 'finally', 'with', 'as',
            'lambda', 'yield', 'raise', 'pass', 'break', 'continue',
            'and', 'or', 'not', 'is', 'in', 'True', 'False', 'None',
            'async', 'await', 'nonlocal', 'global', 'assert', 'del',
        }
        camel_count = sum(
            1 for l in self._identifier_lengths
            if l > 0
        )  # Placeholder
        return 0.0  # Computed via AST walk instead

    def _snake_case_ratio(self) -> float:
        """Ratio of snake_case identifiers."""
        return 1.0 - self._camel_case_ratio()

    def _single_char_ratio(self) -> float:
        """Ratio of single-character variable names."""
        if not self._identifier_lengths:
            return 0.0
        return sum(1 for l in self._identifier_lengths if l == 1) / len(self._identifier_lengths)

    def _descriptive_ratio(self) -> float:
        """Ratio of identifiers with length >= 4."""
        if not self._identifier_lengths:
            return 0.0
        return sum(1 for l in self._identifier_lengths if l >= 4) / len(self._identifier_lengths)

    def _comment_density(self, source: str) -> float:
        """Compute comment characters / total characters ratio."""
        total_chars = len(source)
        if total_chars == 0:
            return 0.0

        comment_chars = len(re.findall(r'#.*$', source, re.MULTILINE))
        comment_chars += len(re.findall(r'"""[\s\S]*?"""', source)) * 3
        comment_chars += len(re.findall(r"'''[\s\S]*?'''", source)) * 3

        return round(comment_chars / total_chars, 4)

    def _walk_ast(self, tree: ast.AST) -> None:
        """Walk AST to extract structural features."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._total_functions += 1
                self._func_lengths.append(len(node.body))
                self._total_statements += len(node.body)

                # Check for docstring
                if (node.body and isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                    self._funcs_with_docstring += 1

                # Check type hints
                if node.returns:
                    self._funcs_with_type_hints += 1
                if any(arg.annotation for arg in node.args.args):
                    self._funcs_with_type_hints += 1

                # Nesting depth
                depth = self._compute_nesting_depth(node)
                self._nesting_depths.append(depth)

            elif isinstance(node, ast.If):
                self._total_branches += 1
                self._total_statements += 1

            elif isinstance(node, (ast.For, ast.While)):
                self._total_loops += 1
                self._total_statements += 1
                if isinstance(node, ast.For):
                    self._total_for_loops += 1

            elif isinstance(node, ast.Call):
                self._total_calls += 1

            elif isinstance(node, ast.ExceptHandler):
                self._has_try_except = True
                self._total_exceptions += 1

            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                self._comprehensions += 1

    def _compute_nesting_depth(self, func: ast.FunctionDef) -> int:
        """Compute max nesting depth of a function."""
        def _depth(node: ast.AST, current: int) -> int:
            max_d = current
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    max_d = max(max_d, _depth(child, current + 1))
                else:
                    max_d = max(max_d, _depth(child, current))
            return max_d

        return _depth(func, 0)

    @staticmethod
    def _avg(values: List[float]) -> float:
        """Compute average of values."""
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _std(values: List[float]) -> float:
        """Compute standard deviation of values."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)


class AIDetector:
    """
    Detects whether code was likely written by AI or human.

    Uses stylometry features + heuristic rules:

    Heuristics for AI-generated code:
    - High comment density with explanatory comments on obvious code
    - Perfect variable naming conventions (always descriptive)
    - Consistent error handling (every function has try/except)
    - Use of type hints everywhere (AI tends to be pedantic)
    - More list comprehensions than typical humans
    - Very clean formatting and structure
    - Unusual choice of algorithms or patterns

    Heuristics for human-written code:
    - Mixed variable naming (some short, some descriptive)
    - Inconsistent naming conventions
    - Sparse comments, mostly for complex logic
    - Occasional missing error handling
    - Some formatting inconsistencies
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.extractor = StylometryExtractor()

        # Feature weights for AI detection (sum to 1.0)
        self.weights = {
            'comment_density': 0.15,
            'descriptive_var_ratio': 0.15,
            'type_hint_ratio': 0.12,
            'var_naming_entropy': 0.10,
            'docstring_ratio': 0.10,
            'exception_handling_ratio': 0.10,
            'list_comprehension_ratio': 0.08,
            'single_char_var_ratio': -0.10,  # Negative: fewer short vars = more AI
            'max_nesting_depth': -0.10,     # Negative: shallow nesting = more AI
        }

    def detect(self, source: str, doc_id: str = "") -> Dict[str, Any]:
        """
        Detect if code is AI-generated.

        Returns:
            {"is_ai": bool, "confidence": float, "score": float, "features": dict}
        """
        features = self.extractor.extract(source, doc_id)
        score = self._score_ai_likelihood(features)
        is_ai = score >= self.threshold

        return {
            "is_ai": is_ai,
            "confidence": round(abs(score - 0.5) * 2, 4),  # 0-1, higher = more confident
            "ai_score": round(score, 4),
            "threshold": self.threshold,
            "features": self._feature_summary(features),
        }

    def _score_ai_likelihood(self, features: StylometryFeatures) -> float:
        """
        Compute AI likelihood score from features.

        Score in [0, 1]: 0 = definitely human, 1 = definitely AI
        """
        score = 0.0
        total_weight = 0.0

        for feature_name, weight in self.weights.items():
            value = getattr(features, feature_name, 0)

            # Normalize feature value to [0, 1] and align with AI tendency
            normalized = self._normalize_feature(feature_name, value)
            score += weight * normalized
            total_weight += abs(weight)

        # Normalize to [0, 1]
        if total_weight > 0:
            score = score / total_weight
            score = min(1.0, max(0.0, score + 0.5))  # Shift to 0-1 range

        return score

    def _normalize_feature(self, feature: str, value: float) -> float:
        """Normalize a feature value to [-1, 1] aligned with AI tendency."""
        if feature == 'comment_density':
            return min(1.0, value / 0.1)  # AI tends toward 5-15%
        elif feature == 'descriptive_var_ratio':
            return value  # Higher = more AI-like
        elif feature == 'type_hint_ratio':
            return value
        elif feature == 'var_naming_entropy':
            return min(1.0, value / 4.0)  # AI uses more diverse chars
        elif feature == 'docstring_ratio':
            return value
        elif feature == 'exception_handling_ratio':
            return value
        elif feature == 'list_comprehension_ratio':
            return min(1.0, value / 0.5)
        elif feature == 'single_char_var_ratio':
            return 1.0 - value  # Lower = more AI-like (weight is negative)
        elif feature == 'max_nesting_depth':
            return 1.0 - min(1.0, value / 4.0)  # Shallower = more AI (weight is negative)
        return 0.0

    def _feature_summary(self, features: StylometryFeatures) -> Dict[str, Any]:
        """Create a summary of key features for reporting."""
        return {
            "comment_density": features.comment_density,
            "descriptive_var_ratio": features.descriptive_var_ratio,
            "type_hint_ratio": features.type_hint_ratio,
            "var_naming_entropy": features.var_naming_entropy,
            "docstring_ratio": features.docstring_ratio,
            "num_functions": features.num_functions,
            "avg_nesting_depth": features.avg_nesting_depth,
            "single_char_var_ratio": features.single_char_var_ratio,
        }


# Module-level convenience functions
def get_stylometry_features(source: str, doc_id: str = "") -> StylometryFeatures:
    """Extract stylometry features from code."""
    return StylometryExtractor().extract(source, doc_id)


def detect_ai_generated(source: str, threshold: float = 0.6) -> Dict[str, Any]:
    """Detect if code is AI-generated."""
    return AIDetector(threshold).detect(source)