"""Feature Extractor - Extracts features from code pairs for similarity engines."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, ClassVar

from src.backend.config.settings import settings
from src.backend.engines.ast_multi_layer import compute_ast_layer_scores
from src.backend.engines.file_type_classifier import FileType

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """Similarity scores from each detection engine.

    The extraction layer normalizes missing or failed engines to ``0.0`` so
    the downstream pipeline always receives a stable numeric feature set.
    """

    ast: float = 0.0
    fingerprint: float = 0.0
    embedding: float = 0.0
    ngram: float = 0.0
    winnowing: float = 0.0
    string_tiling: float = 0.0
    graph: float = 0.0
    static_rules: float = 0.0
    sklearn_cosine: float = 0.0
    cfg_similarity: float = 0.0
    dfg_similarity: float = 0.0
    call_graph_similarity: float = 0.0
    input_output_behavior_similarity: float = 0.0
    edge_case_behavior_similarity: float = 0.0
    runtime_bug_similarity: float = 0.0
    identifier_rename_score: float = 0.0
    boilerplate_overlap: float = 0.0
    starter_code_overlap: float = 0.0
    previous_term_match: float = 0.0
    rare_pattern_score: float = 0.0
    common_solution_score: float = 0.0
    student_style_shift: float = 0.0

    # File type classification (added for file-type aware detection)
    file_type: FileType = FileType.CODE
    file_type_confidence: float = 0.0
    file_type_domain: str | None = None

    # Function matching evidence
    function_match_count: int = 0
    function_match_rate: float = 0.0
    variable_rename_count: int = 0
    parameter_rename_count: int = 0

    # Control flow evidence
    control_flow_similarity: float = 0.0
    control_flow_depth_match: int = 0  # 0-1 scale

    # Structural divergence (evidence for rule engine)
    structural_divergence: float = 0.0

    # Coverage of matching code segments
    coverage: float = 0.0  # Fraction of lines matched by CodeHighlighter (0.0-1.0)

    # Evidence fields for rule-based decisions
    ast_evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        """Convert FeatureVector to a dictionary."""
        return {
            "ast": self.ast,
            "fingerprint": self.fingerprint,
            "embedding": self.embedding,
            "ngram": self.ngram,
            "winnowing": self.winnowing,
            "string_tiling": self.string_tiling,
            "graph": self.graph,
            "static_rules": self.static_rules,
            "sklearn_cosine": self.sklearn_cosine,
            "cfg_similarity": self.cfg_similarity,
            "dfg_similarity": self.dfg_similarity,
            "call_graph_similarity": self.call_graph_similarity,
            "input_output_behavior_similarity": self.input_output_behavior_similarity,
            "edge_case_behavior_similarity": self.edge_case_behavior_similarity,
            "runtime_bug_similarity": self.runtime_bug_similarity,
            "identifier_rename_score": self.identifier_rename_score,
            "boilerplate_overlap": self.boilerplate_overlap,
            "starter_code_overlap": self.starter_code_overlap,
            "previous_term_match": self.previous_term_match,
            "rare_pattern_score": self.rare_pattern_score,
            "common_solution_score": self.common_solution_score,
            "student_style_shift": self.student_style_shift,
            "structural_divergence": self.structural_divergence,
        }


class FeatureExtractor:
    """Extracts a FeatureVector from a pair of source code strings.

    The extractor lazily loads each similarity engine so that importing the
    module is cheap and missing optional dependencies (e.g. ML models) only
    affect the engines that need them.
    """

    FEATURE_ORDER: ClassVar[list[str]] = [
        "fingerprint",
        "winnowing",
        "string_tiling",
        "ast",
        "ngram",
        "graph",
        "embedding",
        "static_rules",
        "sklearn_cosine",
    ]

    def __init__(self) -> None:
        # Cached engine instances (lazy-loaded on first use)
        self._ast_engine = None
        self._token_engine = None
        self._unixcoder_engine = None
        self._fallback_embedding = None
        self._ngram_engine = None
        self._winnowing_engine = None
        self._graph_engine = None
        self._sklearn_vectorizer = None
        self._file_type_classifier = None
        self._function_matcher = None
        self._control_flow_visualizer = None

    def _get_file_type_classifier(self):
        """Get or create the file type classifier."""
        if self._file_type_classifier is None:
            from src.backend.engines.file_type_classifier import (
                get_file_type_classifier,
            )

            self._file_type_classifier = get_file_type_classifier()
        return self._file_type_classifier

    def _get_function_matcher(self):
        """Get or create the function matcher."""
        if self._function_matcher is None:
            from src.backend.engines.function_matching import FunctionMatcher

            self._function_matcher = FunctionMatcher()
        return self._function_matcher

    def _get_control_flow_visualizer(self):
        """Get or create the control flow visualizer."""
        if self._control_flow_visualizer is None:
            from src.backend.engines.control_flow_visualization import (
                ControlFlowVisualizer,
            )

            self._control_flow_visualizer = ControlFlowVisualizer()
        return self._control_flow_visualizer

    def _resolve_embedding_base_url(self) -> str | None:
        if settings.EMBEDDING_SERVER_URL:
            return settings.EMBEDDING_SERVER_URL

        host = settings.EMBEDDING_SERVER_HOST
        if host:
            return f"http://{host}:{settings.EMBEDDING_SERVER_PORT}/v1"

        return settings.OPENAI_BASE_URL or None

    # ── Public API ──────────────────────────────────────────────

    def extract(
        self,
        code_a: str,
        code_b: str,
        filename_a: str | None = None,
        filename_b: str | None = None,
    ) -> FeatureVector:
        """Run all enabled engines and collect scores.

        Args:
            code_a: Source code of the first file.
            code_b: Source code of the second file.
            filename_a: Optional filename for file type classification.
            filename_b: Optional filename for file type classification.

        Returns:
            A FeatureVector with a score from each engine.
        """
        # Classify file types
        file_type = FileType.CODE
        file_type_confidence = 0.0
        file_type_domain = None

        if filename_a and filename_b:
            classifier = self._get_file_type_classifier()
            # Use the more conservative classification (lower confidence)
            class_a = classifier.classify(filename_a, code_a)
            class_b = classifier.classify(filename_b, code_b)

            # If either is CONFIG, treat as CONFIG
            if (
                class_a.file_type == FileType.CONFIG
                or class_b.file_type == FileType.CONFIG
            ):
                file_type = FileType.CONFIG
                file_type_domain = class_a.domain or class_b.domain
            elif (
                class_a.file_type == FileType.DATA or class_b.file_type == FileType.DATA
            ):
                file_type = FileType.DATA
            elif (
                class_a.file_type == FileType.SCRIPT
                or class_b.file_type == FileType.SCRIPT
            ):
                file_type = FileType.SCRIPT
            else:
                file_type = FileType.CODE

            file_type_confidence = min(class_a.confidence, class_b.confidence)

        ast = self._run_ast(code_a, code_b)
        fingerprint = self._run_fingerprint(code_a, code_b)
        embedding = self._run_embedding(code_a, code_b)
        ngram = self._run_ngram(code_a, code_b)
        winnowing = self._run_winnowing(code_a, code_b)
        string_tiling = self._run_string_tiling(code_a, code_b)
        graph = self._run_graph(code_a, code_b)
        ast_cfg_pdg = self._run_ast_cfg_pdg(code_a, code_b)
        graph = max(graph or 0.0, ast_cfg_pdg["similarity"])
        static_rules = self._run_static_rules(code_a, code_b)
        sklearn_cosine = self._run_sklearn(code_a, code_b)

        # Multi-layer AST analysis (new evidence-based approach)
        file_type_str = str(file_type) if isinstance(file_type, FileType) else file_type

        # Use evidence-based AST analysis
        ast_result = compute_ast_layer_scores(code_a, code_b, file_type_str)
        evidence = ast_result.get("evidence", {})

        # Get AST score from evidence (NOT a direct similarity score)
        ast = ast_result.get("final_score", 0.0)

        # Check for config file - apply special handling
        if file_type == FileType.CONFIG or file_type_str == "CONFIG":
            # For config files, AST evidence is supplementary
            # The rule engine makes the final decision
            pass

        # Function matching analysis
        function_matcher = self._get_function_matcher()
        func_report = function_matcher.match_functions(code_a, code_b)

        # Control flow analysis
        cf_visualizer = self._get_control_flow_visualizer()
        cf_tree_a = cf_visualizer.analyze(code_a)
        cf_tree_b = cf_visualizer.analyze(code_b)
        cf_comparison = cf_visualizer.compare_structures(cf_tree_a, cf_tree_b)

        # Coverage computation via CodeHighlighter
        coverage = self._compute_code_coverage(code_a, code_b)

        return FeatureVector(
            ast=ast if ast is not None else 0.0,
            fingerprint=fingerprint if fingerprint is not None else 0.0,
            embedding=embedding if embedding is not None else 0.0,
            ngram=ngram if ngram is not None else 0.0,
            winnowing=winnowing if winnowing is not None else 0.0,
            string_tiling=string_tiling if string_tiling is not None else 0.0,
            graph=graph if graph is not None else 0.0,
            static_rules=static_rules if static_rules is not None else 0.0,
            sklearn_cosine=sklearn_cosine if sklearn_cosine is not None else 0.0,
            cfg_similarity=max(graph or 0.0, ast_cfg_pdg["cfg_sim"]),
            dfg_similarity=ast_cfg_pdg["pdg_sim"],
            file_type=file_type,
            file_type_confidence=file_type_confidence,
            file_type_domain=file_type_domain,
            function_match_count=func_report.match_count,
            function_match_rate=func_report.match_rate,
            variable_rename_count=func_report.variable_rename_count,
            parameter_rename_count=func_report.parameter_rename_count,
            control_flow_similarity=cf_comparison.get("similarity", 0.0),
            control_flow_depth_match=min(
                1.0,
                cf_comparison.get("depth_a", 0)
                / max(1, cf_comparison.get("depth_b", 1)),
            ),
            # Add divergence score for evidence-based decisions
            structural_divergence=evidence.get("divergence_score", 0.0),
            # Add AST evidence for rule engine
            ast_evidence=evidence,
            # Code matching coverage
            coverage=coverage,
        )

    def to_features(self, fv: FeatureVector) -> list[float]:
        """Flatten a FeatureVector into a list of floats.

        Returns:
            List of floats in FEATURE_ORDER.
        """
        return [getattr(fv, name) for name in self.FEATURE_ORDER]

    def _coerce_score(self, result: Any, engine_name: str) -> float | None:
        """Normalize engine outputs to a plain numeric score.

        Similarity engines are not perfectly consistent today:
        some return a raw float while others return a Finding-like object
        with a ``score`` attribute. The downstream fusion layer expects
        floats only, so we normalize here at the integration boundary.
        """
        if result is None:
            return None

        if isinstance(result, (int, float)):
            return float(result)

        score = getattr(result, "score", None)
        if isinstance(score, (int, float)):
            return float(score)

        logger.debug(
            "Engine %s returned non-numeric result of type %s",
            engine_name,
            type(result).__name__,
        )
        return None

    # ── Private engine helpers ──────────────────────────────────

    def _run_ast(self, a: str, b: str) -> float | None:
        try:
            if self._ast_engine is None:
                from src.backend.engines.similarity.ast_similarity import ASTSimilarity

                self._ast_engine = ASTSimilarity()
            result = self._ast_engine.compare({"raw": a}, {"raw": b})
            return self._coerce_score(result, "ast")
        except Exception as exc:
            logger.debug("AST engine unavailable: %s", exc)
            return None

    def _run_fingerprint(self, a: str, b: str) -> float | None:
        try:
            if self._token_engine is None:
                from src.backend.engines.similarity.token_similarity import (
                    TokenSimilarity,
                )

                self._token_engine = TokenSimilarity()
            result = self._token_engine.compare({"raw": a}, {"raw": b})
            return self._coerce_score(result, "fingerprint")
        except Exception as exc:
            logger.debug("Token/Fingerprint engine unavailable: %s", exc)
            return None

    def _run_embedding(self, a: str, b: str) -> float | None:
        runtime = (settings.EMBEDDING_RUNTIME or "local_unixcoder").lower()

        if runtime in {"local", "local_unixcoder", "unixcoder"}:
            try:
                if self._unixcoder_engine is None:
                    from src.backend.engines.similarity.unixcoder_similarity import (
                        UniXcoderSimilarity,
                    )

                    self._unixcoder_engine = UniXcoderSimilarity(
                        model_name=settings.EMBEDDING_MODEL,
                        device=settings.EMBEDDING_DEVICE,
                        batch_size=settings.EMBEDDING_BATCH_SIZE,
                    )
                result = self._unixcoder_engine.compare({"raw": a}, {"raw": b})
                coerced = self._coerce_score(result, "embedding")
                if coerced is not None:
                    return coerced
            except Exception as exc:
                logger.debug(
                    "UniXcoder engine unavailable, falling back to API embeddings: %s",
                    exc,
                )

        try:
            if self._fallback_embedding is None:
                from src.backend.engines.similarity.embedding_similarity import (
                    EmbeddingSimilarity,
                )

                self._fallback_embedding = EmbeddingSimilarity(
                    model_name=settings.EMBEDDING_MODEL,
                    base_url=self._resolve_embedding_base_url(),
                    api_key=settings.OPENAI_API_KEY,
                )
            result = self._fallback_embedding.compare({"raw": a}, {"raw": b})
            return self._coerce_score(result, "embedding")
        except Exception as exc:
            logger.debug("Embedding API fallback also failed: %s", exc)
            return None

    def _run_ngram(self, a: str, b: str) -> float | None:
        try:
            if self._ngram_engine is None:
                from src.backend.engines.similarity.ngram_similarity import (
                    NgramSimilarity,
                )

                self._ngram_engine = NgramSimilarity()
            result = self._ngram_engine.compare({"raw": a}, {"raw": b})
            return self._coerce_score(result, "ngram")
        except Exception as exc:
            logger.debug("N-gram engine unavailable: %s", exc)
            return None

    def _run_winnowing(self, a: str, b: str) -> float | None:
        try:
            if self._winnowing_engine is None:
                from src.backend.engines.similarity.winnowing_similarity import (
                    EnhancedWinnowingSimilarity,
                )

                self._winnowing_engine = EnhancedWinnowingSimilarity()
            result = self._winnowing_engine.compare({"raw": a}, {"raw": b})
            return self._coerce_score(result, "winnowing")
        except Exception as exc:
            logger.debug("Winnowing engine unavailable: %s", exc)
            return None

    def _run_string_tiling(self, a: str, b: str) -> float | None:
        """Score normalized greedy string-tiling overlap between token streams."""
        tokens_a = self._normalized_tokens(a)
        tokens_b = self._normalized_tokens(b)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        matcher = SequenceMatcher(None, tokens_a, tokens_b, autojunk=False)
        matched_tokens = sum(
            block.size for block in matcher.get_matching_blocks() if block.size >= 3
        )
        if matched_tokens == 0:
            return 0.0

        return min(1.0, (2.0 * matched_tokens) / (len(tokens_a) + len(tokens_b)))

    def _run_graph(self, a: str, b: str) -> float | None:
        """Run CFG/DFG graph similarity when the graph backend supports the input."""
        try:
            if self._graph_engine is None:
                from src.backend.engines.similarity.graph_similarity import (
                    GraphSimilarity,
                )

                self._graph_engine = GraphSimilarity()
            result = self._graph_engine.compare({"content": a}, {"content": b})
            return self._coerce_score(result, "graph")
        except Exception as exc:
            logger.debug("Graph engine unavailable: %s", exc)
            return None

    def _run_ast_cfg_pdg(self, a: str, b: str) -> dict[str, float]:
        """Run normalized AST plus CFG/PDG comparison for Python code."""
        try:
            from src.backend.engines.features.ast_normalizer import compare_robust

            result = compare_robust(a, b)
        except Exception as exc:
            logger.debug("AST/CFG/PDG normalizer unavailable: %s", exc)
            return {"similarity": 0.0, "ast_sim": 0.0, "cfg_sim": 0.0, "pdg_sim": 0.0}

        return {
            "similarity": float(result.get("similarity", 0.0)),
            "ast_sim": float(result.get("ast_sim", 0.0)),
            "cfg_sim": float(result.get("cfg_sim", 0.0)),
            "pdg_sim": float(result.get("pdg_sim", 0.0)),
        }

    def _run_static_rules(self, a: str, b: str) -> float | None:
        """Compare PMD-like static rule fingerprints without external tools."""
        features_a = self._static_rule_features(a)
        features_b = self._static_rule_features(b)
        if not features_a and not features_b:
            return 1.0
        if not features_a or not features_b:
            return 0.0
        return self._counter_cosine(features_a, features_b)

    def _run_sklearn(self, a: str, b: str) -> float | None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            if self._sklearn_vectorizer is None:
                self._sklearn_vectorizer = TfidfVectorizer(
                    stop_words="english", max_features=5000
                )

            # Fit on both texts
            texts = [a, b]
            tfidf_matrix = self._sklearn_vectorizer.fit_transform(texts)
            # Compute cosine similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except ImportError:
            logger.debug("sklearn unavailable for sklearn_cosine engine")
            return None
        except Exception as exc:
            logger.debug("sklearn_cosine engine failed: %s", exc)
            return None

    def _normalized_tokens(self, source: str) -> list[str]:
        """Tokenize source while normalizing identifiers and literals."""
        raw_tokens = re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|[-+*/%<>=(){}\[\],.:;]",
            source,
        )
        keywords = {
            "and",
            "as",
            "break",
            "case",
            "catch",
            "class",
            "continue",
            "def",
            "else",
            "except",
            "finally",
            "for",
            "if",
            "import",
            "in",
            "return",
            "switch",
            "try",
            "while",
        }
        normalized: list[str] = []
        for token in raw_tokens:
            lower = token.lower()
            if re.fullmatch(r"\d+(?:\.\d+)?", token):
                normalized.append("NUM")
            elif (
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) and lower not in keywords
            ):
                normalized.append("ID")
            else:
                normalized.append(lower)
        return normalized

    def _static_rule_features(self, source: str) -> Counter[str]:
        """Extract static-analysis style structural features from source."""
        features: Counter[str] = Counter()
        try:
            import ast

            tree = ast.parse(source)
            for node in ast.walk(tree):
                node_name = type(node).__name__
                if node_name in {
                    "For",
                    "While",
                    "If",
                    "Try",
                    "ExceptHandler",
                    "With",
                    "FunctionDef",
                    "AsyncFunctionDef",
                    "ClassDef",
                    "Return",
                    "Assign",
                    "AugAssign",
                    "Compare",
                    "BoolOp",
                    "ListComp",
                    "DictComp",
                    "Lambda",
                    "Call",
                }:
                    features[f"ast:{node_name}"] += 1
        except SyntaxError:
            pass

        regex_rules = {
            "loop": r"\b(for|while)\b",
            "branch": r"\b(if|else|elif|switch|case)\b",
            "exception": r"\b(try|catch|except|finally)\b",
            "function": r"\b(def|function|void|int|String|public|private)\s+[A-Za-z_]",
            "class": r"\b(class|interface)\b",
            "return": r"\breturn\b",
            "io": r"\b(print|println|input|scanf|cout|cin)\b",
            "collection": r"\b(list|dict|set|map|array|ArrayList|HashMap)\b",
        }
        for name, pattern in regex_rules.items():
            count = len(re.findall(pattern, source))
            if count:
                features[f"rule:{name}"] += count

        return features

    def _compute_code_coverage(self, code_a: str, code_b: str) -> float:
        """Compute fraction of lines covered by matching code segments.

        Uses the CodeHighlighter to find matching segments and returns the
        maximum of the two files' matched-line fractions.  A high coverage
        indicates a large proportion of the code participates in matched
        segments, which is a strong plagiarism signal.

        Returns:
            A float in [0.0, 1.0].
        """
        try:
            from src.backend.engines.similarity.code_matching import (
                CodeHighlighter,
            )

            highlighter = CodeHighlighter()
            lines_a = self._non_noise_normalized_lines(code_a, highlighter)
            lines_b = self._non_noise_normalized_lines(code_b, highlighter)
            if not lines_a or not lines_b:
                return 0.0

            import difflib

            matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
            matched_a = sum(block.size for block in matcher.get_matching_blocks())
            return matched_a / max(len(lines_a), 1)
        except Exception as exc:
            logger.debug("CodeHighlighter coverage computation failed: %s", exc)
            return 0.0

    def _non_noise_normalized_lines(self, code: str, highlighter: Any) -> list[str]:
        """Return normalized code lines, skipping blank and comment-only lines.

        Coverage is measured over these lines so clones that are renamed or
        lightly reformatted still register as overlapping; blank lines and
        comment banners are noise and would otherwise fragment the matching.
        """
        normalized = []
        for line in code.splitlines():
            normalized_line = highlighter._normalize_identifiers(line.rstrip())
            compact = normalized_line.replace(" ", "").replace("\t", "")
            if not compact:
                continue
            if compact.startswith(("//", "/*", "*")):
                continue
            normalized.append(normalized_line)
        return normalized

    def _counter_cosine(self, left: Counter[str], right: Counter[str]) -> float:
        """Return cosine similarity for sparse counter features."""
        keys = set(left) | set(right)
        numerator = sum(left[key] * right[key] for key in keys)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return max(0.0, min(1.0, numerator / (left_norm * right_norm)))
