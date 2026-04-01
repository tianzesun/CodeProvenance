"""AI Code Detection Module - Perplexity + Burstiness analysis.

Detects AI-generated code using multiple signals:
- Perplexity: Measure of token predictability (low = AI-like)
- Burstiness: Variance in line length (uniform = AI-like)
- Pattern matching: AI-typical code comments and structures
- Repetition detection: AI often repeats similar phrasing
"""
import math
import re
from collections import Counter
from typing import Dict, List, Any


class AICodeDetector:
    """Detect AI-generated code using heuristic signals."""

    def __init__(self):
        self.ai_comment_patterns = [
            r"# Here\'s (?:a|an|the)",
            r"# This (?:function|code|method|class|approach)",
            r"# The following",
            r"# Let\'s ",
            r"# Now we",
            r"# First,? we",
            r"# Next,? we",
            r"# Finally,? ",
            r"# In (?:this|summary|conclusion)",
            r"# To (?:solve|implement|create|build|handle|process)",
            r"# This (?:function|method) (?:takes|receives|accepts|returns)",
        ]

    def detect(self, code: str) -> Dict[str, Any]:
        """Run all AI detection signals on code.

        Returns:
            {
                "ai_percentage": float 0-100,
                "confidence_interval": [low, high] 0-100,
                "perplexity_score": float 0-1,
                "burstiness_score": float 0-1,
                "pattern_score": float 0-1,
                "repetition_score": float 0-1,
                "detected_model": str or None
            }
        """
        perplexity = self._perplexity_score(code)
        burstiness = self._burstiness_score(code)
        pattern_score = self._ai_pattern_score(code)
        repetition = self._repetition_score(code)

        # Weighted combination
        ai_score = (
            perplexity * 0.30 +
            burstiness * 0.25 +
            pattern_score * 0.25 +
            repetition * 0.20
        ) * 100

        # Confidence based on score agreement
        scores = [perplexity, burstiness, pattern_score, repetition]
        spread = max(scores) - min(scores)
        confidence = max(0.5, 1.0 - spread)
        margin = max(0.05, (1 - confidence) * 0.30)

        # Tentative model fingerprint
        model = None
        if pattern_score > 0.70:
            model = "GPT-4/GPT-4o"
        elif pattern_score > 0.50:
            model = "Claude 3/Gemini"

        return {
            "ai_percentage": round(ai_score, 1),
            "confidence_interval": [
                round(max(0, ai_score - margin * 100), 1),
                round(min(100, ai_score + margin * 100), 1),
            ],
            "perplexity_score": round(perplexity, 3),
            "burstiness_score": round(burstiness, 3),
            "pattern_score": round(pattern_score, 3),
            "repetition_score": round(repetition, 3),
            "detected_model": model,
        }

    # --- Scoring functions ---

    @staticmethod
    def _perplexity_score(code: str) -> float:
        """Lower perplexity = more predictable code = higher AI likelihood.

        Uses simple bigram frequency analysis as a proxy for perplexity.
        """
        lines = [l.strip() for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
        if len(lines) < 3:
            return 0.5  # Not enough data

        tokens = ' '.join(lines).split()
        if len(tokens) < 3:
            return 0.5

        bigrams = list(zip(tokens, tokens[1:]))
        bigram_counts = Counter(bigrams)
        total = len(bigrams)

        # Average log probability
        log_probs = []
        for bi in bigrams:
            cnt = bigram_counts.get(bi, 1)
            prob = cnt / total
            if prob > 0:
                log_probs.append(-math.log2(prob))

        if not log_probs:
            return 0.5

        avg_log_prob = sum(log_probs) / len(log_probs)
        perplexity = 2 ** avg_log_prob

        # Normalize: typical code perplexity range is roughly 10-200
        # Lower perplexity is more AI-like
        normalized = max(0, min(1, (1 - (perplexity - 10) / (200 - 10))))
        return max(0, min(1, normalized))

    @staticmethod
    def _burstiness_score(code: str) -> float:
        """Uniform line lengths suggest AI generation.

        Human code has high variance in line length; AI code is more uniform.
        """
        lines = [l.strip() for l in code.split('\n') if l.strip()]
        if len(lines) < 3:
            return 0.5

        lengths = [len(l) for l in lines]
        mean_len = sum(lengths) / len(lengths)
        if mean_len == 0:
            return 0.5
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        cv = (variance ** 0.5) / mean_len  # Coefficient of variation

        # Low CV = uniform = AI-like
        # Typical human code CV is 0.4-1.5
        normalized = max(0, min(1, (0.4 - cv) / 0.4))  # 1.0 when cv near 0
        return max(0, min(1, normalized))

    def _ai_pattern_score(self, code: str) -> float:
        """Detect AI-typical code comment patterns."""
        if not code:
            return 0.0

        comments = re.findall(r'#.*', code) + re.findall(r'//.*', code)
        if not comments:
            return 0.0

        matches = sum(
            1 for c in comments
            for p in self.ai_comment_patterns
            if re.search(p, c)
        )
        # Score based on density of AI patterns
        return min(1.0, matches / max(len(comments) * 0.3, 1))

    @staticmethod
    def _repetition_score(code: str) -> float:
        """Detect repeated code blocks (AI often creates similar structures).

        High repetition of identical or near-identical lines suggests AI.
        """
        lines = [l.strip() for l in code.split('\n') if l.strip()]
        if len(lines) < 5:
            return 0.0  # Not enough data

        line_counts = Counter(lines)
        # Count how many lines appear more than once
        repeated = sum(cnt for line, cnt in line_counts.items() if cnt > 1)
        ratio = repeated / len(lines)

        # Human code typically has lower repetition
        # Normalized: >30% repeated lines is AI-typical
        return min(1.0, (ratio - 0.10) / 0.30)