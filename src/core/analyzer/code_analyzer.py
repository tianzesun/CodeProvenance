"""
Code Analyzer for CodeProvenance.

High-level interface for code similarity analysis.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib

from src.core.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
from src.utils.ai_detection import detect_ai_code


@dataclass
class AnalysisResult:
    """Result of analyzing a single code submission."""
    file_path: str
    language: str
    line_count: int
    token_count: int
    code_hash: str
    ai_detection: Dict[str, Any]
    complexity_metrics: Dict[str, Any]
    parsed_data: Dict[str, Any]
    analysis_time: float


@dataclass
class ComparisonResult:
    """Result of comparing two code submissions."""
    file_a: str
    file_b: str
    overall_score: float
    individual_scores: Dict[str, float]
    confidence_interval: Dict[str, float]
    deep_analysis: Optional[Dict[str, Any]]
    is_suspicious: bool
    comparison_time: float


class CodeAnalyzer:
    """
    High-level code analyzer for similarity detection.
    
    Provides easy-to-use interface for:
    - Analyzing individual code submissions
    - Comparing pairs of submissions
    - Batch analysis of multiple submissions
    - AI detection integration
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        enable_deep_analysis: bool = True,
        enable_ai_detection: bool = True
    ):
        """
        Initialize code analyzer.
        
        Args:
            threshold: Similarity threshold for flagging (0.0-1.0)
            enable_deep_analysis: Enable deep AST analysis
            enable_ai_detection: Enable AI-generated code detection
        """
        self.threshold = threshold
        self.enable_deep_analysis = enable_deep_analysis
        self.enable_ai_detection = enable_ai_detection
        
        # Initialize similarity engine
        self.similarity_engine = SimilarityEngine()
        register_builtin_algorithms(self.similarity_engine)
        
        # Enable deep analysis if requested
        self.similarity_engine.enable_deep_analysis(enable_deep_analysis)
        
        # Parser factory for language detection
        self._parsers = {}
    
    def analyze_code(
        self,
        code: str,
        language: str = 'auto',
        file_path: str = 'unknown'
    ) -> AnalysisResult:
        """
        Analyze a single code submission.
        
        Args:
            code: Source code to analyze
            language: Programming language ('auto' for auto-detection)
            file_path: File path for reference
            
        Returns:
            AnalysisResult with analysis data
        """
        import time
        start_time = time.time()
        
        # Auto-detect language if needed
        if language == 'auto':
            language = self._detect_language(code, file_path)
        
        # Parse code
        parsed_data = self._parse_code(code, language)
        
        # Calculate metrics
        lines = code.split('\n')
        line_count = len([l for l in lines if l.strip()])
        token_count = len(parsed_data.get('tokens', []))
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # AI detection
        ai_detection = {}
        if self.enable_ai_detection:
            ai_result = detect_ai_code(code, language)
            ai_detection = {
                'is_likely_ai': ai_result.is_likely_ai,
                'ai_score': ai_result.ai_score,
                'confidence': ai_result.confidence,
                'indicators': ai_result.indicators,
                'explanation': ai_result.explanation
            }
        
        # Complexity metrics
        complexity_metrics = self._calculate_complexity(parsed_data)
        
        analysis_time = time.time() - start_time
        
        return AnalysisResult(
            file_path=file_path,
            language=language,
            line_count=line_count,
            token_count=token_count,
            code_hash=code_hash,
            ai_detection=ai_detection,
            complexity_metrics=complexity_metrics,
            parsed_data=parsed_data,
            analysis_time=analysis_time
        )
    
    def compare_codes(
        self,
        code_a: str,
        code_b: str,
        language_a: str = 'auto',
        language_b: str = 'auto',
        file_a: str = 'unknown',
        file_b: str = 'unknown'
    ) -> ComparisonResult:
        """
        Compare two code submissions.
        
        Args:
            code_a: First source code
            code_b: Second source code
            language_a: Language of first code
            language_b: Language of second code
            file_a: File path of first code
            file_b: File path of second code
            
        Returns:
            ComparisonResult with similarity scores
        """
        import time
        start_time = time.time()
        
        # Parse both codes
        parsed_a = self._parse_code(code_a, language_a)
        parsed_b = self._parse_code(code_b, language_b)
        
        # Compare using similarity engine
        comparison_result = self.similarity_engine.compare(parsed_a, parsed_b)
        
        # Extract scores
        overall_score = comparison_result.get('overall_score', 0.0)
        individual_scores = comparison_result.get('individual_scores', {})
        confidence_interval = comparison_result.get('confidence_interval', {})
        deep_analysis = comparison_result.get('deep_analysis')
        
        # Determine if suspicious
        is_suspicious = overall_score >= self.threshold
        
        comparison_time = time.time() - start_time
        
        return ComparisonResult(
            file_a=file_a,
            file_b=file_b,
            overall_score=overall_score,
            individual_scores=individual_scores,
            confidence_interval=confidence_interval,
            deep_analysis=deep_analysis,
            is_suspicious=is_suspicious,
            comparison_time=comparison_time
        )
    
    def analyze_pairwise(
        self,
        submissions: Dict[str, str],
        languages: Optional[Dict[str, str]] = None
    ) -> List[ComparisonResult]:
        """
        Analyze all pairwise comparisons between submissions.
        
        Args:
            submissions: Dictionary mapping file paths to code content
            languages: Optional dictionary mapping file paths to languages
            
        Returns:
            List of ComparisonResult for all pairs
        """
        results = []
        file_list = list(submissions.keys())
        
        for i, file_a in enumerate(file_list):
            for file_b in file_list[i + 1:]:
                code_a = submissions[file_a]
                code_b = submissions[file_b]
                
                lang_a = languages.get(file_a, 'auto') if languages else 'auto'
                lang_b = languages.get(file_b, 'auto') if languages else 'auto'
                
                result = self.compare_codes(
                    code_a=code_a,
                    code_b=code_b,
                    language_a=lang_a,
                    language_b=lang_b,
                    file_a=file_a,
                    file_b=file_b
                )
                results.append(result)
        
        return results
    
    def find_suspicious_pairs(
        self,
        submissions: Dict[str, str],
        threshold: Optional[float] = None,
        languages: Optional[Dict[str, str]] = None
    ) -> List[ComparisonResult]:
        """
        Find pairs with similarity above threshold.
        
        Args:
            submissions: Dictionary mapping file paths to code content
            threshold: Custom threshold (overrides default)
            languages: Optional language mappings
            
        Returns:
            List of ComparisonResult for suspicious pairs
        """
        if threshold is None:
            threshold = self.threshold
        
        all_results = self.analyze_pairwise(submissions, languages)
        
        # Filter by threshold
        suspicious = [r for r in all_results if r.overall_score >= threshold]
        
        # Sort by score descending
        suspicious.sort(key=lambda x: x.overall_score, reverse=True)
        
        return suspicious
    
    def _parse_code(self, code: str, language: str) -> Dict[str, Any]:
        """Parse code into structured representation."""
        from src.core.parser.base_parser import ParserFactory
        from src.core.parser.python_parser import PythonParser
        
        # Get parser for language
        parser = ParserFactory.get_parser(language)
        
        if parser is None:
            # Fallback to basic parsing
            return {
                'language': language,
                'tokens': self._tokenize_basic(code),
                'ast': None,
                'lines': code.split('\n'),
                'raw': code
            }
        
        # Parse with language-specific parser
        parsed = parser.parse('unknown', code)
        parsed['raw'] = code
        return parsed
    
    def _tokenize_basic(self, code: str) -> List[Dict[str, Any]]:
        """Basic tokenization for unsupported languages."""
        import re
        
        tokens = []
        # Simple regex-based tokenization
        patterns = [
            (r'\b(if|else|elif|for|while|return|def|class|import|from)\b', 'KEYWORD'),
            (r'\b[a-zA-Z_]\w*\b', 'IDENTIFIER'),
            (r'\b\d+\b', 'NUMBER'),
            (r'["\'].*?["\']', 'STRING'),
            (r'[+\-*/%=<>!&|^~]', 'OPERATOR'),
            (r'[(){}\[\]:;,.]', 'PUNCTUATION'),
        ]
        
        for match in re.finditer('|'.join(f'(?P<{name}>{pattern})' for pattern, name in patterns), code):
            for name, value in match.groupdict().items():
                if value:
                    tokens.append({
                        'type': name,
                        'value': value,
                        'line': code[:match.start()].count('\n') + 1
                    })
        
        return tokens
    
    def _detect_language(self, code: str, file_path: str) -> str:
        """Auto-detect programming language."""
        # Check file extension
        if file_path != 'unknown':
            ext = Path(file_path).suffix.lower()
            extension_map = {
                '.py': 'python',
                '.java': 'java',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.c': 'c',
                '.cpp': 'cpp',
                '.cs': 'csharp',
                '.go': 'go',
                '.rs': 'rust',
                '.rb': 'ruby',
                '.php': 'php',
                '.scala': 'scala',
                '.swift': 'swift',
                '.kt': 'kotlin',
            }
            if ext in extension_map:
                return extension_map[ext]
        
        # Simple heuristic based on code patterns
        if 'def ' in code or 'import ' in code or 'class ' in code:
            if ':' in code and '->' in code:
                return 'python'
            elif '{' in code and '}' in code:
                return 'java'
        
        # Default
        return 'python'
    
    def _calculate_complexity(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate code complexity metrics."""
        tokens = parsed_data.get('tokens', [])
        lines = parsed_data.get('lines', [])
        
        # Token-based metrics
        token_count = len(tokens)
        # Handle both dict tokens and string tokens
        if tokens and isinstance(tokens[0], dict):
            unique_tokens = len(set(t.get('value', '') for t in tokens))
        else:
            unique_tokens = len(set(str(t) for t in tokens))
        
        # Line-based metrics
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        comment_lines = [l for l in lines if l.strip().startswith('#')]
        
        # Calculate metrics
        return {
            'token_count': token_count,
            'unique_token_count': unique_tokens,
            'token_diversity': unique_tokens / max(token_count, 1),
            'line_count': len(lines),
            'code_line_count': len(code_lines),
            'comment_line_count': len(comment_lines),
            'comment_ratio': len(comment_lines) / max(len(lines), 1),
            'avg_line_length': sum(len(l) for l in lines) / max(len(lines), 1),
        }


# Convenience functions
def analyze_single_code(
    code: str,
    language: str = 'auto',
    threshold: float = 0.5
) -> AnalysisResult:
    """
    Quick analysis of a single code submission.
    
    Args:
        code: Source code
        language: Programming language
        threshold: Similarity threshold
        
    Returns:
        AnalysisResult
    """
    analyzer = CodeAnalyzer(threshold=threshold)
    return analyzer.analyze_code(code, language)


def compare_two_codes(
    code_a: str,
    code_b: str,
    language: str = 'auto',
    threshold: float = 0.5
) -> ComparisonResult:
    """
    Quick comparison of two code submissions.
    
    Args:
        code_a: First code
        code_b: Second code
        language: Programming language
        threshold: Similarity threshold
        
    Returns:
        ComparisonResult
    """
    analyzer = CodeAnalyzer(threshold=threshold)
    return analyzer.compare_codes(code_a, code_b, language, language)