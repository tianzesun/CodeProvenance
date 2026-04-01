"""Fingerprint Engine - Token-based code fingerprinting."""
from typing import Dict, Any
from src.engines.base_engine import BaseEngine, EngineResult


class FingerprintEngine(BaseEngine):
    def __init__(self, weight: float = 1.0, k: int = 5, t: int = 10):
        super().__init__(name="fingerprint", weight=weight)
        self.k = k
        self.t = t

    def compare(self, code_a: str, code_b: str, language: str = 'auto', **kwargs) -> EngineResult:
        from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
        from src.core.parser.base_parser import ParserFactory
        parser_a = ParserFactory.get_parser(language)
        parser_b = ParserFactory.get_parser(language)
        parsed_a = parser_a.parse('unknown', code_a) if parser_a else {'tokens': [], 'raw': code_a}
        parsed_b = parser_b.parse('unknown', code_b) if parser_b else {'tokens': [], 'raw': code_b}
        winnowing = EnhancedWinnowingSimilarity(k=self.k, t=self.t)
        score = winnowing.compare(parsed_a, parsed_b)
        return EngineResult(score=score, details={'algorithm': 'enhanced_winnowing', 'k': self.k, 't': self.t}, confidence=0.9)

    def get_name(self) -> str:
        return "fingerprint"
