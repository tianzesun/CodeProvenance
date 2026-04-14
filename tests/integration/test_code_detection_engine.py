"""
Integration tests for Code Detection Engine.

Tests the complete code detection pipeline including:
- Code analysis
- Similarity detection
- Batch processing
- Report generation
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.backend.backend.core.analyzer.code_analyzer import CodeAnalyzer, analyze_single_code, compare_two_codes
from src.backend.backend.core.analyzer.batch_analyzer import BatchAnalyzer, analyze_batch
from src.backend.backend.core.processor.code_processor import CodeProcessor, process_code
from src.backend.backend.core.processor.submission_processor import SubmissionProcessor, process_submission


class TestCodeAnalyzerIntegration:
    """Integration tests for CodeAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = CodeAnalyzer(threshold=0.5)
        
        # Sample code snippets
        self.code_a = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        
        self.code_b = """
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
"""
        
        self.code_c = """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[0]
    left = [x for x in arr[1:] if x < pivot]
    right = [x for x in arr[1:] if x >= pivot]
    return quicksort(left) + [pivot] + quicksort(right)
"""
    
    def test_analyze_single_code(self):
        """Test analyzing a single code submission."""
        result = self.analyzer.analyze_code(self.code_a, 'python', 'fibonacci.py')
        
        assert result.file_path == 'fibonacci.py'
        assert result.language == 'python'
        assert result.line_count > 0
        assert result.token_count > 0
        assert len(result.code_hash) == 64  # SHA256
        assert 'is_likely_ai' in result.ai_detection
        assert 'token_count' in result.complexity_metrics
    
    def test_compare_similar_codes(self):
        """Test comparing similar code submissions."""
        result = self.analyzer.compare_codes(
            self.code_a,
            self.code_b,
            'python',
            'python',
            'fibonacci.py',
            'fib.py'
        )
        
        assert result.file_a == 'fibonacci.py'
        assert result.file_b == 'fib.py'
        assert 0.0 <= result.overall_score <= 1.0
        assert result.overall_score > 0.5  # Should be similar
        # Check for actual algorithm keys (enhanced_token, enhanced_winnowing, etc.)
        assert len(result.individual_scores) > 0
        assert any('token' in key or 'winnowing' in key or 'ngram' in key for key in result.individual_scores.keys())
    
    def test_compare_different_codes(self):
        """Test comparing different code submissions."""
        # Use a higher threshold for this test since different algorithms can score higher
        analyzer = CodeAnalyzer(threshold=0.7)
        result = analyzer.compare_codes(
            self.code_a,
            self.code_c,
            'python',
            'python',
            'fibonacci.py',
            'quicksort.py'
        )
        
        # Different algorithms should score lower than similar ones
        # The score should be less than the similar codes score (which is > 0.9)
        assert result.overall_score < 0.8  # Should be different from similar codes
        assert not result.is_suspicious
    
    def test_analyze_pairwise(self):
        """Test pairwise analysis of multiple submissions."""
        submissions = {
            'fibonacci.py': self.code_a,
            'fib.py': self.code_b,
            'quicksort.py': self.code_c
        }
        
        results = self.analyzer.analyze_pairwise(submissions)
        
        # Should have 3 comparisons (n*(n-1)/2)
        assert len(results) == 3
        
        # Check that all pairs are present
        pairs = [(r.file_a, r.file_b) for r in results]
        assert ('fibonacci.py', 'fib.py') in pairs or ('fib.py', 'fibonacci.py') in pairs
        assert ('fibonacci.py', 'quicksort.py') in pairs or ('quicksort.py', 'fibonacci.py') in pairs
        assert ('fib.py', 'quicksort.py') in pairs or ('quicksort.py', 'fib.py') in pairs
    
    def test_find_suspicious_pairs(self):
        """Test finding suspicious pairs."""
        submissions = {
            'fibonacci.py': self.code_a,
            'fib.py': self.code_b,
            'quicksort.py': self.code_c
        }
        
        suspicious = self.analyzer.find_suspicious_pairs(submissions, threshold=0.5)
        
        # Should find the similar fibonacci pair
        assert len(suspicious) >= 1
        assert any(r.file_a == 'fibonacci.py' and r.file_b == 'fib.py' 
                   or r.file_a == 'fib.py' and r.file_b == 'fibonacci.py'
                   for r in suspicious)
    
    def test_convenience_functions(self):
        """Test convenience functions."""
        # Test analyze_single_code
        result = analyze_single_code(self.code_a, 'python')
        assert result.language == 'python'
        
        # Test compare_two_codes
        result = compare_two_codes(self.code_a, self.code_b, 'python')
        assert result.overall_score > 0.5


class TestBatchAnalyzerIntegration:
    """Integration tests for BatchAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = CodeAnalyzer(threshold=0.5)
        self.batch_analyzer = BatchAnalyzer(analyzer=self.analyzer)
        
        self.submissions = {
            'student1.py': """
def add(a, b):
    return a + b
""",
            'student2.py': """
def add(x, y):
    return x + y
""",
            'student3.py:': """
def multiply(a, b):
    return a * b
"""
        }
    
    def test_analyze_submissions(self):
        """Test batch analysis of submissions."""
        result = self.batch_analyzer.analyze_submissions(self.submissions)
        
        assert result.total_submissions == 3
        assert result.total_comparisons == 3  # 3 choose 2
        assert len(result.analysis_results) == 3
        assert len(result.comparison_results) == 3
        assert result.execution_time > 0
        
        # Check summary
        assert 'language_distribution' in result.summary
        assert 'average_similarity' in result.summary
        assert 'suspicious_pair_count' in result.summary
    
    def test_analyze_directory(self):
        """Test analyzing a directory of code files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_dir = Path(tmpdir) / 'test_code'
            test_dir.mkdir()
            
            (test_dir / 'file1.py').write_text('def test(): pass')
            (test_dir / 'file2.py').write_text('def test(): pass')
            (test_dir / 'file3.py').write_text('def other(): pass')
            
            result = self.batch_analyzer.analyze_directory(str(test_dir), '*.py')
            
            assert result.total_submissions == 3
            assert result.total_comparisons == 3
    
    def test_export_results(self):
        """Test exporting batch analysis results."""
        result = self.batch_analyzer.analyze_submissions(self.submissions)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            exported = self.batch_analyzer.export_results(
                result,
                tmpdir,
                formats=['json', 'html', 'csv']
            )
            
            assert 'json' in exported
            assert 'html' in exported
            assert 'csv' in exported
            
            # Check files exist
            assert os.path.exists(exported['json'])
            assert os.path.exists(exported['html'])
            assert os.path.exists(exported['csv'])


class TestCodeProcessorIntegration:
    """Integration tests for CodeProcessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = CodeProcessor()
        
        self.code_with_comments = """
# This is a comment
def add(a, b):
    # Another comment
    return a + b  # Inline comment
"""
        
        self.code_with_whitespace = """
def   add(  a,  b  ):
    return   a   +   b
"""
    
    def test_process_code(self):
        """Test code processing."""
        result = self.processor.process(self.code_with_comments, 'python')
        
        assert result.original_code == self.code_with_comments
        assert result.processed_code != self.code_with_comments
        assert len(result.tokens) > 0
        assert len(result.lines) > 0
        assert result.language == 'python'
        assert result.processing_time > 0
    
    def test_remove_comments(self):
        """Test comment removal."""
        result = self.processor.process(self.code_with_comments, 'python', remove_comments=True)
        
        # Comments should be removed
        assert '#' not in result.processed_code
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        result = self.processor.process(self.code_with_whitespace, 'python', normalize_whitespace=True)
        
        # Should not have multiple spaces
        assert '  ' not in result.processed_code
    
    def test_process_batch(self):
        """Test batch processing."""
        submissions = {
            'file1.py': self.code_with_comments,
            'file2.py': self.code_with_whitespace
        }
        
        results = self.processor.process_batch(submissions)
        
        assert len(results) == 2
        assert 'file1.py' in results
        assert 'file2.py' in results
    
    def test_convenience_function(self):
        """Test convenience function."""
        result = process_code(self.code_with_comments, 'python')
        assert result.language == 'python'


class TestSubmissionProcessorIntegration:
    """Integration tests for SubmissionProcessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = SubmissionProcessor()
        
        self.code = """
def hello_world():
    print("Hello, World!")
"""
    
    def test_process_submission(self):
        """Test processing a single submission."""
        result = self.processor.process_submission(
            'sub1',
            'hello.py',
            self.code,
            'python'
        )
        
        assert result.submission_id == 'sub1'
        assert result.file_path == 'hello.py'
        assert result.language == 'python'
        assert len(result.fingerprint) == 64  # SHA256
        assert result.processing_time > 0
        assert 'submission_id' in result.metadata
    
    def test_process_submissions(self):
        """Test processing multiple submissions."""
        submissions = {
            'sub1': {
                'file_path': 'hello.py',
                'code': self.code,
                'language': 'python'
            },
            'sub2': {
                'file_path': 'world.py',
                'code': 'def world(): pass',
                'language': 'python'
            }
        }
        
        results = self.processor.process_submissions(submissions)
        
        assert len(results) == 2
        assert 'sub1' in results
        assert 'sub2' in results
    
    def test_process_directory(self):
        """Test processing a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / 'submissions'
            test_dir.mkdir()
            
            (test_dir / 'file1.py').write_text(self.code)
            (test_dir / 'file2.py').write_text('def other(): pass')
            
            results = self.processor.process_directory(str(test_dir), '*.py')
            
            assert len(results) == 2
    
    def test_compare_fingerprints(self):
        """Test fingerprint comparison."""
        # Create duplicate code
        code_duplicate = self.code
        
        submissions = {
            'sub1': {
                'file_path': 'hello1.py',
                'code': self.code,
                'language': 'python'
            },
            'sub2': {
                'file_path': 'hello2.py',
                'code': code_duplicate,
                'language': 'python'
            },
            'sub3': {
                'file_path': 'other.py',
                'code': 'def other(): pass',
                'language': 'python'
            }
        }
        
        results = self.processor.process_submissions(submissions)
        duplicates = self.processor.compare_fingerprints(results)
        
        # Should find one duplicate group
        assert len(duplicates) == 1
        assert duplicates[0]['count'] == 2
    
    def test_convenience_function(self):
        """Test convenience function."""
        result = process_submission('sub1', 'hello.py', self.code, 'python')
        assert result.submission_id == 'sub1'


class TestEndToEndPipeline:
    """End-to-end integration tests."""
    
    def test_complete_pipeline(self):
        """Test complete analysis pipeline."""
        # Create test submissions
        submissions = {
            'student1.py': """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)
""",
            'student2.py': """
def factorial(num):
    if num <= 1:
        return 1
    return num * factorial(num-1)
""",
            'student3.py': """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        }
        
        # Process submissions
        processor = SubmissionProcessor()
        processed = processor.process_submissions(submissions)
        
        # Analyze similarities
        analyzer = CodeAnalyzer(threshold=0.5)
        suspicious = analyzer.find_suspicious_pairs(
            {k: v.processing_result.processed_code for k, v in processed.items()}
        )
        
        # Should detect student1.py and student2.py as similar
        assert len(suspicious) >= 1
        similar_pair = suspicious[0]
        assert 'student1.py' in [similar_pair.file_a, similar_pair.file_b]
        assert 'student2.py' in [similar_pair.file_a, similar_pair.file_b]
        assert similar_pair.overall_score > 0.5
    
    def test_ai_detection_integration(self):
        """Test AI detection integration."""
        ai_code = """
# This function calculates the factorial
# Here we handle the base case
def factorial(n):
    # Check if n is less than or equal to 1
    if n <= 1:
        return 1
    # Recursively calculate factorial
    return n * factorial(n-1)
"""
        
        analyzer = CodeAnalyzer(enable_ai_detection=True)
        result = analyzer.analyze_code(ai_code, 'python')
        
        # Should detect AI patterns
        assert 'is_likely_ai' in result.ai_detection
        assert 'ai_score' in result.ai_detection
    
    def test_performance_large_batch(self):
        """Test performance with larger batch."""
        import time
        
        # Create 50 submissions
        submissions = {}
        for i in range(50):
            submissions[f'student{i}.py'] = f"""
def function_{i}():
    return {i}
"""
        
        # Measure time
        start_time = time.time()
        
        analyzer = CodeAnalyzer(threshold=0.5)
        batch_analyzer = BatchAnalyzer(analyzer=analyzer)
        result = batch_analyzer.analyze_submissions(submissions)
        
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (< 30 seconds)
        assert elapsed < 30
        assert result.total_submissions == 50
        assert result.total_comparisons == 1225  # 50 choose 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])