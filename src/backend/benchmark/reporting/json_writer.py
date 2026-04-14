"""JSON report writer for benchmark results.

Provides structured JSON output for reproducibility and analysis.
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class JSONReportWriter:
    """Writes benchmark results to JSON format.
    
    Usage:
        writer = JSONReportWriter("output.json")
        writer.write(result_dict)
    """
    
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
    
    def write(
        self,
        results: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """Write results to JSON file.
        
        Args:
            results: Benchmark results dict.
            metadata: Optional metadata dict.
            
        Returns:
            Path to written file.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "results": results
        }
        
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return str(self.output_path)
    
    @staticmethod
    def read(path: str) -> Dict[str, Any]:
        """Read a previously written report.
        
        Args:
            path: Path to JSON file.
            
        Returns:
            Report dict.
        """
        with open(path, 'r') as f:
            return json.load(f)
    
    def write_batch(
        self,
        results: List[Dict[str, Any]],
        summary: Dict[str, Any] = None
    ) -> str:
        """Write multiple results with summary.
        
        Args:
            results: List of result dicts.
            summary: Optional summary dict.
            
        Returns:
            Path to written file.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary or {},
            "results": results
        }
        
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return str(self.output_path)