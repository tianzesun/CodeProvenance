"""
Batch Analyzer for CodeProvenance.

Provides batch processing capabilities for analyzing multiple code submissions.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import os

from .code_analyzer import CodeAnalyzer, AnalysisResult, ComparisonResult


@dataclass
class BatchAnalysisResult:
    """Result of batch analysis."""
    job_id: str
    total_submissions: int
    total_comparisons: int
    analysis_results: Dict[str, AnalysisResult]
    comparison_results: List[ComparisonResult]
    suspicious_pairs: List[ComparisonResult]
    summary: Dict[str, Any]
    execution_time: float
    timestamp: str


class BatchAnalyzer:
    """
    Batch analyzer for processing multiple code submissions.
    
    Features:
    - Parallel processing of submissions
    - Progress tracking
    - Result caching
    - Report generation
    """
    
    def __init__(
        self,
        analyzer: Optional[CodeAnalyzer] = None,
        max_workers: int = 4,
        cache_results: bool = True
    ):
        """
        Initialize batch analyzer.
        
        Args:
            analyzer: CodeAnalyzer instance (creates default if None)
            max_workers: Maximum parallel workers
            cache_results: Whether to cache results
        """
        self.analyzer = analyzer or CodeAnalyzer()
        self.max_workers = max_workers
        self.cache_results = cache_results
        self._cache: Dict[str, Any] = {}
    
    def analyze_submissions(
        self,
        submissions: Dict[str, str],
        languages: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> BatchAnalysisResult:
        """
        Analyze multiple code submissions.
        
        Args:
            submissions: Dictionary mapping file paths to code content
            languages: Optional language mappings
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchAnalysisResult with all analysis data
        """
        import time
        import uuid
        start_time = time.time()
        
        job_id = str(uuid.uuid4())[:8]
        file_list = list(submissions.keys())
        total_files = len(file_list)
        
        # Analyze individual submissions
        analysis_results: Dict[str, AnalysisResult] = {}
        for i, file_path in enumerate(file_list):
            code = submissions[file_path]
            language = languages.get(file_path, 'auto') if languages else 'auto'
            
            # Check cache
            cache_key = self._get_cache_key(code, language)
            if self.cache_results and cache_key in self._cache:
                analysis_results[file_path] = self._cache[cache_key]
            else:
                result = self.analyzer.analyze_code(code, language, file_path)
                analysis_results[file_path] = result
                if self.cache_results:
                    self._cache[cache_key] = result
            
            # Progress callback
            if progress_callback:
                progress_callback(i + 1, total_files)
        
        # Perform pairwise comparisons
        comparison_results = self.analyzer.analyze_pairwise(submissions, languages)
        
        # Find suspicious pairs
        suspicious_pairs = [r for r in comparison_results if r.is_suspicious]
        suspicious_pairs.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Calculate summary
        summary = self._calculate_summary(analysis_results, comparison_results, suspicious_pairs)
        
        execution_time = time.time() - start_time
        
        return BatchAnalysisResult(
            job_id=job_id,
            total_submissions=total_files,
            total_comparisons=len(comparison_results),
            analysis_results=analysis_results,
            comparison_results=comparison_results,
            suspicious_pairs=suspicious_pairs,
            summary=summary,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat()
        )
    
    def analyze_directory(
        self,
        directory_path: str,
        file_pattern: str = '*.py',
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> BatchAnalysisResult:
        """
        Analyze all code files in a directory.
        
        Args:
            directory_path: Path to directory
            file_pattern: File pattern to match (e.g., '*.py')
            recursive: Whether to search recursively
            progress_callback: Optional progress callback
            
        Returns:
            BatchAnalysisResult
        """
        path = Path(directory_path)
        
        if not path.exists():
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Find all matching files
        if recursive:
            files = list(path.rglob(file_pattern))
        else:
            files = list(path.glob(file_pattern))
        
        # Read file contents
        submissions = {}
        languages = {}
        
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                relative_path = str(file_path.relative_to(path))
                submissions[relative_path] = content
                
                # Detect language from extension
                ext = file_path.suffix.lower()
                language_map = {
                    '.py': 'python',
                    '.java': 'java',
                    '.js': 'javascript',
                    '.ts': 'typescript',
                    '.c': 'c',
                    '.cpp': 'cpp',
                    '.go': 'go',
                    '.rs': 'rust',
                }
                languages[relative_path] = language_map.get(ext, 'auto')
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")
        
        return self.analyze_submissions(submissions, languages, progress_callback)
    
    def _calculate_summary(
        self,
        analysis_results: Dict[str, AnalysisResult],
        comparison_results: List[ComparisonResult],
        suspicious_pairs: List[ComparisonResult]
    ) -> Dict[str, Any]:
        """Calculate summary statistics."""
        # Language distribution
        language_dist = {}
        for result in analysis_results.values():
            lang = result.language
            language_dist[lang] = language_dist.get(lang, 0) + 1
        
        # AI detection stats
        ai_detected = sum(
            1 for r in analysis_results.values()
            if r.ai_detection.get('is_likely_ai', False)
        )
        
        # Similarity stats
        if comparison_results:
            scores = [r.overall_score for r in comparison_results]
            avg_similarity = sum(scores) / len(scores)
            max_similarity = max(scores)
            min_similarity = min(scores)
        else:
            avg_similarity = max_similarity = min_similarity = 0.0
        
        # Complexity stats
        complexities = [r.complexity_metrics.get('token_count', 0) for r in analysis_results.values()]
        avg_complexity = sum(complexities) / max(len(complexities), 1)
        
        return {
            'language_distribution': language_dist,
            'ai_detected_count': ai_detected,
            'ai_detected_percentage': ai_detected / max(len(analysis_results), 1),
            'average_similarity': avg_similarity,
            'max_similarity': max_similarity,
            'min_similarity': min_similarity,
            'suspicious_pair_count': len(suspicious_pairs),
            'average_complexity': avg_complexity,
            'total_tokens': sum(r.token_count for r in analysis_results.values()),
            'total_lines': sum(r.line_count for r in analysis_results.values()),
        }
    
    def _get_cache_key(self, code: str, language: str) -> str:
        """Generate cache key for code."""
        import hashlib
        content_hash = hashlib.md5(code.encode()).hexdigest()
        return f"{language}:{content_hash}"
    
    def export_results(
        self,
        result: BatchAnalysisResult,
        output_dir: str,
        formats: List[str] = None
    ) -> Dict[str, str]:
        """
        Export batch analysis results.
        
        Args:
            result: BatchAnalysisResult to export
            output_dir: Output directory
            formats: List of formats ('json', 'html', 'csv')
            
        Returns:
            Dictionary mapping format to file path
        """
        if formats is None:
            formats = ['json', 'html']
        
        os.makedirs(output_dir, exist_ok=True)
        
        exported = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if 'json' in formats:
            json_path = os.path.join(output_dir, f'batch_analysis_{result.job_id}_{timestamp}.json')
            self._export_json(result, json_path)
            exported['json'] = json_path
        
        if 'html' in formats:
            html_path = os.path.join(output_dir, f'batch_analysis_{result.job_id}_{timestamp}.html')
            self._export_html(result, html_path)
            exported['html'] = html_path
        
        if 'csv' in formats:
            csv_path = os.path.join(output_dir, f'similarity_matrix_{result.job_id}_{timestamp}.csv')
            self._export_csv(result, csv_path)
            exported['csv'] = csv_path
        
        return exported
    
    def _export_json(self, result: BatchAnalysisResult, output_path: str):
        """Export results as JSON."""
        data = {
            'job_id': result.job_id,
            'timestamp': result.timestamp,
            'execution_time': result.execution_time,
            'summary': result.summary,
            'submissions': {
                path: {
                    'language': r.language,
                    'line_count': r.line_count,
                    'token_count': r.token_count,
                    'ai_detection': r.ai_detection,
                    'complexity_metrics': r.complexity_metrics,
                }
                for path, r in result.analysis_results.items()
            },
            'suspicious_pairs': [
                {
                    'file_a': r.file_a,
                    'file_b': r.file_b,
                    'overall_score': r.overall_score,
                    'individual_scores': r.individual_scores,
                }
                for r in result.suspicious_pairs
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _export_html(self, result: BatchAnalysisResult, output_path: str):
        """Export results as HTML."""
        from src.utils.report import ReportGenerator
        
        generator = ReportGenerator(title=f"Batch Analysis - Job {result.job_id}")
        
        # Prepare job data
        job_data = {
            'job_id': result.job_id,
            'name': f'Batch Analysis {result.job_id}',
            'total_comparisons': result.total_comparisons,
            'total_submissions': result.total_submissions,
        }
        
        # Prepare comparison results
        comparison_results = [
            {
                'file_a': r.file_a,
                'file_b': r.file_b,
                'overall_score': r.overall_score,
                'individual_scores': r.individual_scores,
            }
            for r in result.comparison_results
        ]
        
        # Prepare submissions
        submissions = {
            path: {
                'filename': Path(path).name,
                'language': r.language,
                'line_count': r.line_count,
                'token_count': r.token_count,
            }
            for path, r in result.analysis_results.items()
        }
        
        html = generator.generate_html(
            job_data,
            comparison_results,
            submissions,
            threshold=self.analyzer.threshold
        )
        
        with open(output_path, 'w') as f:
            f.write(html)
    
    def _export_csv(self, result: BatchAnalysisResult, output_path: str):
        """Export similarity matrix as CSV."""
        lines = ['file_a,file_b,overall_score,token_score,ngram_score,ast_score,winnowing_score']
        
        for r in result.comparison_results:
            scores = r.individual_scores
            lines.append(
                f'"{r.file_a}","{r.file_b}",'
                f'{r.overall_score:.4f},'
                f'{scores.get("token", 0):.4f},'
                f'{scores.get("ngram", 0):.4f},'
                f'{scores.get("ast", 0):.4f},'
                f'{scores.get("winnowing", 0):.4f}'
            )
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))


def analyze_batch(
    submissions: Dict[str, str],
    threshold: float = 0.5,
    languages: Optional[Dict[str, str]] = None
) -> BatchAnalysisResult:
    """
    Convenience function for batch analysis.
    
    Args:
        submissions: Dictionary mapping file paths to code
        threshold: Similarity threshold
        languages: Optional language mappings
        
    Returns:
        BatchAnalysisResult
    """
    analyzer = CodeAnalyzer(threshold=threshold)
    batch_analyzer = BatchAnalyzer(analyzer=analyzer)
    return batch_analyzer.analyze_submissions(submissions, languages)


def analyze_directory(
    directory_path: str,
    file_pattern: str = '*.py',
    threshold: float = 0.5,
    recursive: bool = True
) -> BatchAnalysisResult:
    """
    Convenience function for directory analysis.
    
    Args:
        directory_path: Path to directory
        file_pattern: File pattern to match
        threshold: Similarity threshold
        recursive: Whether to search recursively
        
    Returns:
        BatchAnalysisResult
    """
    analyzer = CodeAnalyzer(threshold=threshold)
    batch_analyzer = BatchAnalyzer(analyzer=analyzer)
    return batch_analyzer.analyze_directory(directory_path, file_pattern, recursive)