"""Feature Extractor - Extracts features from code pairs for similarity engines."""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, ClassVar

from src.backend.config.settings import settings
from src.backend.engines.ast_multi_layer import compute_ast_layer_scores
from src.backend.engines.file_type_classifier import FileType

logger = logging.getLogger(__name__)

#: ``SequenceMatcher`` is roughly quadratic, and ``autojunk=False`` removes its
#: only safeguard, so one very large pair could pin a worker for minutes. Inputs
#: beyond these sizes are compared on their leading part only.
MAX_TILING_TOKENS = 6000
MAX_COVERAGE_LINES = 5000

#: Runtime values that switch embeddings off. ``"none"`` is what the benchmark
#: runner sets on hosts without a GPU; it used to be treated as "not local" and
#: sent the code to the embedding API instead.
_EMBEDDING_DISABLED = frozenset({"none", "off", "disabled", "false", "0"})
_LOCAL_EMBEDDING_RUNTIMES = frozenset({"local", "local_unixcoder", "unixcoder"})

_KEYWORDS = frozenset(
    {
        "and", "as", "assert", "async", "await", "break", "case", "catch", "class", "const",
        "continue", "def", "default", "del", "do", "elif", "else", "except", "finally", "for",
        "from", "function", "global", "if", "import", "in", "is", "lambda", "let", "new",
        "nonlocal", "not", "or", "pass", "private", "public", "raise", "return", "static",
        "switch", "this", "throw", "try", "var", "void", "while", "with", "yield",
    }
)  # fmt: skip
_TOKEN_RE = re.compile(
    r"(?P<comment>#[^\n]*|//[^\n]*|/\*.*?\*/)"
    r"|(?P<string>\"\"\"(?:\\.|[^\\])*?\"\"\"|'''(?:\\.|[^\\])*?'''"
    r"|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"
    r"|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<op>==|!=|<=|>=|[-+*/%<>=(){}\[\],.:;])",
    re.DOTALL,
)


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
    control_flow_depth_match: float = 0.0  # 0-1 ratio (was annotated ``int``)

    # Structural divergence (evidence for rule engine)
    structural_divergence: float = 0.0

    # Coverage of matching code segments
    coverage: float = 0.0  # Fraction of lines matched by CodeHighlighter (0.0-1.0)
    #: False when coverage could not be computed. 0.0 then means "unknown", not "no overlap";
    #: the fusion hard gate must not veto on it.
    coverage_available: bool = True

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

    An engine whose constructor fails is remembered and skipped (with one
    warning) instead of being re-imported and re-constructed for every pair; a
    failed local embedding model used to be reloaded on every comparison.
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
        self._file_type_classifier = None
        self._function_matcher = None
        self._control_flow_visualizer = None
        self._code_highlighter = None
        self._failed_engines: set[str] = set()

    # ── Lazy engine loading ─────────────────────────────────────

    def _load(self, name: str, attr: str, factory: Callable[[], Any]) -> Any:
        """Return the cached engine ``attr``, constructing it once.

        Returns ``None`` (without retrying) if it cannot be constructed.
        """
        engine = getattr(self, attr)
        if engine is not None:
            return engine
        if name in self._failed_engines:
            return None
        try:
            engine = factory()
        except Exception as exc:
            self._failed_engines.add(name)
            logger.warning("%s engine unavailable, scoring it as 0.0: %s", name, exc)
            return None
        setattr(self, attr, engine)
        return engine

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

    def _get_code_highlighter(self):
        """Get or create the CodeHighlighter (it was rebuilt for every pair)."""
        if self._code_highlighter is None:
            from src.backend.engines.similarity.code_matching import CodeHighlighter

            self._code_highlighter = CodeHighlighter()
        return self._code_highlighter

    def _resolve_embedding_base_url(self) -> str | None:
        if settings.EMBEDDING_SERVER_URL:
            return settings.EMBEDDING_SERVER_URL

        host = settings.EMBEDDING_SERVER_HOST
        if host:
            return f"http://{host}:{settings.EMBEDDING_SERVER_PORT}/v1"

        return settings.OPENAI_BASE_URL or None

    def _embedding_runtime(self) -> str:
        """Configured embedding runtime.

        The environment is read first: the benchmark runner switches embeddings
        off by setting ``EMBEDDING_RUNTIME`` in the process environment, but
        ``settings`` is read once at start-up and never saw that change.
        """
        return (
            os.environ.get("EMBEDDING_RUNTIME")
            or settings.EMBEDDING_RUNTIME
            or "local_unixcoder"
        ).strip().lower()

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
        file_type, file_type_confidence, file_type_domain = self._classify_pair(
            code_a, code_b, filename_a, filename_b
        )

        fingerprint = self._run_fingerprint(code_a, code_b)
        embedding = self._run_embedding(code_a, code_b)
        ngram = self._run_ngram(code_a, code_b)
        winnowing = self._run_winnowing(code_a, code_b)
        string_tiling = self._run_string_tiling(code_a, code_b)
        graph_raw = self._run_graph(code_a, code_b)
        ast_cfg_pdg = self._run_ast_cfg_pdg(code_a, code_b)
        graph = max(graph_raw or 0.0, ast_cfg_pdg["similarity"])
        static_rules = self._run_static_rules(code_a, code_b)
        sklearn_cosine = self._run_sklearn(code_a, code_b)

        # Multi-layer, evidence-based AST analysis. Its score is the AST feature.
        file_type_str = str(file_type) if isinstance(file_type, FileType) else file_type
        ast_score, evidence = self._run_ast_layers(code_a, code_b, file_type_str)

        func_report = self._run_function_matching(code_a, code_b)
        cf_comparison = self._run_control_flow(code_a, code_b)
        coverage_value = self._compute_code_coverage(code_a, code_b)
        coverage = 0.0 if coverage_value is None else coverage_value

        depth_a = cf_comparison.get("depth_a", 0) or 0
        depth_b = cf_comparison.get("depth_b", 0) or 0
        return FeatureVector(
            ast=ast_score,
            fingerprint=fingerprint if fingerprint is not None else 0.0,
            embedding=embedding if embedding is not None else 0.0,
            ngram=ngram if ngram is not None else 0.0,
            winnowing=winnowing if winnowing is not None else 0.0,
            string_tiling=string_tiling if string_tiling is not None else 0.0,
            graph=graph,
            static_rules=static_rules if static_rules is not None else 0.0,
            sklearn_cosine=sklearn_cosine if sklearn_cosine is not None else 0.0,
            # ``graph`` is already max()-ed with the combined score above, so using
            # it here made cfg_similarity a copy of the combined score. Use the
            # raw graph engine and the CFG-only score.
            cfg_similarity=max(graph_raw or 0.0, ast_cfg_pdg["cfg_sim"]),
            dfg_similarity=ast_cfg_pdg["pdg_sim"],
            file_type=file_type,
            file_type_confidence=file_type_confidence,
            file_type_domain=file_type_domain,
            function_match_count=getattr(func_report, "match_count", 0),
            function_match_rate=getattr(func_report, "match_rate", 0.0),
            variable_rename_count=getattr(func_report, "variable_rename_count", 0),
            parameter_rename_count=getattr(func_report, "parameter_rename_count", 0),
            control_flow_similarity=cf_comparison.get("similarity", 0.0),
            # smaller / larger depth. It was ``depth_a / depth_b`` capped at 1, which
            # reported a perfect match whenever A was deeper than B (10 vs 2 -> 1.0).
            control_flow_depth_match=(
                1.0 if depth_a == depth_b else min(depth_a, depth_b) / max(depth_a, depth_b)
            ),
            structural_divergence=evidence.get("divergence_score", 0.0),
            ast_evidence=evidence,
            coverage=coverage,
            coverage_available=coverage_value is not None,
        )

    def to_features(self, fv: FeatureVector) -> list[float]:
        """Flatten a FeatureVector into a list of floats.

        Returns:
            List of floats in FEATURE_ORDER.
        """
        return [getattr(fv, name) for name in self.FEATURE_ORDER]

    # ── Pair-level analyses (each isolated: one failure no longer aborts extract) ──

    def _classify_pair(
        self, code_a: str, code_b: str, filename_a: str | None, filename_b: str | None
    ) -> tuple[FileType, float, str | None]:
        if not (filename_a and filename_b):
            return FileType.CODE, 0.0, None
        try:
            classifier = self._get_file_type_classifier()
            class_a = classifier.classify(filename_a, code_a)
            class_b = classifier.classify(filename_b, code_b)
        except Exception:
            logger.warning("File type classification failed; treating the pair as code", exc_info=True)
            return FileType.CODE, 0.0, None

        # Use the more conservative classification: CONFIG, then DATA, then SCRIPT.
        domain = None
        if FileType.CONFIG in (class_a.file_type, class_b.file_type):
            file_type = FileType.CONFIG
            domain = class_a.domain or class_b.domain
        elif FileType.DATA in (class_a.file_type, class_b.file_type):
            file_type = FileType.DATA
        elif FileType.SCRIPT in (class_a.file_type, class_b.file_type):
            file_type = FileType.SCRIPT
        else:
            file_type = FileType.CODE
        return file_type, min(class_a.confidence, class_b.confidence), domain

    def _run_ast_layers(self, code_a: str, code_b: str, file_type_str: Any) -> tuple[float, dict]:
        """Evidence-based AST score, falling back to the plain AST engine.

        The plain engine used to run on EVERY pair and its result was thrown away
        (overwritten by the layered score), doubling the most expensive structural
        step. It now runs only when the layered analysis fails.
        """
        try:
            result = compute_ast_layer_scores(code_a, code_b, file_type_str)
            return float(result.get("final_score", 0.0) or 0.0), result.get("evidence", {}) or {}
        except Exception:
            logger.warning("Multi-layer AST analysis failed; using the plain AST engine", exc_info=True)
        return self._run_ast(code_a, code_b) or 0.0, {}

    def _run_function_matching(self, code_a: str, code_b: str) -> Any:
        try:
            return self._get_function_matcher().match_functions(code_a, code_b)
        except Exception:
            logger.warning("Function matching failed; reporting no function evidence", exc_info=True)
            return None

    def _run_control_flow(self, code_a: str, code_b: str) -> dict[str, Any]:
        try:
            visualizer = self._get_control_flow_visualizer()
            return visualizer.compare_structures(
                visualizer.analyze(code_a), visualizer.analyze(code_b)
            ) or {}
        except Exception:
            logger.warning("Control flow analysis failed; reporting no control-flow evidence", exc_info=True)
            return {}

    def _coerce_score(self, result: Any, engine_name: str) -> float | None:
        """Normalize engine outputs to a plain numeric score.

        Similarity engines are not perfectly consistent today:
        some return a raw float while others return a Finding-like object
        with a ``score`` attribute. The downstream fusion layer expects
        floats only, so we normalize here at the integration boundary.
        NaN and infinity are treated as "no result" rather than propagated.
        """
        if result is None:
            return None

        if isinstance(result, (int, float)):
            value = float(result)
        else:
            score = getattr(result, "score", None)
            if not isinstance(score, (int, float)):
                logger.debug(
                    "Engine %s returned non-numeric result of type %s",
                    engine_name,
                    type(result).__name__,
                )
                return None
            value = float(score)

        if not math.isfinite(value):
            logger.debug("Engine %s returned a non-finite score", engine_name)
            return None
        return value

    # ── Private engine helpers ──────────────────────────────────

    def _compare_with(self, name: str, attr: str, factory: Callable[[], Any], a: str, b: str,
                      key: str = "raw") -> float | None:
        engine = self._load(name, attr, factory)
        if engine is None:
            return None
        try:
            return self._coerce_score(engine.compare({key: a}, {key: b}), name)
        except Exception as exc:
            logger.debug("%s engine failed on this pair: %s", name, exc)
            return None

    def _run_ast(self, a: str, b: str) -> float | None:
        def factory():
            from src.backend.engines.similarity.ast_similarity import ASTSimilarity

            return ASTSimilarity()

        return self._compare_with("ast", "_ast_engine", factory, a, b)

    def _run_fingerprint(self, a: str, b: str) -> float | None:
        def factory():
            from src.backend.engines.similarity.token_similarity import TokenSimilarity

            return TokenSimilarity()

        return self._compare_with("fingerprint", "_token_engine", factory, a, b)

    def _run_embedding(self, a: str, b: str) -> float | None:
        runtime = self._embedding_runtime()
        if runtime in _EMBEDDING_DISABLED:
            return None

        if runtime in _LOCAL_EMBEDDING_RUNTIMES:

            def local_factory():
                from src.backend.engines.similarity.unixcoder_similarity import (
                    UniXcoderSimilarity,
                )

                return UniXcoderSimilarity(
                    model_name=settings.EMBEDDING_MODEL,
                    device=settings.EMBEDDING_DEVICE,
                    batch_size=settings.EMBEDDING_BATCH_SIZE,
                )

            local = self._compare_with("unixcoder", "_unixcoder_engine", local_factory, a, b)
            if local is not None:
                return local

        # Fall back to a remote embedding endpoint ONLY if one has been
        # configured. Student code used to be sent to an external API whenever
        # the local model was missing, whether or not anyone had set that up.
        base_url = self._resolve_embedding_base_url()
        if not (settings.OPENAI_API_KEY or base_url):
            return None
        logger.info("Using the configured embedding API for this comparison")

        def api_factory():
            from src.backend.engines.similarity.embedding_similarity import (
                EmbeddingSimilarity,
            )

            return EmbeddingSimilarity(
                model_name=settings.EMBEDDING_MODEL,
                base_url=base_url,
                api_key=settings.OPENAI_API_KEY,
            )

        return self._compare_with("embedding_api", "_fallback_embedding", api_factory, a, b)

    def _run_ngram(self, a: str, b: str) -> float | None:
        def factory():
            from src.backend.engines.similarity.ngram_similarity import NgramSimilarity

            return NgramSimilarity()

        return self._compare_with("ngram", "_ngram_engine", factory, a, b)

    def _run_winnowing(self, a: str, b: str) -> float | None:
        def factory():
            from src.backend.engines.similarity.winnowing_similarity import (
                EnhancedWinnowingSimilarity,
            )

            return EnhancedWinnowingSimilarity()

        return self._compare_with("winnowing", "_winnowing_engine", factory, a, b)

    def _run_string_tiling(self, a: str, b: str) -> float | None:
        """Score normalized token-sequence overlap (matching blocks of 3+ tokens)."""
        tokens_a = self._normalized_tokens(a)[:MAX_TILING_TOKENS]
        tokens_b = self._normalized_tokens(b)[:MAX_TILING_TOKENS]
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

        def factory():
            from src.backend.engines.similarity.graph_similarity import GraphSimilarity

            return GraphSimilarity()

        return self._compare_with("graph", "_graph_engine", factory, a, b, key="content")

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

            # A fresh vectorizer per call. One instance was cached on ``self`` and
            # re-fitted on every pair, so concurrent comparisons (a thread pool over
            # one extractor) overwrote each other's vocabulary.
            vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
            tfidf_matrix = vectorizer.fit_transform([a, b])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return self._coerce_score(float(similarity), "sklearn_cosine")
        except ImportError:
            logger.debug("sklearn unavailable for sklearn_cosine engine")
            return None
        except Exception as exc:
            logger.debug("sklearn_cosine engine failed: %s", exc)
            return None

    def _normalized_tokens(self, source: str) -> list[str]:
        """Tokenize source while normalizing identifiers and literals.

        Comments are dropped and string literals collapse to one token. Their
        words used to be tokenized as code, so rewording a comment changed the
        score. A single scanner pass classifies each token (the old code ran two
        ``re.fullmatch`` calls per token).
        """
        normalized: list[str] = []
        append = normalized.append
        for match in _TOKEN_RE.finditer(source):
            kind = match.lastgroup
            if kind == "comment":
                continue
            if kind == "string":
                append("STR")
            elif kind == "number":
                append("NUM")
            elif kind == "ident":
                word = match.group().lower()
                append(word if word in _KEYWORDS else "ID")
            else:
                append(match.group())
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
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            # Not Python, or unparseable (NUL bytes / deep nesting also land here;
            # only SyntaxError used to be caught).
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

    def _compute_code_coverage(self, code_a: str, code_b: str) -> float | None:
        """Compute fraction of lines covered by matching code segments.

        Uses the CodeHighlighter's normalization to find matching segments and
        returns the larger of the two files' matched-line fractions. A high
        coverage indicates a large proportion of the code participates in matched
        segments, which is a strong plagiarism signal.

        The old code divided only by the length of file A, contradicting this
        description: a 10-line file fully contained in a 1,000-line one scored 1.0
        or 0.01 depending on argument order.

        Returns:
            A float in [0.0, 1.0], or None when the computation failed.
        """
        try:
            highlighter = self._get_code_highlighter()
            lines_a = self._non_noise_normalized_lines(code_a, highlighter)[:MAX_COVERAGE_LINES]
            lines_b = self._non_noise_normalized_lines(code_b, highlighter)[:MAX_COVERAGE_LINES]
            if not lines_a or not lines_b:
                return 0.0

            matcher = SequenceMatcher(None, lines_a, lines_b, autojunk=False)
            matched = sum(block.size for block in matcher.get_matching_blocks())
            return min(1.0, max(matched / len(lines_a), matched / len(lines_b)))
        except Exception as exc:
            logger.debug("CodeHighlighter coverage computation failed: %s", exc)
            return None

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
