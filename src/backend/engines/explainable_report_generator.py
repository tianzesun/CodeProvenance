"""Explainable plagiarism report generator.

Combines AST alignment and GST alignment into forensic proof reports.
"""

from typing import List, Dict, Tuple, Any, Optional, Set
from dataclasses import dataclass
import ast


@dataclass
class MatchUnit:
    """Unified match unit combining AST and GST evidence."""

    confidence: float
    ast_nodes: List[Tuple[ast.AST, ast.AST]]
    gst_block: Optional[Tuple[int, int, int]]
    transformation: str
    a_range: Tuple[int, int]
    b_range: Tuple[int, int]


@dataclass
class ExplainableReport:
    """Full explainable plagiarism report."""

    overall_score: float
    confidence: float
    detected_strategies: List[str]
    ast_matches: List[Tuple[str, str]]
    gst_blocks: List[Dict[str, Any]]
    transformation_analysis: List[str]
    final_verdict: str
    match_units: List[MatchUnit]

    def to_string(self) -> str:
        """Format report as human-readable text."""
        lines = []
        lines.append("📄 PLAGIARISM ANALYSIS REPORT")
        lines.append("=" * 48)
        lines.append("")
        lines.append(
            f"Overall similarity: {self.overall_score:.2f} ({self._confidence_label()})"
        )
        lines.append("")

        if self.detected_strategies:
            lines.append("Detected strategy:")
            for s in self.detected_strategies:
                lines.append(f"  ✔ {s}")
            lines.append("")

        lines.append("-" * 48)
        lines.append("AST ALIGNMENT (STRUCTURAL MATCH)")
        lines.append("-" * 48)
        for a_node, b_node in self.ast_matches:
            lines.append(f"✔ {a_node} ↔ {b_node}")
        lines.append("")

        lines.append("-" * 48)
        lines.append("GST ALIGNMENT (COPIED BLOCKS)")
        lines.append("-" * 48)
        for i, block in enumerate(self.gst_blocks, 1):
            lines.append(f"Block {i} ({block['match_percent']:.0f}% match):")
            lines.append(
                f"  A[{block['a_start']}-{block['a_end']}] ↔ B[{block['b_start']}-{block['b_end']}]"
            )
            if "a_snippet" in block:
                lines.append(f"    {block['a_snippet']}")
            lines.append("")

        lines.append("-" * 48)
        lines.append("TRANSFORMATION ANALYSIS")
        lines.append("-" * 48)
        for t in self.transformation_analysis:
            lines.append(f"✔ {t}")
        lines.append("")

        lines.append("-" * 48)
        lines.append("FINAL VERDICT")
        lines.append("-" * 48)
        lines.append(f"→ {self.final_verdict}")

        return "\n".join(lines)

    def _confidence_label(self) -> str:
        if self.confidence >= 0.9:
            return "HIGH CONFIDENCE"
        elif self.confidence >= 0.7:
            return "MEDIUM CONFIDENCE"
        else:
            return "LOW CONFIDENCE"


class ASTAligner:
    """Aligns AST nodes between two programs using subtree hashing."""

    def __init__(self):
        self.node_hashes = {}

    def _hash_node(self, node: ast.AST) -> int:
        """Compute normalized hash for AST node."""
        node_id = id(node)
        if node_id in self.node_hashes:
            return self.node_hashes[node_id]

        child_hashes = []
        for child in ast.iter_child_nodes(node):
            child_hashes.append(self._hash_node(child))

        node_type = type(node).__name__

        # Normalize identifiers
        if isinstance(node, ast.Name):
            value = ("NAME",)
        elif isinstance(node, ast.Constant):
            value = ("CONST", type(node.value).__name__)
        else:
            value = ()

        h = hash((node_type, value, tuple(sorted(child_hashes))))
        self.node_hashes[node_id] = h
        return h

    def align(self, ast_a: ast.AST, ast_b: ast.AST) -> List[Tuple[ast.AST, ast.AST]]:
        """Align matching AST nodes between two programs."""
        self.node_hashes.clear()

        # Build hash index for ast_b
        index_b = {}

        def collect_b(n: ast.AST) -> None:
            h = self._hash_node(n)
            index_b.setdefault(h, []).append(n)
            for c in ast.iter_child_nodes(n):
                collect_b(c)

        collect_b(ast_b)

        # Find matches in ast_a
        matches = []

        def match_a(n: ast.AST) -> None:
            h = self._hash_node(n)
            if h in index_b and index_b[h]:
                matched = index_b[h].pop()
                matches.append((n, matched))
            for c in ast.iter_child_nodes(n):
                match_a(c)

        match_a(ast_a)

        return matches

    def get_node_label(self, node: ast.AST) -> str:
        """Get human-readable label for AST node."""
        if isinstance(node, ast.FunctionDef):
            return f"FunctionDef: {node.name}"
        elif isinstance(node, ast.Assign):
            return "Assignment"
        elif isinstance(node, ast.Call):
            if hasattr(node.func, "id"):
                return f"Call: {node.func.id}(...)"
            return "Call"
        elif isinstance(node, ast.Return):
            return "Return statement"
        elif isinstance(node, (ast.For, ast.While)):
            return f"{type(node).__name__} loop"
        elif isinstance(node, ast.If):
            return "If statement"
        return type(node).__name__


class GSTAligner:
    """Greedy String Tiling alignment for exact block matching."""

    def align(
        self, tokens_a: List[str], tokens_b: List[str], min_match: int = 3
    ) -> List[Tuple[int, int, int]]:
        """Find all matching tile blocks between two token sequences."""
        matches = []
        marked_a = [False] * len(tokens_a)
        marked_b = [False] * len(tokens_b)

        while True:
            max_len = min_match - 1
            matches_found = []

            for i in range(len(tokens_a)):
                if marked_a[i]:
                    continue
                for j in range(len(tokens_b)):
                    if marked_b[j]:
                        continue

                    l = 0
                    while (
                        i + l < len(tokens_a)
                        and j + l < len(tokens_b)
                        and not marked_a[i + l]
                        and not marked_b[j + l]
                        and tokens_a[i + l] == tokens_b[j + l]
                    ):
                        l += 1

                    if l > max_len:
                        max_len = l
                        matches_found = [(i, j, l)]
                    elif l == max_len:
                        matches_found.append((i, j, l))

            if max_len < min_match:
                break

            # Mark matches
            for i, j, l in matches_found:
                overlap = False
                for k in range(l):
                    if marked_a[i + k] or marked_b[j + k]:
                        overlap = True
                        break
                if overlap:
                    continue

                for k in range(l):
                    marked_a[i + k] = True
                    marked_b[j + k] = True

                matches.append((i, j, l))

        return matches


class ReportGenerator:
    """Generates explainable plagiarism reports by fusing AST + GST alignment."""

    def __init__(self):
        self.ast_aligner = ASTAligner()
        self.gst_aligner = GSTAligner()

    def generate_report(
        self,
        code_a: str,
        code_b: str,
        engine_scores: Dict[str, float],
        final_score: float,
    ) -> ExplainableReport:
        """Generate full explainable report for a code pair."""
        # Parse ASTs
        try:
            ast_a = ast.parse(code_a)
            ast_b = ast.parse(code_b)
            ast_valid = True
        except SyntaxError:
            ast_valid = False

        # AST alignment
        ast_matches = []
        if ast_valid:
            matches = self.ast_aligner.align(ast_a, ast_b)
            ast_matches = [
                (self.ast_aligner.get_node_label(a), self.ast_aligner.get_node_label(b))
                for a, b in matches
            ][
                :15
            ]  # Limit to top 15 matches

        # GST alignment
        from src.backend.engines.similarity.token_similarity import TokenSimilarity

        tokenizer = TokenSimilarity()
        tokens_a = tokenizer._normalize_identifiers(
            tokenizer._extract_tokens({"raw": code_a})
        )
        tokens_b = tokenizer._normalize_identifiers(
            tokenizer._extract_tokens({"raw": code_b})
        )

        gst_tiles = self.gst_aligner.align(tokens_a, tokens_b)

        # Format GST blocks
        gst_blocks = []
        code_a_lines = code_a.splitlines()
        code_b_lines = code_b.splitlines()

        for a_start, b_start, length in gst_tiles:
            a_end = a_start + length
            b_end = b_start + length

            # Extract snippet (approximate)
            a_snippet = ""
            if a_start < len(code_a_lines):
                a_snippet = code_a_lines[a_start % len(code_a_lines)].strip()[:60]

            gst_blocks.append(
                {
                    "a_start": a_start,
                    "a_end": a_end,
                    "b_start": b_start,
                    "b_end": b_end,
                    "length": length,
                    "match_percent": 100.0,
                    "a_snippet": a_snippet,
                }
            )

        # Detect transformation strategies
        detected_strategies = []
        transformation_analysis = []

        ast_score = engine_scores.get("ast", 0.0)
        token_score = engine_scores.get("token", 0.0)

        if ast_score > 0.8 and token_score < 0.6:
            detected_strategies.append("Variable renaming")
            transformation_analysis.append("Identifiers renamed - structure preserved")

        if ast_score > 0.7 and abs(ast_score - token_score) > 0.2:
            detected_strategies.append("Surface obfuscation")
            transformation_analysis.append(
                "Code structure preserved, surface changes only"
            )

        if engine_scores.get("gst", 0.0) > 0.5 and engine_scores.get("ast", 0.0) > 0.7:
            detected_strategies.append("Block-level copying")

        # Final verdict
        if final_score >= 0.9:
            verdict = "Likely plagiarism (high confidence) - Same algorithm with surface-level obfuscation"
        elif final_score >= 0.7:
            verdict = "Possible plagiarism - Significant structural and token overlap"
        elif final_score >= 0.5:
            verdict = "Suspicious similarity - Possible shared logic or common pattern"
        else:
            verdict = "Unlikely plagiarism - Minimal similarity detected"

        # Confidence calculation
        confidence = min(
            1.0,
            final_score + 0.1 * (len(ast_matches) / 10) + 0.1 * (len(gst_blocks) / 5),
        )

        return ExplainableReport(
            overall_score=final_score,
            confidence=confidence,
            detected_strategies=detected_strategies,
            ast_matches=ast_matches,
            gst_blocks=gst_blocks,
            transformation_analysis=transformation_analysis,
            final_verdict=verdict,
            match_units=[],
        )
