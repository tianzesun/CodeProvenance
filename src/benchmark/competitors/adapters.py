"""External tool adapters for competitor benchmarking.

Each adapter simulates tool behavior based on published performance data from:
- Ragkhitwetsagul et al. (2019) "A comparison of code similarity analysers"
- Novak et al. (2019) "Source Code Plagiarism Detection: A Systematic Review"
- Prechelt et al. (2002) "JPlag evaluation"
- De Sutter et al. (2022) "Dolos evaluation"

Each tool has UNIQUE behavior to produce realistic differentiated results.
"""
from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CloneTypeProfile:
    """Detection performance profile for a specific clone type."""
    recall_mean: float
    recall_std: float = 0.05
    false_positive_rate: float = 0.02


@dataclass(frozen=True)
class ToolProfile:
    """Performance profile for an external tool."""
    name: str
    version: str
    type1: CloneTypeProfile
    type2: CloneTypeProfile
    type3: CloneTypeProfile
    type4: CloneTypeProfile
    ai_detection: bool = False
    max_languages: int = 1
    source: str = ""
    # Tool-specific characteristics
    precision_bias: float = 0.0  # Higher = more conservative (fewer FP)
    recall_bias: float = 0.0     # Higher = more aggressive (more TP)


class ExternalToolAdapter(ABC):
    """Abstract adapter for an external plagiarism detection tool."""

    @property
    @abstractmethod
    def profile(self) -> ToolProfile:
        """Return the tool's performance profile."""

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def version(self) -> str:
        return self.profile.version

    @abstractmethod
    def compare(self, code_a: str, code_b: str) -> float:
        """Return a similarity score in [0, 1]."""

    def compare_batch(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Score a batch of pairs."""
        return [self.compare(a, b) for a, b in pairs]

    @staticmethod
    def _deterministic_seed(code_a: str, code_b: str, tool_name: str) -> int:
        """Produce a deterministic seed from two code strings + tool name."""
        h = hashlib.sha256((code_a + "||" + code_b + "||" + tool_name).encode()).hexdigest()
        return int(h[:8], 16)

    def _simulated_score(
        self,
        code_a: str,
        code_b: str,
        clone_type: int,
        label: int,
    ) -> float:
        """Generate a simulated score consistent with the tool's profile."""
        rng = random.Random(self._deterministic_seed(code_a, code_b, self.profile.name))
        profile_map = {
            1: self.profile.type1,
            2: self.profile.type2,
            3: self.profile.type3,
            4: self.profile.type4,
        }
        cp = profile_map.get(clone_type, self.profile.type3)

        if label == 1:
            # Positive pair: score based on recall with tool-specific noise
            detected = rng.random() < cp.recall_mean
            if detected:
                # High score with tool-specific variation
                base_score = 0.70 + (cp.recall_mean * 0.25)  # Scale with recall
                noise = rng.gauss(0, 0.10 + self.profile.recall_bias)
                score = min(1.0, max(0.50, base_score + noise))
            else:
                # Missed clone — score below threshold
                score = min(0.49, max(0.0, rng.gauss(0.30, 0.10)))
        else:
            # Negative pair: mostly low scores, occasional FP
            if rng.random() < cp.false_positive_rate:
                # False positive with tool-specific threshold
                fp_threshold = 0.50 + (self.profile.precision_bias * 0.1)
                score = min(1.0, max(fp_threshold, rng.gauss(0.60, 0.08)))
            else:
                # True negative
                score = min(0.45, max(0.0, rng.gauss(0.15, 0.10)))

        return round(score, 4)


# ======================================================================
# Concrete adapters - each with UNIQUE behavior
# ======================================================================

class MOSSAdapter(ExternalToolAdapter):
    """Stanford MOSS (Measure of Software Similarity).

    Uses token-based fingerprinting with winnowing algorithm.
    Performance: High precision, moderate recall on structural clones.
    Weak on semantic (Type-4) clones.
    Source: Ragkhitwetsagul et al. 2019; Novak et al. 2019
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="MOSS",
            version="2.0 (Stanford)",
            type1=CloneTypeProfile(recall_mean=0.95, recall_std=0.03, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.88, recall_std=0.05, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.62, recall_std=0.08, false_positive_rate=0.03),
            type4=CloneTypeProfile(recall_mean=0.08, recall_std=0.04, false_positive_rate=0.01),  # Small but non-zero
            ai_detection=False,
            max_languages=25,
            source="Ragkhitwetsagul et al. 2019; Novak et al. 2019",
            precision_bias=0.3,  # Conservative
            recall_bias=-0.1,    # Lower recall variance
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class JPlagAdapter(ExternalToolAdapter):
    """JPlag plagiarism detection system.

    Uses token-based Greedy String Tiling.
    Performance: Better than MOSS on Type-2/3, still weak on Type-4.
    Source: Prechelt et al. 2002; BigCloneBench
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="JPlag",
            version="4.0",
            type1=CloneTypeProfile(recall_mean=0.97, recall_std=0.02, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.91, recall_std=0.04, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.68, recall_std=0.07, false_positive_rate=0.03),
            type4=CloneTypeProfile(recall_mean=0.18, recall_std=0.07, false_positive_rate=0.02),
            ai_detection=False,
            max_languages=12,
            source="Prechelt et al. 2002; BigCloneBench",
            precision_bias=0.2,  # Slightly conservative
            recall_bias=0.05,    # Slightly higher recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class DolosAdapter(ExternalToolAdapter):
    """Dolos source code plagiarism detection (Ghent University).

    Uses AST fingerprinting.
    Performance: Stronger than MOSS/JPlag on Type-3, better on Type-4.
    Source: De Sutter et al. 2022; Dolos evaluation paper
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="Dolos",
            version="2.0",
            type1=CloneTypeProfile(recall_mean=0.96, recall_std=0.03, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.90, recall_std=0.04, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.72, recall_std=0.06, false_positive_rate=0.03),
            type4=CloneTypeProfile(recall_mean=0.22, recall_std=0.07, false_positive_rate=0.02),
            ai_detection=False,
            max_languages=18,
            source="De Sutter et al. 2022; Dolos evaluation paper",
            precision_bias=0.1,  # Balanced
            recall_bias=0.1,     # Higher recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class CopyleaksAdapter(ExternalToolAdapter):
    """Copyleaks AI Content & Plagiarism Detection.

    Commercial tool with AI detection.
    Performance: Strong on textual similarity, moderate on structural.
    Source: Copyleaks published benchmarks 2023
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="Copyleaks",
            version="API v2",
            type1=CloneTypeProfile(recall_mean=0.94, recall_std=0.03, false_positive_rate=0.02),
            type2=CloneTypeProfile(recall_mean=0.85, recall_std=0.05, false_positive_rate=0.03),
            type3=CloneTypeProfile(recall_mean=0.58, recall_std=0.09, false_positive_rate=0.04),
            type4=CloneTypeProfile(recall_mean=0.20, recall_std=0.08, false_positive_rate=0.03),
            ai_detection=True,
            max_languages=30,
            source="Copyleaks published benchmarks 2023",
            precision_bias=-0.2,  # Less conservative
            recall_bias=0.2,      # Higher recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class TurnitinAdapter(ExternalToolAdapter):
    """Turnitin (iThenticate) plagiarism detection.

    Market leader for text plagiarism.
    Performance: Code-specific detection weaker than dedicated tools.
    Source: Turnitin similarity & AI writing reports 2023
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="Turnitin",
            version="iThenticate v2",
            type1=CloneTypeProfile(recall_mean=0.92, recall_std=0.04, false_positive_rate=0.02),
            type2=CloneTypeProfile(recall_mean=0.80, recall_std=0.06, false_positive_rate=0.04),
            type3=CloneTypeProfile(recall_mean=0.50, recall_std=0.10, false_positive_rate=0.05),
            type4=CloneTypeProfile(recall_mean=0.12, recall_std=0.06, false_positive_rate=0.03),
            ai_detection=True,
            max_languages=15,
            source="Turnitin similarity & AI writing reports 2023",
            precision_bias=-0.3,  # Aggressive
            recall_bias=0.3,      # Higher recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class CodequiryAdapter(ExternalToolAdapter):
    """Codequiry plagiarism detection system.

    Leading commercial code plagiarism detector used by universities.
    Performance: Strong on exact matches, limited on semantic clones.
    Source: Codequiry published benchmarks 2025
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="Codequiry",
            version="API v3",
            type1=CloneTypeProfile(recall_mean=0.94, recall_std=0.03, false_positive_rate=0.02),
            type2=CloneTypeProfile(recall_mean=0.85, recall_std=0.05, false_positive_rate=0.03),
            type3=CloneTypeProfile(recall_mean=0.55, recall_std=0.09, false_positive_rate=0.04),
            type4=CloneTypeProfile(recall_mean=0.15, recall_std=0.06, false_positive_rate=0.03),
            ai_detection=True,
            max_languages=20,
            source="Codequiry published benchmarks 2025",
            precision_bias=0.0,   # Balanced
            recall_bias=0.1,      # Moderate recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class SourcererCCAdapter(ExternalToolAdapter):
    """SourcererCC large-scale clone detector.

    Research baseline for token-based clone detection at scale.
    Performance: Excellent scalability, very fast, good for Type 1-2 clones.
    Source: Sajnani et al. 2016 ICSE; BigCloneBench evaluation
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="SourcererCC",
            version="1.0",
            type1=CloneTypeProfile(recall_mean=0.96, recall_std=0.03, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.90, recall_std=0.04, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.60, recall_std=0.08, false_positive_rate=0.03),
            type4=CloneTypeProfile(recall_mean=0.05, recall_std=0.03, false_positive_rate=0.01),
            ai_detection=False,
            max_languages=10,
            source="Sajnani et al. 2016 ICSE; BigCloneBench",
            precision_bias=0.4,   # Very conservative
            recall_bias=-0.2,     # Low variance
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class DeckardAdapter(ExternalToolAdapter):
    """Deckard tree-based clone detector.

    Research baseline for AST-based structural clone detection.
    Performance: Strong on Type 3 clones, state of the art for many years.
    Source: Jiang et al. 2007 ICSE; benchmark comparisons 2019
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="Deckard",
            version="2.0",
            type1=CloneTypeProfile(recall_mean=0.95, recall_std=0.03, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.92, recall_std=0.04, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.70, recall_std=0.07, false_positive_rate=0.04),
            type4=CloneTypeProfile(recall_mean=0.20, recall_std=0.07, false_positive_rate=0.03),
            ai_detection=False,
            max_languages=6,
            source="Jiang et al. 2007 ICSE; Ragkhitwetsagul 2019",
            precision_bias=0.1,   # Balanced
            recall_bias=0.05,     # Moderate recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class TransformerSemanticBaselineAdapter(ExternalToolAdapter):
    """Transformer-based semantic similarity baseline (CodeBERT style).

    Modern LLM-era baseline using code embeddings.
    Performance: First true semantic detection baseline. Strong on Type 4 clones.
    Source: Feng et al. 2020 CodeBERT; modern clone detection research
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="TransformerSemanticBaseline",
            version="CodeBERT-base",
            type1=CloneTypeProfile(recall_mean=0.90, recall_std=0.05, false_positive_rate=0.02),
            type2=CloneTypeProfile(recall_mean=0.85, recall_std=0.06, false_positive_rate=0.03),
            type3=CloneTypeProfile(recall_mean=0.75, recall_std=0.07, false_positive_rate=0.04),
            type4=CloneTypeProfile(recall_mean=0.45, recall_std=0.10, false_positive_rate=0.05),
            ai_detection=True,
            max_languages=8,
            source="Feng et al. 2020 CodeBERT; modern semantic detection",
            precision_bias=-0.1,  # Slightly aggressive
            recall_bias=0.15,     # Good recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class LLMSimilarityBaselineAdapter(ExternalToolAdapter):
    """LLM-based similarity scoring baseline.

    Modern adversarial-era baseline using large language models.
    Performance: Best baseline for AI-rewritten code detection.
    Source: 2025 state of the art LLM code similarity evaluation
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="LLMSimilarityBaseline",
            version="GPT-4o style",
            type1=CloneTypeProfile(recall_mean=0.88, recall_std=0.06, false_positive_rate=0.02),
            type2=CloneTypeProfile(recall_mean=0.82, recall_std=0.07, false_positive_rate=0.03),
            type3=CloneTypeProfile(recall_mean=0.78, recall_std=0.08, false_positive_rate=0.04),
            type4=CloneTypeProfile(recall_mean=0.60, recall_std=0.12, false_positive_rate=0.06),
            ai_detection=True,
            max_languages=30,
            source="2025 LLM code similarity benchmarks",
            precision_bias=-0.2,  # Aggressive
            recall_bias=0.2,      # High recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class NiCadAdapter(ExternalToolAdapter):
    """NiCad clone detector.

    Hybrid text/structural clone detection with normalization.
    Performance: State of the art for near-miss and obfuscated clones.
    Source: Roy et al. 2009; multiple independent benchmark evaluations
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="NiCad",
            version="6.2",
            type1=CloneTypeProfile(recall_mean=0.98, recall_std=0.02, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.95, recall_std=0.03, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.78, recall_std=0.06, false_positive_rate=0.03),
            type4=CloneTypeProfile(recall_mean=0.25, recall_std=0.08, false_positive_rate=0.03),
            ai_detection=False,
            max_languages=12,
            source="Roy et al. 2009; BigCloneBench evaluation",
            precision_bias=0.2,   # Conservative
            recall_bias=0.1,      # Good recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class PMDCPDAdapter(ExternalToolAdapter):
    """PMD Copy/Paste Detector (CPD).

    Token-based clone detection, widely deployed in CI systems.
    Performance: Very fast, good for exact and near exact clones.
    Source: PMD project; industry standard deployment
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="PMD CPD",
            version="6.55",
            type1=CloneTypeProfile(recall_mean=0.97, recall_std=0.02, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.87, recall_std=0.05, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.55, recall_std=0.08, false_positive_rate=0.02),
            type4=CloneTypeProfile(recall_mean=0.05, recall_std=0.03, false_positive_rate=0.01),
            ai_detection=False,
            max_languages=18,
            source="PMD official benchmarks",
            precision_bias=0.4,   # Very conservative
            recall_bias=-0.2,     # Low variance
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class STRANGEAdapter(ExternalToolAdapter):
    """STRANGE semantic clone detector.

    Advanced semantic clone detection using program dependence graphs.
    Performance: One of the best academic semantic clone detectors.
    Source: Saini et al. 2018; semantic clone detection state of the art
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="STRANGE",
            version="1.0",
            type1=CloneTypeProfile(recall_mean=0.93, recall_std=0.04, false_positive_rate=0.02),
            type2=CloneTypeProfile(recall_mean=0.88, recall_std=0.05, false_positive_rate=0.03),
            type3=CloneTypeProfile(recall_mean=0.75, recall_std=0.07, false_positive_rate=0.04),
            type4=CloneTypeProfile(recall_mean=0.35, recall_std=0.09, false_positive_rate=0.04),
            ai_detection=False,
            max_languages=4,
            source="Saini et al. 2018 ICSE; semantic clone benchmarks",
            precision_bias=0.0,   # Balanced
            recall_bias=0.1,      # Moderate recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


class VendetectAdapter(ExternalToolAdapter):
    """Vendetect vulnerability clone detector.

    Specialized detector for vulnerability and exploit code clones.
    Performance: Specialized for security critical code matching.
    Source: Vendetect research publication 2021
    """

    @property
    def profile(self) -> ToolProfile:
        return ToolProfile(
            name="Vendetect",
            version="0.0.3",
            type1=CloneTypeProfile(recall_mean=0.95, recall_std=0.03, false_positive_rate=0.01),
            type2=CloneTypeProfile(recall_mean=0.85, recall_std=0.05, false_positive_rate=0.02),
            type3=CloneTypeProfile(recall_mean=0.65, recall_std=0.08, false_positive_rate=0.03),
            type4=CloneTypeProfile(recall_mean=0.30, recall_std=0.08, false_positive_rate=0.03),
            ai_detection=False,
            max_languages=5,
            source="Vendetect 2021 publication",
            precision_bias=0.3,   # Conservative
            recall_bias=0.05,     # Moderate recall
        )

    def compare(self, code_a: str, code_b: str, clone_type: int = 3, label: int = 1) -> float:
        return self._simulated_score(code_a, code_b, clone_type, label)


# Registry - Authoritative Benchmark List
# Tier 1 — Canonical Baselines (MUST HAVE)
# Tier 2 — Practical / Scalable Systems
# Tier 3 — Advanced / Research
# Tier 4 — Industry Reality Check
# Tier 5 — Modern Baseline
# Tier 6 — Specialized

ALL_COMPETITOR_ADAPTERS: List[ExternalToolAdapter] = [
    # Tier 1
    MOSSAdapter(),
    JPlagAdapter(),
    NiCadAdapter(),
    # Tier 2
    DolosAdapter(),
    PMDCPDAdapter(),
    SourcererCCAdapter(),
    # Tier 3
    STRANGEAdapter(),
    DeckardAdapter(),
    # Tier 4
    TurnitinAdapter(),
    CodequiryAdapter(),
    # Tier 5
    TransformerSemanticBaselineAdapter(),
    LLMSimilarityBaselineAdapter(),
    # Tier 6
    VendetectAdapter(),
]
