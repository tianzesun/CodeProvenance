"""CodeProvenance Engine v4 - PRL v3 (Multi-Judge Precision Recovery Layer).

Architecture:
  [Candidate Generation] → [Evidence Extraction] → [Multi-Judge System] → [Score Fusion] → [Decision]
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from benchmark.similarity.base_engine import BaseSimilarityEngine


@dataclass
class Evidence:
    token_sim: float = 0.0
    ast_sim: float = 0.0
    embedding_sim: float = 0.0
    api_overlap: float = 0.0
    identifier_overlap: float = 0.0
    control_flow_sim: float = 0.0
    literal_sim: float = 0.0
    call_graph_sim: float = 0.0
    semantic_role_sim: float = 0.0
    lines_a: int = 0
    lines_b: int = 0
    code_size_ratio: float = 0.0
    shared_apis: Set[str] = field(default_factory=set)
    control_flow_a: List[str] = field(default_factory=list)
    control_flow_b: List[str] = field(default_factory=list)

    @property
    def is_short_function(self) -> bool:
        return min(self.lines_a, self.lines_b) < 5


@dataclass
class Judgment:
    passed: bool
    confidence: float
    reason: str = ""
    veto: bool = False


@dataclass
class MultiJudgeResult:
    accept: bool
    final_score: float
    risk_level: str
    rejections: List[str] = field(default_factory=list)
    judge_results: Dict[str, Judgment] = field(default_factory=dict)


def extract_apis(code: str) -> Set[str]:
    pattern = re.compile(r'\b([a-zA-Z_]\w*)\s*\(')
    exclude = {'if', 'while', 'for', 'switch', 'return', 'def', 'class',
               'lambda', 'with', 'print', 'len', 'range', 'int', 'str', 'float',
               'list', 'dict', 'set', 'tuple', 'bool', 'type', 'isinstance'}
    return {m.group(1) for m in pattern.finditer(code) if m.group(1) not in exclude}


def extract_control_flow(code: str) -> List[str]:
    return re.findall(r'\b(if|elif|else|for|while|return|try|except|break|continue|raise|yield)\b', code)


def extract_literals(code: str) -> Set[str]:
    strings = re.findall(r'["\']([^"\']*)["\']', code)
    numbers = re.findall(r'\b(\d+\.?\d*)\b', code)
    return set(strings) | set(numbers)


def extract_identifiers(code: str) -> Set[str]:
    return set(re.findall(r'\b([a-zA-Z_]\w*)\b', code)) - {
        'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while',
        'import', 'from', 'try', 'except', 'finally', 'with', 'as',
        'in', 'not', 'and', 'or', 'is', 'None', 'True', 'False',
    }


def control_flow_similarity(cf_a: List[str], cf_b: List[str]) -> float:
    if not cf_a and not cf_b:
        return 1.0
    counter_a = Counter(cf_a)
    counter_b = Counter(cf_b)
    all_keys = set(counter_a.keys()) | set(counter_b.keys())
    if not all_keys:
        return 1.0
    diffs = []
    for k in all_keys:
        max_count = max(counter_a.get(k, 0), counter_b.get(k, 0), 1)
        diff = abs(counter_a.get(k, 0) - counter_b.get(k, 0)) / max_count
        diffs.append(diff)
    return 1.0 - (sum(diffs) / len(diffs))


def sequence_overlap(seq_a: List[str], seq_b: List[str]) -> float:
    if not seq_a and not seq_b:
        return 1.0
    set_a, set_b = set(seq_a), set(seq_b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    intersection = set_a & set_b
    return len(intersection) / len(union) if union else 0.0


def compute_semantic_roles(code: str) -> Set[str]:
    roles = set()
    code_lower = code.lower()
    role_patterns = {
        'getter': r'def\s+get', 'setter': r'def\s+set',
        'validator': r'\b(validat|check|assert|verify)',
        'converter': r'\b(convert|transform|parse|format)',
        'calculator': r'\b(calc|comput|process|evaluat)',
        'filter': r'\b(filter|select|search|find)',
        'aggregator': r'\b(sum|aver|total|count|reduce)',
        'io': r'\b(open|read|write|print|input|fetch)',
        'sorter': r'\b(sort|order|arrang)',
        'iterator': r'\b(iterat|loop|travers)',
    }
    for role, pattern in role_patterns.items():
        if re.search(pattern, code_lower):
            roles.add(role)
    return roles


class EvidenceExtractor:
    def extract(self, code_a: str, code_b: str,
                token_sim: float, ast_sim: float, embedding_sim: float) -> Evidence:
        evidence = Evidence(
            token_sim=token_sim, ast_sim=ast_sim, embedding_sim=embedding_sim,
        )
        apis_a = extract_apis(code_a)
        apis_b = extract_apis(code_b)
        evidence.shared_apis = apis_a & apis_b
        if apis_a or apis_b:
            evidence.api_overlap = len(apis_a & apis_b) / len(apis_a | apis_b)
        else:
            evidence.api_overlap = 1.0

        cf_a = extract_control_flow(code_a)
        cf_b = extract_control_flow(code_b)
        evidence.control_flow_a = cf_a
        evidence.control_flow_b = cf_b
        evidence.control_flow_sim = control_flow_similarity(cf_a, cf_b)

        lit_a = extract_literals(code_a)
        lit_b = extract_literals(code_b)
        if lit_a or lit_b:
            evidence.literal_sim = len(lit_a & lit_b) / len(lit_a | lit_b)
        else:
            evidence.literal_sim = 1.0

        ids_a = extract_identifiers(code_a)
        ids_b = extract_identifiers(code_b)
        if ids_a or ids_b:
            evidence.identifier_overlap = len(ids_a & ids_b) / len(ids_a | ids_b)

        calls_a = re.findall(r'\b([a-zA-Z_]\w*)\s*\(', code_a)
        calls_b = re.findall(r'\b([a-zA-Z_]\w*)\s*\(', code_b)
        evidence.call_graph_sim = sequence_overlap(calls_a, calls_b)

        roles_a = compute_semantic_roles(code_a)
        roles_b = compute_semantic_roles(code_b)
        if roles_a or roles_b:
            evidence.semantic_role_sim = len(roles_a & roles_b) / len(roles_a | roles_b)
        else:
            evidence.semantic_role_sim = 1.0  # Both have no special roles = match

        evidence.lines_a = len(code_a.splitlines())
        evidence.lines_b = len(code_b.splitlines())
        if max(evidence.lines_a, evidence.lines_b) > 0:
            evidence.code_size_ratio = max(evidence.lines_a, evidence.lines_b) / max(min(evidence.lines_a, evidence.lines_b), 1)

        return evidence


class StrictStructuralJudge:
    def judge(self, evidence: Evidence) -> Judgment:
        rejections = []
        if evidence.ast_sim < 0.15:
            rejections.append(f"AST too low ({evidence.ast_sim:.2f})")
        if evidence.code_size_ratio > 3.0:
            rejections.append(f"Size mismatch (ratio={evidence.code_size_ratio:.1f})")
        if evidence.control_flow_sim < 0.2:
            rejections.append(f"Control flow divergent ({evidence.control_flow_sim:.2f})")
        if not rejections and evidence.token_sim < 0.1 and evidence.ast_sim < 0.2:
            rejections.append("No structural signal")
        return Judgment(
            passed=not bool(rejections), confidence=evidence.ast_sim,
            reason="; ".join(rejections), veto=bool(rejections)
        )


class SemanticValidator:
    def judge(self, evidence: Evidence) -> Judgment:
        rejections = []
        if evidence.embedding_sim > 0.85 and evidence.api_overlap < 0.2:
            rejections.append("Semantic hallucination (high embed, low API)")
        if evidence.embedding_sim > 0.9 and evidence.token_sim < 0.2 and evidence.ast_sim < 0.2:
            rejections.append("Embedding-only match")
        # Don't veto renamed clones - they have high AST
        if evidence.ast_sim > 0.8:
            return Judgment(passed=True, confidence=evidence.ast_sim)
        if evidence.embedding_sim > 0.8 and evidence.api_overlap < 0.1 and evidence.shared_apis:
            rejections.append("Different API usage")
        return Judgment(
            passed=not bool(rejections), confidence=1.0 - len(rejections) * 0.3,
            reason="; ".join(rejections), veto=bool(rejections)
        )


class BehaviorJudge:
    def judge(self, evidence: Evidence) -> Judgment:
        # CRITICAL FIX: For renamed clones (Type-2), AST is 1.0 but tokens differ completely
        # Don't reject when AST is perfect - structure IS the clone
        if evidence.ast_sim > 0.9:
            return Judgment(passed=True, confidence=evidence.ast_sim)

        rejections = []
        if evidence.control_flow_sim < 0.3:
            rejections.append(f"Behavior divergent (CF={evidence.control_flow_sim:.2f})")
        if evidence.call_graph_sim < 0.2 and evidence.token_sim < 0.2 and evidence.ast_sim < 0.2:
            rejections.append(f"Call graph mismatch")
        # Only reject semantic role mismatch when structure doesn't match
        if evidence.semantic_role_sim < 0.5 and evidence.control_flow_sim < 0.5:
            if evidence.ast_sim < 0.5:
                rejections.append("Different semantic roles")
        return Judgment(
            passed=not bool(rejections),
            confidence=max(evidence.control_flow_sim, evidence.call_graph_sim),
            reason="; ".join(rejections), veto=bool(rejections)
        )


class NoiseDetector:
    def judge(self, evidence: Evidence) -> Judgment:
        rejections = []
        # Short function protection (lenient for renamed clones)
        if evidence.is_short_function:
            if evidence.token_sim < 0.5 and evidence.ast_sim < 0.3:
                rejections.append("Short function with weak match")

        # CRITICAL: Renamed clones have low ID overlap but high AST
        # Don't veto if AST is high
        if evidence.ast_sim > 0.5:
            return Judgment(passed=True, confidence=evidence.ast_sim)

        # Only veto if ALL signals are truly weak
        if (evidence.token_sim < 0.1 and evidence.ast_sim < 0.1 and
            evidence.embedding_sim < 0.3):
            rejections.append("All signals too weak")

        if evidence.identifier_overlap < 0.05 and evidence.literal_sim < 0.1:
            if not evidence.shared_apis and evidence.ast_sim < 0.3:
                rejections.append("No shared identifiers or APIs")

        return Judgment(
            passed=not bool(rejections), confidence=0.9 - len(rejections) * 0.2,
            reason="; ".join(rejections), veto=bool(rejections)
        )


class MultiJudgeSystem:
    def __init__(self):
        self.structural = StrictStructuralJudge()
        self.semantic = SemanticValidator()
        self.behavior = BehaviorJudge()
        self.noise = NoiseDetector()

    def evaluate(self, evidence: Evidence) -> MultiJudgeResult:
        results = {
            "structural": self.structural.judge(evidence),
            "semantic": self.semantic.judge(evidence),
            "behavior": self.behavior.judge(evidence),
            "noise": self.noise.judge(evidence),
        }
        risk_score = 0
        if evidence.ast_sim < 0.2: risk_score += 1
        if evidence.api_overlap < 0.1: risk_score += 1
        if evidence.embedding_sim > 0.85 and evidence.token_sim < 0.3: risk_score += 1
        if evidence.is_short_function: risk_score += 1
        if risk_score >= 3:
            risk_level = "high"
        elif risk_score >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        rejections = []
        for name, j in results.items():
            if j.veto:
                rejections.append(f"{name}: {j.reason}")

        accept = not any(j.veto for j in results.values())
        return MultiJudgeResult(
            accept=accept, final_score=0.0, risk_level=risk_level,
            rejections=rejections, judge_results=results,
        )


class ScoreFusionV2:
    @staticmethod
    def fuse(evidence: Evidence) -> float:
        w_token = 0.25
        w_ast = 0.25
        w_embed = 0.20
        w_api = 0.10
        w_cf = 0.10
        w_lit = 0.10

        # High embedding is risky - reduce weight
        if evidence.embedding_sim > 0.85:
            w_embed *= 0.5
            w_ast += 0.05
            w_token += 0.05

        if evidence.ast_sim > 0.7:
            w_ast += 0.1
        if evidence.api_overlap > 0.7:
            w_api += 0.05

        total = w_token + w_ast + w_embed + w_api + w_cf + w_lit
        score = (
            w_token * evidence.token_sim +
            w_ast * evidence.ast_sim +
            w_embed * evidence.embedding_sim +
            w_api * evidence.api_overlap +
            w_cf * evidence.control_flow_sim +
            w_lit * evidence.literal_sim
        ) / total

        return min(1.0, max(0.0, score))


class AdaptiveThresholdV2:
    @staticmethod
    def get_threshold(evidence: Evidence, risk_level: str) -> float:
        if risk_level == "high":
            return 0.90
        elif risk_level == "medium":
            return 0.80
        else:
            return 0.55  # Lowered from 0.65 for Type-2 clones


class PRLv3:
    def __init__(self):
        self.extractor = EvidenceExtractor()
        self.judges = MultiJudgeSystem()
        self.fusion = ScoreFusionV2()
        self.threshold = AdaptiveThresholdV2()

    def evaluate(self, code_a: str, code_b: str,
                 token_sim: float, ast_sim: float, embedding_sim: float) -> Tuple[bool, float]:
        evidence = self.extractor.extract(code_a, code_b, token_sim, ast_sim, embedding_sim)

        # Fast accept: very strong signals
        if token_sim > 0.95 and ast_sim > 0.9:
            return True, 1.0
        # Fast accept: AST is perfect (Type-2 renamed clone)
        if ast_sim > 0.99 and evidence.api_overlap >= 0.0:
            # Structure is identical - accept even with token=0
            return True, max(0.5, ast_sim)
        # Fast reject: all signals very weak
        if token_sim < 0.05 and ast_sim < 0.05 and embedding_sim < 0.2:
            return False, 0.0

        verdict = self.judges.evaluate(evidence)
        if not verdict.accept:
            return False, 0.0

        final_score = self.fusion.fuse(evidence)
        adaptive_thresh = self.threshold.get_threshold(evidence, verdict.risk_level)

        if final_score < adaptive_thresh:
            return False, final_score

        return True, final_score


class CodeProvenanceEngineV4(BaseSimilarityEngine):
    def __init__(self):
        self._token_engine = None
        self._prl = PRLv3()

    def _get_token_engine(self):
        if self._token_engine is None:
            from benchmark.similarity import TokenWinnowingEngine
            self._token_engine = TokenWinnowingEngine()
        return self._token_engine

    @property
    def name(self) -> str:
        return "codeprovenance_v4"

    def compare(self, code_a: str, code_b: str) -> float:
        if not code_a or not code_b:
            return 0.0

        token_sim = self._get_token_engine().compare(code_a, code_b)
        ast_sim = self._compute_ast_similarity(code_a, code_b)
        embedding_sim = self._compute_embedding_similarity(code_a, code_b)

        is_clone, confidence = self._prl.evaluate(
            code_a, code_b, token_sim, ast_sim, embedding_sim
        )

        if is_clone:
            return confidence
        return 0.0

    def _compute_ast_similarity(self, code_a: str, code_b: str) -> float:
        try:
            from benchmark.similarity import compare_ast_safe
            return compare_ast_safe(code_a, code_b, max_depth=3)
        except Exception:
            return 0.0

    def _compute_embedding_similarity(self, code_a: str, code_b: str) -> float:
        tokens_a = set(code_a.lower().split())
        tokens_b = set(code_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)