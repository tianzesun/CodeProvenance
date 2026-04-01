"""MOSS benchmark runner.

Provides a standardized MOSS baseline for comparison against custom engines.

MOSS (Measure Of Software Similarity) is the established Stanford plagiarism
detection tool. This runner executes MOSS and parse results into the same
benchmark format used by benchmark/run_benchmark.py.

Usage:
    from benchmark.moss.runner import MossRunner
    
    runner = MossRunner(user_id="your_moss_user_id")
    results = runner.evaluate(dataset)
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymoss  # Standard MOSS python wrapper


@dataclass
class MossResult:
    """Result from a MOSS evaluation."""
    pairs: List[Dict[str, Any]] = field(default_factory=list)
    total_pairs_checked: int = 0
    pairs_with_matches: int = 0
    max_similarity: float = 0.0
    avg_similarity: float = 0.0
    errors: List[str] = field(default_factory=list)


class MossRunner:
    """MOSS benchmark runner.
    
    Runs MOSS against ground-truth datasets and returns results
    in the same format as other benchmark engines.
    
    Usage:
        runner = MossRunner(user_id="12345678")
        result = runner.evaluate(pairs)
        
        # Or standalone:
        runner = MossRunner(user_id="12345678")
        result = runner.run_moss(file_paths)
    """
    
    MOSS_LANG_MAP = {
        "python": "py",
        "java": "java",
        "c": "c",
        "cpp": "cc",
        "javascript": "js",
    }
    
    def __init__(self, user_id: Optional[str] = None, language: str = "py"):
        """Initialize MOSS runner.
        
        Args:
            user_id: MOSS user ID (get from https://theory.stanford.edu/~aiken/moss/).
            language: Language code for MOSS.
        """
        self.user_id = user_id or os.environ.get("MOSS_USER_ID", "")
        self.language = language
        self._enabled = bool(self.user_id)
    
    @property
    def name(self) -> str:
        """Return runner name for benchmark reporting."""
        return "moss_baseline"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code snippets using MOSS.
        
        Creates temporary files, runs MOSS, and parses result.
        Note: This is slow because MOSS requires external service calls.
        For bulk comparison, use run_moss_batch() instead.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            MOSS similarity percentage (0.0 - 100.0 converted to 0.0 - 1.0).
        """
        if not self._enabled:
            return 0.0
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.' + self.language, delete=False) as f1, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.' + self.language, delete=False) as f2:
            f1.write(code_a)
            f1_path = f1.name
            f2.write(code_b)
            f2_path = f2.name
        
        try:
            result = self.run_moss([f1_path, f2_path])
            if result.pairs:
                return result.pairs[0].get("similarity", 0.0)
        finally:
            Path(f1_path).unlink(missing_ok=True)
            Path(f2_path).unlink(missing_ok=True)
        
        return 0.0
    
    def run_moss(self, file_paths: List[str]) -> MossResult:
        """Run MOSS on a set of files.
        
        Args:
            file_paths: List of file paths to check for similarity.
            
        Returns:
            MossResult with MOSS output.
        """
        result = MossResult()
        
        if not self._enabled:
            result.errors.append("MOSS user ID not configured")
            return result
        
        if not file_paths:
            return result
        
        try:
            moss = pymoss.Moss(self.user_id, self.language)
            
            for fp in file_paths:
                moss.add_file_by_path(fp)
            
            moss.set_comment("CodeProvenance benchmark evaluation")
            url = moss.send()
            
            # Parse results from MOSS URL
            result = self._parse_moss_results(url)
            result.total_pairs_checked = len(file_paths)
            
        except Exception as e:
            result.errors.append(f"MOSS execution failed: {str(e)}")
        
        return result
    
    def _parse_moss_results(self, url: str) -> MossResult:
        """Parse MOSS results from the results URL.
        
        Args:
            url: MOSS results URL.
            
        Returns:
            MossResult with parsed pairs.
        """
        result = MossResult()
        
        if not self._enabled:
            return result
        
        try:
            import requests
            response = requests.get(url, timeout=30)
            html = response.text
        except Exception:
            return result
        
        # Parse HTML table
        pairs = re.findall(
            r'<a[^>]*>([^<]+)</a>.*?<a[^>]*>([^<]+)</a>.*?(\d+)%',
            html,
            re.DOTALL
        )
        
        similarities = []
        for file1, file2, pct in pairs:
            sim = float(pct) / 100.0
            result.pairs.append({
                "file1": file1.strip(),
                "file2": file2.strip(),
                "similarity": sim,
                "source": "moss",
            })
            similarities.append(sim)
        
        if similarities:
            result.pairs_with_matches = len(similarities)
            result.max_similarity = max(similarities)
            result.avg_similarity = sum(similarities) / len(similarities)
        
        return result
    
    def evaluate(
        self,
        pairs: List[Tuple[str, str, int]],
    ) -> List[Tuple[float, int, int, str, str]]:
        """Evaluate MOSS on a list of code pairs for benchmark comparison.
        
        Args:
            pairs: List of (code_a, code_b, label).
            
        Returns:
            List of (score, label, clone_type, code_a, code_b).
        """
        results: List[Tuple[float, int, int, str, str]] = []
        
        if not self._enabled:
            # Return zero scores for all pairs
            for code_a, code_b, label in pairs:
                results.append((0.0, label, 0, code_a, code_b))
            return results
        
        # Write all files to temp directory for bulk MOSS
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dir = Path(tmpdir)
            file_map: Dict[str, str] = {}
            
            for i, (code_a, code_b, label) in enumerate(pairs):
                path_a = tmp_dir / f"a_{i}.py"
                path_b = tmp_dir / f"b_{i}.py"
                path_a.write_text(code_a)
                path_b.write_text(code_b)
                file_map[f"a_{i}.py"] = str(path_a)
                file_map[f"b_{i}.py"] = str(path_b)
            
            # Run MOSS on all files
            try:
                moss = pymoss.Moss(self.user_id, self.language)
                all_files = list(set(file_map.values()))
                for fp in all_files:
                    moss.add_file_by_path(fp)
                
                url = moss.send()
                
                # Parse results
                moss_result = self._parse_moss_results(url)
                
                # Build score map
                score_map: Dict[Tuple[str, str], float] = {}
                for pair in moss_result.pairs:
                    f1 = Path(pair["file1"]).name
                    f2 = Path(pair["file2"]).name
                    score_map[(f1, f2)] = pair["similarity"]
                
                # Look up scores for each pair
                for i, (code_a, code_b, label) in enumerate(pairs):
                    key_a = f"a_{i}.py"
                    key_b = f"b_{i}.py"
                    score = score_map.get((key_a, key_b), 
                                 score_map.get((key_b, key_a), 0.0))
                    results.append((score, label, 0, code_a, code_b))
                    
            except Exception:
                for code_a, code_b, label in pairs:
                    results.append((0.0, label, 0, code_a, code_b))
        
        return results


class MossScoreEngine:
    """MOSS as a benchmark engine implementing BaseSimilarityEngine contract.
    
    Wraps MossRunner behind the standard engine interface.
    
    Usage:
        engine = MossScoreEngine(user_id="12345678")
        score = engine.compare(code_a, code_b)
    """
    
    def __init__(self, user_id: Optional[str] = None):
        """Initialize MOSS engine.
        
        Args:
            user_id: MOSS user ID.
        """
        self._runner = MossRunner(user_id=user_id)
    
    @property
    def name(self) -> str:
        """Return engine name."""
        return "moss_baseline_v1"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code snippets.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score [0, 1].
        """
        return self._runner.compare(code_a, code_b)