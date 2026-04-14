import json
import hashlib
import platform
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from .core.evaluator import EvaluationResult

logger = logging.getLogger(__name__)

class ReproducibilityReport:
    """
    Generates a formal reproducibility report for academic submission.
    Ensures that all experiments can be tracked back to their source.
    """
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.report_data: Dict[str, Any] = {
            "metadata": {
                "timestamp": datetime.datetime.now().isoformat(),
                "system": {
                    "os": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "python_version": platform.python_version(),
                }
            },
            "configuration": {},
            "datasets": [],
            "results": {},
            "hashes": {}
        }

    def record_config(self, config: Dict[str, Any]):
        """Record system and engine configuration."""
        self.report_data["configuration"] = config

    def record_dataset(self, name: str, version: str, path: Path, integrity_hash: str):
        """Record dataset information used in the experiment."""
        self.report_data["datasets"].append({
            "name": name,
            "version": version,
            "path": str(path),
            "integrity_hash": integrity_hash
        })

    def record_results(self, experiment_name: str, results: EvaluationResult):
        """Record evaluation results."""
        self.report_data["results"][experiment_name] = {
            "precision": results.precision,
            "recall": results.recall,
            "f1": results.f1,
            "accuracy": results.accuracy,
            "auc_roc": results.auc_roc,
            "ece": results.ece,
            "metadata": results.metadata
        }

    def generate(self):
        """Finalize and save the report."""
        # Compute a hash of the entire results section for integrity
        results_str = json.dumps(self.report_data["results"], sort_keys=True)
        self.report_data["hashes"]["results_hash"] = hashlib.sha256(results_str.encode()).hexdigest()
        
        with open(self.output_path, 'w') as f:
            json.dump(self.report_data, f, indent=2)
        logger.info(f"Reproducibility report generated: {self.output_path}")

class CIGate:
    """
    Stricter CI Gate for performance and integrity.
    Used to enforce 'publication-grade' standards.
    """
    
    def __init__(self, baseline_path: Optional[Path] = None):
        self.baseline = self._load_baseline(baseline_path) if baseline_path else {}

    def _load_baseline(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def check_performance(self, current: EvaluationResult, min_f1: float = 0.8, max_ece: float = 0.1) -> bool:
        """
        Check if performance meets the required standards.
        """
        passed = True
        if current.f1 < min_f1:
            logger.error(f"Performance Check Failed: F1 {current.f1:.4f} < {min_f1:.4f}")
            passed = False
            
        if current.ece and current.ece > max_ece:
            logger.error(f"Performance Check Failed: ECE {current.ece:.4f} > {max_ece:.4f}")
            passed = False
            
        return passed

    def check_regression(self, current: EvaluationResult, tolerance: float = 0.01) -> bool:
        """
        Check for performance regression against baseline.
        """
        if not self.baseline:
            return True
            
        baseline_f1 = self.baseline.get("f1", 0.0)
        if current.f1 < baseline_f1 - tolerance:
            logger.error(f"Regression Check Failed: F1 {current.f1:.4f} < Baseline {baseline_f1:.4f} - {tolerance}")
            return False
        return True
