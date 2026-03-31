"""AST Engine - Abstract Syntax Tree based similarity detection."""
from typing import Dict, Any
from src.engines.base_engine import BaseEngine, EngineResult


class ASTEngine(BaseEngine):
    def __init__(self, weight: float = 1.0, use_deep_analysis: bool = True):
        super().__init__(name="ast", weight=weight)
        self.use_deep_analysis = use_deep_analysis

    def compare(self, code_a: str, code_b: str, language: str = 'auto', **kwargs) -> EngineResult:
        from src.core.parser.base_parser import ParserFactory
        parser_a = ParserFactory.get_parser(language)
        parser_b = ParserFactory.get_parser(language)
        parsed_a = parser_a.parse('unknown', code_a) if parser_a else {'ast': None, 'raw': code_a}
        parsed_b = parser_b.parse('unknown', code_b) if parser_b else {'ast': None, 'raw': code_b}
        score = 0.0
        details = {}
        if self.use_deep_analysis and parsed_a.get('ast') and parsed_b.get('ast'):
            from src.core.similarity.deep_analysis import compare_codes_deep
            deep_result = compare_codes_deep(parsed_a, parsed_b, language)
            score = deep_result.get('combined_score', 0.0)
            details = {'tree_edit_distance': deep_result.get('tree_edit_distance', 1.0),
                       'tree_kernel': deep_result.get('tree_kernel_similarity', 0.0)}
        else:
            from src.core.similarity.ast_similarity import ASTSimilarity
            score = ASTSimilarity().compare(parsed_a, parsed_b)
            details = {'algorithm': 'ast_similarity'}
        return EngineResult(score=score, details=details, confidence=0.85)

    def get_name(self) -> str:
        return "ast"
